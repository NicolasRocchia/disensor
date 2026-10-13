#!/usr/bin/env python3
"""Corre la medición de lectura pública (#110). El método está en el README de
este directorio; esto solo ejecuta y registra.

Dos experimentos con la misma pregunta. A (modo `documento`): cada modelo, en
sesión fresca, recibe la pregunta y el README entero de un commit, el de antes
y el de después del ejemplo real. B (modo `busqueda`): sesión fresca con
búsqueda web y solo la pregunta. Cada corrida queda en
corridas/<fecha>/<modelo>-<modo>-<idioma>-<estado>.md con su encabezado y la
respuesta sin editar. No puntúa: eso es puntuar.py.

Correr desde la raíz del repositorio:

    python3 docs/notes/lectura-publica/correr.py --fecha 2026-10-12 [--modo documento|busqueda|todos]
        [--modelos claude-sonnet,claude-haiku,codex] [--idiomas es,en] [--estados antes,despues]

Los README salen de git (`git show <commit>:<ruta>`), no del árbol de trabajo.
Una corrida que ya existe no se repite con el mismo nombre: `--repeticion N`
la guarda aparte, con sufijo -rN y `repeticion: N` en el encabezado, y
puntuar.py las cuenta todas. Una corrida que falla (el CLI sale
con error o no contesta) no deja archivo: se informa y se sigue con la
siguiente, para que un fallo de infraestructura no quede como si fuera una
respuesta del modelo.

Los dos CLIs se corren desde un directorio vacío y temporal, no desde el
repo: `claude -p` recibe del harness el directorio de trabajo y, si es un
repositorio, su rama, su estado y sus commits recientes, aunque --safe-mode
apague CLAUDE.md; codex explora lo que tiene a mano.

Confinamiento, que no es lo mismo en los dos CLIs y el encabezado lo dice:
`claude -p --tools ""` apaga las herramientas por construcción, y `num_turns`
queda registrado. `codex exec` no tiene un flag que las apague, y su sandbox
no arranca desde algunos procesos padre en Windows: en modo documento el
confinamiento es por instrucción, y lo que sí se registra, leyendo los eventos
JSONL de la corrida, es cuántas herramientas llamó. puntuar.py deja fuera del
experimento A toda corrida de documento con llamadas a herramientas.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]

COMMITS = {"antes": "de14e5c", "despues": "96e12ae"}
DOCUMENTOS = {"es": "README.es.md", "en": "README.md"}
PREGUNTA = {
    "es": "¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.",
    "en": "What is disensor and what does the file it generates look like? Show an example of the artifact.",
}
PREFACIO = {
    "documento": {
        "es": "Contestá usando solo el documento que sigue, sin buscar en la web ni usar herramientas.",
        "en": "Answer using only the document below, without searching the web or using tools.",
    },
    "busqueda": {
        "es": "Buscá en la web lo que necesites y citá de dónde sale cada cosa.",
        "en": "Search the web for whatever you need and cite where each thing comes from.",
    },
}
MODELOS = {
    "claude-sonnet": {"cli": "claude", "modelo": "sonnet"},
    "claude-haiku": {"cli": "claude", "modelo": "haiku"},
    "codex": {"cli": "codex", "modelo": "gpt-5.6-sol"},
}
# Los flags de la receta endurecida del catálogo de revisores. El bypass del
# sandbox está porque el sandbox de codex no arranca desde Claude Code en
# Windows; NO apaga las herramientas, y por eso se registran los eventos.
CODEX_BASE = [
    "exec",
    "--json",
    "-m", MODELOS["codex"]["modelo"],
    "--dangerously-bypass-approvals-and-sandbox",
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "-c", "project_doc_max_bytes=0",
    "--skip-git-repo-check",
]
# Tipos de ítem de los eventos JSONL de codex que NO son una llamada a
# herramienta: el mensaje del agente y su razonamiento. Todo otro ítem
# completado cuenta como herramienta, a propósito: una versión del CLI que
# renombre o agregue un tipo tiene que sobrar y sacar la corrida de A, no
# faltar y colarla. El conteo completo por tipo queda en el encabezado, para
# que se pueda releer.
ITEMS_BENIGNOS = ("agent_message", "reasoning")
# Tope por corrida. Un CLI que no termina es una corrida fallida, no el fin
# de la tanda (lo cazó la ronda 4).
TIMEOUT_S = 1800


class CorridaFallida(RuntimeError):
    """El CLI no devolvió una respuesta: no hay nada que guardar como corrida."""


def log(msg: str) -> None:
    print(f"[correr] {msg}", flush=True)


def ejecutable(nombre: str) -> str:
    ruta = shutil.which(nombre)
    if not ruta:
        raise SystemExit(f"no encuentro {nombre} en el PATH")
    return ruta


def version(nombre: str) -> str:
    try:
        salida = subprocess.run([ejecutable(nombre), "--version"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60)
        return (salida.stdout or salida.stderr).strip().splitlines()[0]
    except Exception as err:  # noqa: BLE001
        return f"desconocida ({err})"


def git_show(commit: str, ruta: str) -> str:
    salida = subprocess.run(["git", "show", f"{commit}:{ruta}"], cwd=RAIZ, capture_output=True,
                            text=True, encoding="utf-8", check=True)
    return salida.stdout


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def armar_prompt(modo: str, idioma: str, documento: str | None) -> str:
    partes = [PREFACIO[modo][idioma], "", PREGUNTA[idioma]]
    if modo == "documento":
        assert documento is not None
        partes += ["", "----- documento -----", "", documento]
    return "\n".join(partes) + "\n"


def correr_claude(modelo: str, modo: str, prompt: str) -> tuple[str, dict, list[str]]:
    herramientas = "" if modo == "documento" else "WebSearch,WebFetch"
    cmd = [ejecutable("claude"), "-p", "--safe-mode", "--no-session-persistence",
           "--model", modelo, "--output-format", "json", "--tools", herramientas]
    # Desde un directorio vacío y temporal, igual que codex, y por una razón
    # medida: `claude -p` recibe del harness el directorio de trabajo y, si es
    # un repositorio, su rama, su estado y sus commits recientes, aunque
    # --safe-mode apague CLAUDE.md. Corrido desde la raíz del repo, el modelo
    # vio mensajes de commit que nombran final_state y los seis estados, y
    # las corridas de búsqueda hablaron de "tu worktree": eso no es "solo el
    # documento". Lo mostraron las doce corridas del 13/10 a la mañana.
    cuna = Path(tempfile.mkdtemp(prefix="lectura-publica-"))
    try:
        salida = subprocess.run(cmd, input=prompt, cwd=cuna, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as err:
        raise CorridaFallida(f"claude no terminó en {TIMEOUT_S} s") from err
    finally:
        shutil.rmtree(cuna, ignore_errors=True)
    if salida.returncode != 0:
        raise CorridaFallida(f"claude salió con {salida.returncode}: {salida.stderr[-2000:]}")
    try:
        datos = json.loads(salida.stdout)
    except json.JSONDecodeError as err:
        raise CorridaFallida(f"la salida de claude no fue JSON: {salida.stdout[-500:]}") from err
    if datos.get("is_error") or not datos.get("result"):
        raise CorridaFallida(f"claude no contestó: {datos.get('result')!r}")
    texto = datos["result"]
    meta = {k: datos.get(k) for k in ("duration_ms", "duration_api_ms", "num_turns", "total_cost_usd", "subtype")
            if k in datos}
    if isinstance(datos.get("usage"), dict):
        meta["usage"] = datos["usage"]
    if isinstance(datos.get("modelUsage"), dict):
        meta["modelos_usados"] = sorted(datos["modelUsage"].keys())
    # Un turno es la respuesta; cada herramienta agrega uno. Con --tools "" no
    # hay herramientas, y el número lo confirma.
    meta["llamadas_a_herramientas"] = max(0, int(datos.get("num_turns") or 1) - 1)
    # Acá no hay un flujo de eventos que leer: `--output-format json` devuelve
    # un único JSON, que se parseó entero arriba o la corrida falló sin dejar
    # archivo. Cero líneas ilegibles es una propiedad de la salida, no un
    # conteo que falte, y se registra para que puntuar.py no lo tome por un
    # registro ausente (lo que sacó de A a las ocho corridas de documento del
    # 13/10, hechas antes de este campo).
    meta["eventos_ilegibles"] = 0
    return texto, meta, cmd


def contar_eventos(jsonl: str) -> tuple[Counter, int, int]:
    """Tipos de evento e ítem de los eventos JSONL de codex, cuántos son
    herramientas, y cuántas líneas que parecían un evento no se pudieron leer.

    Una línea ilegible (un evento truncado, un envoltorio distinto) podría ser
    una herramienta que no se contó: se registra aparte y puntuar.py saca de
    A toda corrida de documento que tenga alguna. Lo pidió la ronda 4.
    """
    tipos: Counter = Counter()
    herramientas = 0
    ilegibles = 0
    for linea in jsonl.splitlines():
        linea = linea.strip()
        if not linea.startswith("{"):
            continue
        try:
            evento = json.loads(linea)
        except json.JSONDecodeError:
            ilegibles += 1
            continue
        tipo = str(evento.get("type", "?"))
        item = evento.get("item")
        if isinstance(item, dict):
            tipo_item = str(item.get("type", "?"))
            tipos[f"{tipo}/{tipo_item}"] += 1
            if tipo.endswith("completed") and tipo_item not in ITEMS_BENIGNOS:
                herramientas += 1
        else:
            tipos[tipo] += 1
    return tipos, herramientas, ilegibles


def correr_codex(modo: str, prompt: str) -> tuple[str, dict, list[str]]:
    # Desde un directorio vacío y temporal: no hay repositorio que explorar ni
    # AGENTS.md que leer, y lo que escriba se va con el directorio. Eso acota,
    # no confina: el conteo de herramientas de abajo es lo que dice qué hizo.
    cuna = Path(tempfile.mkdtemp(prefix="lectura-publica-"))
    ultimo = cuna / "respuesta.md"
    # `--search` es flag global de `codex`, no del subcomando `exec`: va antes.
    cmd = [ejecutable("codex")] + (["--search"] if modo == "busqueda" else []) + CODEX_BASE + ["-o", str(ultimo)]
    try:
        salida = subprocess.run(cmd, input=prompt, cwd=cuna, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        texto = ultimo.read_text(encoding="utf-8") if ultimo.exists() else ""
    except subprocess.TimeoutExpired as err:
        raise CorridaFallida(f"codex no terminó en {TIMEOUT_S} s") from err
    finally:
        shutil.rmtree(cuna, ignore_errors=True)
    if salida.returncode != 0:
        raise CorridaFallida(f"codex salió con {salida.returncode}: {salida.stderr[-2000:]}")
    if not texto.strip():
        raise CorridaFallida(f"codex no escribió respuesta; cola de stdout: {salida.stdout[-1000:]}")
    tipos, herramientas, ilegibles = contar_eventos(salida.stdout)
    meta = {"eventos": dict(sorted(tipos.items())), "llamadas_a_herramientas": herramientas,
            "eventos_ilegibles": ilegibles}
    return texto, meta, cmd


def mostrar_comando(cmd: list[str]) -> str:
    # Sin rutas de esta máquina: el nombre del CLI y sus flags, que es lo
    # reproducible. Un argumento vacío se muestra como "", y el archivo de
    # salida (un temporal con el nombre de la cuenta adentro) como <archivo>.
    # Lo cazó la ronda adversarial: la primera versión solo sacaba la ruta del
    # ejecutable.
    partes = [Path(cmd[0]).stem]
    anterior = ""
    for a in cmd[1:]:
        if anterior in ("-o", "--output-last-message"):
            partes.append("<archivo>")
        else:
            partes.append(a if a != "" else '""')
        anterior = a
    return " ".join(p if " " not in p else f'"{p}"' for p in partes)


def escribir_corrida(destino: Path, encabezado: dict, respuesta: str) -> None:
    lineas = [f"# {encabezado['modelo']}, {encabezado['modo']}, {encabezado['idioma']}, {encabezado['estado']}", "", "```yaml"]
    for clave, valor in encabezado.items():
        if isinstance(valor, (dict, list)):
            valor = json.dumps(valor, ensure_ascii=False)
        lineas.append(f"{clave}: {valor}")
    lineas += ["```", "", "## Respuesta", "", respuesta.rstrip("\n"), ""]
    destino.write_text("\n".join(lineas), encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fecha", default=dt.date.today().isoformat())
    ap.add_argument("--modo", choices=["documento", "busqueda", "todos"], default="todos")
    ap.add_argument("--modelos", default=",".join(MODELOS))
    ap.add_argument("--idiomas", default="es,en")
    ap.add_argument("--estados", default="antes,despues", help="Solo para el modo documento.")
    ap.add_argument("--repeticion", type=int, default=1,
                    help="Número de repetición: 1 es la corrida base; N > 1 agrega el sufijo -rN al archivo.")
    args = ap.parse_args()
    if args.repeticion < 1:
        raise SystemExit("--repeticion empieza en 1")
    sufijo = f"-r{args.repeticion}" if args.repeticion > 1 else ""

    modelos = [m.strip() for m in args.modelos.split(",") if m.strip()]
    for m in modelos:
        if m not in MODELOS:
            raise SystemExit(f"modelo desconocido: {m}; conozco {', '.join(MODELOS)}")
    idiomas = [i.strip() for i in args.idiomas.split(",") if i.strip()]
    estados = [e.strip() for e in args.estados.split(",") if e.strip()]
    modos = ["documento", "busqueda"] if args.modo == "todos" else [args.modo]

    carpeta = AQUI / "corridas" / args.fecha
    carpeta.mkdir(parents=True, exist_ok=True)
    versiones = {cli: version(cli) for cli in sorted({MODELOS[m]["cli"] for m in modelos})}

    plan: list[tuple[str, str, str, str]] = []
    for modo in modos:
        for modelo in modelos:
            for idioma in idiomas:
                if modo == "documento":
                    plan += [(modelo, modo, idioma, estado) for estado in estados]
                else:
                    plan.append((modelo, modo, idioma, "despues"))
    log(f"{len(plan)} corrida(s) planificadas en {carpeta.relative_to(RAIZ)}")

    fallidas: list[str] = []
    for modelo, modo, idioma, estado in plan:
        destino = carpeta / f"{modelo}-{modo}-{idioma}-{estado}{sufijo}.md"
        if destino.exists():
            log(f"ya existe, no se repite: {destino.name}")
            continue
        documento = None
        encabezado = {
            "modelo": modelo,
            "modelo_pedido": MODELOS[modelo]["modelo"],
            "cli": f"{MODELOS[modelo]['cli']} {versiones[MODELOS[modelo]['cli']]}",
            "modo": modo,
            "idioma": idioma,
            "estado": estado,
            "repeticion": args.repeticion,
            "pregunta": PREGUNTA[idioma],
        }
        if modo == "documento":
            commit = COMMITS[estado]
            documento = git_show(commit, DOCUMENTOS[idioma])
            encabezado.update({"documento": DOCUMENTOS[idioma], "commit": commit,
                               "sha256": sha256(documento), "bytes": len(documento.encode("utf-8"))})
        else:
            encabezado["documento"] = "web"
        prompt = armar_prompt(modo, idioma, documento)
        encabezado["prompt_sha256"] = sha256(prompt)
        log(f"corriendo {destino.name}")
        inicio = dt.datetime.now().astimezone()
        t0 = time.monotonic()
        try:
            if MODELOS[modelo]["cli"] == "claude":
                respuesta, meta, cmd = correr_claude(MODELOS[modelo]["modelo"], modo, prompt)
            else:
                respuesta, meta, cmd = correr_codex(modo, prompt)
        except CorridaFallida as err:
            log(f"  FALLÓ, no se guarda: {err}")
            fallidas.append(destino.name)
            continue
        fin = dt.datetime.now().astimezone()
        encabezado.update({"comando": mostrar_comando(cmd), "inicio": inicio.isoformat(timespec="seconds"),
                           "fin": fin.isoformat(timespec="seconds"), "duracion_s": int(time.monotonic() - t0)})
        encabezado["confinamiento"] = ("herramientas apagadas por construcción (--tools \"\")"
                                       if MODELOS[modelo]["cli"] == "claude" and modo == "documento"
                                       else "por instrucción; ver llamadas_a_herramientas" if modo == "documento"
                                       else "con búsqueda web, a propósito")
        encabezado.update({f"cli_{k}": v for k, v in meta.items()})
        escribir_corrida(destino, encabezado, respuesta)
        aviso = f", {meta['llamadas_a_herramientas']} llamada(s) a herramientas" if modo == "documento" else ""
        log(f"  listo en {encabezado['duracion_s']} s, {len(respuesta)} caracteres{aviso}")
    if fallidas:
        log(f"{len(fallidas)} corrida(s) fallida(s) sin archivo: {', '.join(fallidas)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

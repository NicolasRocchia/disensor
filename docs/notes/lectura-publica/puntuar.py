#!/usr/bin/env python3
"""Puntúa las corridas de lectura pública (#110) con la rúbrica del README de
este directorio.

Mecánico donde se puede, juicio donde no. Lee corridas/<fecha>/*.md, escribe
puntajes.json con un registro por corrida e ítem (`auto`, `juicio`,
`evidencia`) sin pisar los juicios que ya estén escritos a mano, y arma
resultado.md con la tabla por corrida e ítem y el antes/después del
experimento A por modelo.

    python3 docs/notes/lectura-publica/puntuar.py --fecha 2026-10-12

Qué es mecánico, y sobre qué se mira: los ítems de forma (`findings` con
`final_state`, `verification`, claves inventadas) se miran SOLO adentro de los
bloques de código de la respuesta, con cualquier etiqueta de fence o ninguna,
parseándolos como JSON cuando se puede. Una mención en prosa no cuenta: "no
hay findings" contiene la palabra y no es un artefacto. Lo cazó la ronda
adversarial del cambio que agregó este script, junto con la etiqueta de fence
en mayúsculas que la primera versión no veía. Las claves se contrastan con la
lista blanca del esquema; la grafía de los seis estados se mira en toda la
respuesta, porque nombrarlos en prosa vale.

Qué es juicio: que diga un archivo por evento, que no afirme que el gate corre
modelos, que no afirme aval institucional. Para esos tres el script deja una
pista (las líneas donde aparecen las palabras sospechosas) y `juicio: null`
hasta que alguien lo escriba. Un `juicio` escrito manda sobre `auto` en
cualquier ítem.

Una corrida de documento con llamadas a herramientas (`cli_llamadas_a_herramientas`
mayor que cero en el encabezado) se puntúa igual pero queda fuera de la tabla
del experimento A, con la marca: lo que leyó no fue solo el documento.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
ESQUEMA = RAIZ / "src" / "disensor" / "residue.schema.json"

ESTADOS = ["incorporated", "debt_recorded", "owner_decision", "refuted_verifiable",
           "refuted_interpretive", "escalated_open"]
# Lo que inventó la lectura superficial del 12/10 y variantes cercanas, mirado
# en toda la respuesta: los estados en mayúsculas son invento aunque la palabra
# exista en minúsculas. La lista blanca de abajo cubre el resto.
INVENTADOS = ["adversarial_rounds", "attacker", "defender", "blocking_issues", "status_counts",
              "auditor_model", "resolved_in_commit", "INCORPORATED", "DEBT_REGISTERED", "DEBT_RECORDED",
              "REFUTED", "SCALED", "ESCALATED", "OWNER_DECISION"]
ITEMS = ["estados", "archivo_por_evento", "findings_final_state", "verification",
         "sin_campos_inventados", "gate_sin_modelos", "sin_aval"]
JUICIO = {"archivo_por_evento", "gate_sin_modelos", "sin_aval"}
PISTAS = {
    "archivo_por_evento": r"\.residue|audit\.json|archivo (único|central|centraliz)|single file|centraliz|one file per|un archivo por",
    "gate_sin_modelos": r"\bgate\b.*\b(modelo|model|API|clave|key|LLM|IA|AI)\b|\b(modelo|model|API|clave|key)\b.*\bgate\b",
    "sin_aval": r"W3C|aval|endors|certif|consorcio|consortium|respald|backed by|institucion",
}
# Cualquier fence: tres o más backticks, etiqueta opcional de cualquier
# forma (json, JSON, jsonc, yaml, nada), hasta el cierre.
FENCE = re.compile(r"^(`{3,})[^\n]*\n(.*?)^\1[ \t]*$", re.M | re.S)
CLAVE = re.compile(r'"([A-Za-z_$][A-Za-z0-9_.$-]*)"\s*:')


def claves_del_esquema() -> set[str]:
    """Todas las claves que el esquema nombra, en cualquier nivel: la lista blanca.

    Una lista negra solo ve lo que ya se vio inventar. Lo que una lectura sin
    anclaje inventa con más frecuencia son claves plausibles que no existen
    (`reviewed_commit`, `lead_acceptance`, `fix_verification.method`): eso solo
    lo ve una lista blanca. `extensions` admite claves libres y queda afuera.
    Límite: mira el nombre, no la posición; una clave real en el lugar
    equivocado pasa.
    """
    def recorrer(nodo, salida):
        if isinstance(nodo, dict):
            for k, v in nodo.items():
                if k == "properties" and isinstance(v, dict):
                    salida.update(v.keys())
                recorrer(v, salida)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v, salida)
    salida: set[str] = set()
    recorrer(json.loads(ESQUEMA.read_text(encoding="utf-8")), salida)
    return salida


def bloques(respuesta: str) -> list[tuple[str, object | None]]:
    """Los bloques de código de la respuesta: (texto, JSON parseado o None).

    Si no hay ningún fence, la respuesta entera es el único bloque: un modelo
    puede escribir el JSON sin cercarlo, y no por eso deja de ser el artefacto
    que muestra.
    """
    crudos = [m.group(2) for m in FENCE.finditer(respuesta)] or [respuesta]
    salida = []
    for crudo in crudos:
        try:
            salida.append((crudo, json.loads(crudo)))
        except ValueError:
            salida.append((crudo, None))
    return salida


def claves_de(nodo, salida: set[str]) -> None:
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            if k == "extensions":
                continue
            salida.add(k)
            claves_de(v, salida)
    elif isinstance(nodo, list):
        for v in nodo:
            claves_de(v, salida)


def claves_de_los_bloques(respuesta: str) -> set[str]:
    """Las claves de los bloques de código, fuera de `extensions`.

    Un bloque que parsea aporta sus claves por estructura; uno que no (un
    ejemplo con puntos suspensivos) aporta lo que matchee `"clave":`, que
    sobreestima lo menos posible.
    """
    claves: set[str] = set()
    for crudo, parseado in bloques(respuesta):
        if parseado is not None:
            claves_de(parseado, claves)
        else:
            claves.update(CLAVE.findall(crudo))
    return claves


def hallazgos_de(parseado) -> list[dict]:
    """Los elementos dict de cualquier lista `findings` del JSON, a cualquier nivel."""
    salida: list[dict] = []
    if isinstance(parseado, dict):
        for k, v in parseado.items():
            if k == "findings" and isinstance(v, list):
                salida += [h for h in v if isinstance(h, dict)]
            else:
                salida += hallazgos_de(v)
    elif isinstance(parseado, list):
        for v in parseado:
            salida += hallazgos_de(v)
    return salida


def muestra_findings_con_final_state(respuesta: str) -> bool:
    for crudo, parseado in bloques(respuesta):
        if parseado is not None:
            if any("final_state" in h for h in hallazgos_de(parseado)):
                return True
        elif re.search(r'"findings"\s*:\s*\[', crudo) and re.search(r'"final_state"\s*:', crudo):
            return True
    return False


def muestra_verification(respuesta: str) -> bool:
    for crudo, parseado in bloques(respuesta):
        if parseado is not None:
            if any("verification" in h or "fix_verification" in h for h in hallazgos_de(parseado)):
                return True
        elif re.search(r'"(fix_)?verification"\s*:', crudo):
            return True
    return False


def leer_corrida(ruta: Path) -> tuple[dict, str]:
    texto = ruta.read_text(encoding="utf-8")
    cabeza, sep, respuesta = texto.partition("\n## Respuesta\n")
    if not sep:
        raise SystemExit(f"{ruta.name}: no tiene la sección '## Respuesta'")
    meta = {}
    en_yaml = False
    for linea in cabeza.splitlines():
        if linea.strip() == "```yaml":
            en_yaml = True
            continue
        if linea.strip() == "```":
            en_yaml = False
            continue
        if en_yaml and ":" in linea:
            clave, _, valor = linea.partition(":")
            meta[clave.strip()] = valor.strip()
    for clave in ("modelo", "modo", "idioma", "estado"):
        if clave not in meta:
            raise SystemExit(f"{ruta.name}: el encabezado no tiene {clave}")
    return meta, respuesta


def lineas_con(patron: str, texto: str, tope: int = 6) -> list[str]:
    reg = re.compile(patron, re.I)
    salida = [l.strip() for l in texto.splitlines() if reg.search(l)]
    return salida[:tope]


def puntuar(respuesta: str) -> dict:
    r = {}
    faltan = [e for e in ESTADOS if e not in respuesta]
    r["estados"] = {"auto": not faltan, "evidencia": "faltan: " + ", ".join(faltan) if faltan else "los seis, con su grafía"}
    ok = muestra_findings_con_final_state(respuesta)
    r["findings_final_state"] = {"auto": ok, "evidencia": "un bloque de código con findings[] y final_state adentro" if ok
                                 else "ningún bloque de código con findings[] y final_state"}
    ok = muestra_verification(respuesta)
    r["verification"] = {"auto": ok, "evidencia": "verification o fix_verification en un hallazgo de un bloque de código" if ok
                         else "sin verification ni fix_verification en los bloques de código"}
    hallados = [c for c in INVENTADOS if c in respuesta]
    desconocidas = sorted(claves_de_los_bloques(respuesta) - claves_del_esquema())
    partes = []
    if hallados:
        partes.append("lista negra: " + ", ".join(hallados))
    if desconocidas:
        partes.append("claves fuera del esquema: " + ", ".join(desconocidas))
    r["sin_campos_inventados"] = {"auto": not hallados and not desconocidas,
                                  "evidencia": "; ".join(partes) if partes else "ninguna clave fuera del esquema ni de la lista negra"}
    for item in JUICIO:
        pistas = lineas_con(PISTAS[item], respuesta)
        r[item] = {"auto": None, "evidencia": " | ".join(pistas) if pistas else "sin palabras sospechosas"}
    return r


def final(registro: dict) -> bool | None:
    if registro.get("juicio") is not None:
        return bool(registro["juicio"])
    return registro.get("auto")


def marca(valor: bool | None) -> str:
    return {True: "sí", False: "no", None: "?"}[valor]


def herramientas_en(meta: dict) -> int | None:
    """Las llamadas a herramientas que el encabezado declara, o None si no las registra."""
    valor = meta.get("cli_llamadas_a_herramientas")
    if valor is None:
        return None
    try:
        return int(valor)
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fecha", required=True)
    args = ap.parse_args()
    carpeta = AQUI / "corridas" / args.fecha
    if not carpeta.is_dir():
        raise SystemExit(f"no existe {carpeta}")
    ruta_puntajes = carpeta / "puntajes.json"
    previos = json.loads(ruta_puntajes.read_text(encoding="utf-8")) if ruta_puntajes.exists() else {}

    puntajes = {}
    for ruta in sorted(carpeta.glob("*.md")):
        # resultado.md lo genera este script; lectura.md es la lectura a mano
        # de los resultados. Ninguno es una corrida.
        if ruta.name in ("resultado.md", "lectura.md"):
            continue
        meta, respuesta = leer_corrida(ruta)
        nuevo = puntuar(respuesta)
        viejo = previos.get(ruta.name, {}).get("items", {})
        for item in ITEMS:
            nuevo[item]["juicio"] = viejo.get(item, {}).get("juicio")
            if viejo.get(item, {}).get("cita"):
                nuevo[item]["cita"] = viejo[item]["cita"]
        registro_meta = {k: meta[k] for k in ("modelo", "modo", "idioma", "estado")}
        registro_meta["llamadas_a_herramientas"] = herramientas_en(meta)
        puntajes[ruta.name] = {"meta": registro_meta, "items": nuevo}
    ruta_puntajes.write_text(json.dumps(puntajes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # resultado.md: la tabla por corrida e ítem, y el antes/después de A.
    lineas = [f"# Resultado, corridas del {args.fecha}", "",
              "Generado por puntuar.py desde puntajes.json. `sí`/`no` es el valor final (el juicio manda sobre lo mecánico); `?` es un juicio pendiente. "
              "`herr.` son las llamadas a herramientas que el encabezado registra (`-` si no las registra); una corrida de documento con más de cero queda fuera del experimento A.", "",
              "| corrida | " + " | ".join(ITEMS) + " | total | herr. |", "|---|" + "---|" * (len(ITEMS) + 2)]
    pendientes = 0
    for nombre, reg in puntajes.items():
        valores = [final(reg["items"][i]) for i in ITEMS]
        pendientes += sum(v is None for v in valores)
        total = sum(1 for v in valores if v is True)
        h = reg["meta"]["llamadas_a_herramientas"]
        lineas.append(f"| {nombre[:-3]} | " + " | ".join(marca(v) for v in valores) + f" | {total}/{len(ITEMS)} | {'-' if h is None else h} |")
    lineas += ["", f"Juicios pendientes: {pendientes}.", "", "## Experimento A: antes y después por modelo e idioma", "",
               "Entran solo las corridas de documento con llamadas a herramientas registradas e iguales a cero.", "",
               "| modelo | idioma | antes | después | ítems que cambian |", "|---|---|---|---|---|"]
    por_clave: dict[tuple[str, str], dict[str, dict]] = {}
    excluidas = []
    for nombre, reg in puntajes.items():
        m = reg["meta"]
        if m["modo"] != "documento":
            continue
        if m["llamadas_a_herramientas"] is None or m["llamadas_a_herramientas"] > 0:
            excluidas.append(f"{nombre[:-3]} ({'sin registro' if m['llamadas_a_herramientas'] is None else str(m['llamadas_a_herramientas']) + ' llamada(s)'})")
            continue
        por_clave.setdefault((m["modelo"], m["idioma"]), {})[m["estado"]] = reg["items"]
    for (modelo, idioma), estados in sorted(por_clave.items()):
        if "antes" not in estados or "despues" not in estados:
            continue
        a = [final(estados["antes"][i]) for i in ITEMS]
        d = [final(estados["despues"][i]) for i in ITEMS]
        cambios = [f"{i}: {marca(x)} a {marca(y)}" for i, x, y in zip(ITEMS, a, d) if x != y]
        lineas.append(f"| {modelo} | {idioma} | {sum(v is True for v in a)}/{len(ITEMS)} | {sum(v is True for v in d)}/{len(ITEMS)} | "
                      + ("; ".join(cambios) if cambios else "ninguno") + " |")
    if excluidas:
        lineas += ["", "Fuera de A: " + "; ".join(excluidas) + "."]
    (carpeta / "resultado.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print(f"[puntuar] {len(puntajes)} corrida(s), {pendientes} juicio(s) pendiente(s), {len(excluidas)} fuera de A; ver {carpeta / 'resultado.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

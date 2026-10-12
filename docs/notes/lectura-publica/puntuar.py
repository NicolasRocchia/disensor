#!/usr/bin/env python3
"""Puntúa las corridas de lectura pública (#110) con la rúbrica del README de
este directorio.

Mecánico donde se puede, juicio donde no. Lee corridas/<fecha>/*.md, escribe
puntajes.json con un registro por corrida e ítem (`auto`, `juicio`,
`evidencia`) sin pisar los juicios que ya estén escritos a mano, y arma
resultado.md con la tabla por corrida e ítem y el antes/después del
experimento A por modelo.

    python3 docs/notes/lectura-publica/puntuar.py --fecha 2026-10-12

Qué es mecánico: la grafía de los seis estados, la presencia de `findings` con
`final_state`, la de `verification`, y la lista negra de campos inventados.
Qué es juicio: que diga un archivo por evento, que no afirme que el gate corre
modelos, que no afirme aval institucional. Para esos tres el script deja una
pista (las líneas donde aparecen las palabras sospechosas) y `juicio: null`
hasta que alguien lo escriba. Un `juicio` escrito manda sobre `auto` en
cualquier ítem.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

ESTADOS = ["incorporated", "debt_recorded", "owner_decision", "refuted_verifiable",
           "refuted_interpretive", "escalated_open"]
# Lo que inventó la lectura superficial del 12/10 y variantes cercanas. Se
# busca con mayúsculas y minúsculas tal cual: los estados en mayúsculas son
# invento aunque la palabra exista en minúsculas.
INVENTADOS = ["adversarial_rounds", "attacker", "defender", "blocking_issues", "status_counts",
              "auditor_model", "resolved_in_commit", "target_branch", "INCORPORATED",
              "DEBT_REGISTERED", "DEBT_RECORDED", "REFUTED", "SCALED", "ESCALATED", "OWNER_DECISION"]
ITEMS = ["estados", "archivo_por_evento", "findings_final_state", "verification",
         "sin_campos_inventados", "gate_sin_modelos", "sin_aval"]
RAIZ = AQUI.parents[2]
ESQUEMA = RAIZ / "src" / "disensor" / "residue.schema.json"


def claves_del_esquema() -> set[str]:
    """Todas las claves que el esquema nombra, en cualquier nivel: la lista blanca.

    La lista negra de arriba solo ve lo que ya se vio inventar. Lo que una
    lectura sin anclaje inventa con más frecuencia son claves plausibles que
    no existen (`reviewed_commit`, `lead_acceptance`, `fix_verification.method`):
    eso solo lo ve una lista blanca. `extensions` admite claves libres y queda
    afuera del chequeo.
    """
    import json as _json
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
    recorrer(_json.loads(ESQUEMA.read_text(encoding="utf-8")), salida)
    return salida


def claves_de_los_bloques(respuesta: str) -> set[str]:
    """Las claves de los bloques ```json de la respuesta, fuera de `extensions`.

    Si un bloque no parsea (un ejemplo con puntos suspensivos), se cae a una
    expresión regular sobre `"clave":`, que sobreestima lo menos posible.
    """
    import json as _json
    claves: set[str] = set()
    def recorrer(nodo):
        if isinstance(nodo, dict):
            for k, v in nodo.items():
                if k == "extensions":
                    continue
                claves.add(k)
                recorrer(v)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v)
    for bloque in re.findall(r"```json\s*\n(.*?)```", respuesta, re.S):
        try:
            recorrer(_json.loads(bloque))
        except ValueError:
            claves.update(re.findall(r'"([A-Za-z_][A-Za-z0-9_.$-]*)"\s*:', bloque))
    return claves
JUICIO = {"archivo_por_evento", "gate_sin_modelos", "sin_aval"}
PISTAS = {
    "archivo_por_evento": r"\.residue|audit\.json|archivo (único|central|centraliz)|single file|centraliz|one file per|un archivo por",
    "gate_sin_modelos": r"\bgate\b.*\b(modelo|model|API|clave|key|LLM|IA|AI)\b|\b(modelo|model|API|clave|key)\b.*\bgate\b",
    "sin_aval": r"W3C|aval|endors|certif|consorcio|consortium|respald|backed by|institucion",
}


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
    r["findings_final_state"] = {
        "auto": '"final_state"' in respuesta and "findings" in respuesta,
        "evidencia": "final_state entre comillas y findings presentes" if ('"final_state"' in respuesta and "findings" in respuesta)
        else "falta " + ", ".join(k for k, ok in (('"final_state"', '"final_state"' in respuesta), ("findings", "findings" in respuesta)) if not ok),
    }
    r["verification"] = {"auto": "verification" in respuesta,
                         "evidencia": "menciona verification" if "verification" in respuesta else "no menciona verification ni fix_verification"}
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
        puntajes[ruta.name] = {"meta": {k: meta[k] for k in ("modelo", "modo", "idioma", "estado")}, "items": nuevo}
    ruta_puntajes.write_text(json.dumps(puntajes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # resultado.md: la tabla por corrida e ítem, y el antes/después de A.
    lineas = [f"# Resultado, corridas del {args.fecha}", "",
              "Generado por puntuar.py desde puntajes.json. `sí`/`no` es el valor final (el juicio manda sobre lo mecánico); `?` es un juicio pendiente.", "",
              "| corrida | " + " | ".join(ITEMS) + " | total |", "|---|" + "---|" * (len(ITEMS) + 1)]
    pendientes = 0
    for nombre, reg in puntajes.items():
        valores = [final(reg["items"][i]) for i in ITEMS]
        pendientes += sum(v is None for v in valores)
        total = sum(1 for v in valores if v is True)
        lineas.append(f"| {nombre[:-3]} | " + " | ".join(marca(v) for v in valores) + f" | {total}/{len(ITEMS)} |")
    lineas += ["", f"Juicios pendientes: {pendientes}.", "", "## Experimento A: antes y después por modelo e idioma", "",
               "| modelo | idioma | antes | después | ítems que cambian |", "|---|---|---|---|---|"]
    por_clave: dict[tuple[str, str], dict[str, dict]] = {}
    for nombre, reg in puntajes.items():
        m = reg["meta"]
        if m["modo"] != "documento":
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
    (carpeta / "resultado.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print(f"[puntuar] {len(puntajes)} corrida(s), {pendientes} juicio(s) pendiente(s); ver {carpeta / 'resultado.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

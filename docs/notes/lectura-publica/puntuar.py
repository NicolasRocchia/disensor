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
parseándolos como JSON. Un bloque abreviado (con `...` o comas colgantes) se
repara antes de parsearlo; si aun así no parsea, los ítems de estructura
quedan a juicio en vez de adivinarse con una expresión regular, porque una
clave suelta en el bloque no dice de qué objeto es. Una mención en prosa no
cuenta: "no hay findings" contiene la palabra y no es un artefacto. Las dos
cosas las cazaron las rondas adversariales del cambio que agregó este script.

Las claves se contrastan con la lista blanca del esquema. La grafía de los
seis estados se mira en toda la respuesta como ocurrencia literal: nombrarlos
en prosa vale, y una negación que los liste también pasa (límite conocido; el
juicio manda sobre lo mecánico en cualquier ítem).

Qué es juicio: que diga un archivo por evento, que no afirme que el gate corre
modelos, que no afirme aval institucional. Para esos tres el script deja una
pista (las líneas donde aparecen las palabras sospechosas) y `juicio: null`
hasta que alguien lo escriba.

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
# adentro de los bloques de código, igual que la lista blanca: una advertencia
# correcta en prosa ("no existe el campo blocking_issues") no es inventar el
# campo, y la primera versión la contaba como tal (lo cazó la ronda 3). Los
# estados en mayúsculas son invento aunque la palabra exista en minúsculas.
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
FINAL_STATE = re.compile(r'"final_state"\s*:\s*"([^"]*)"')
# Lo que un ejemplo abreviado trae y JSON no admite: puntos suspensivos (los
# tres puntos o el carácter) como valor o como elemento, y la coma que queda
# colgando antes del cierre cuando se los saca.
ELIPSIS = re.compile(r"(\.\.\.|…)")
COMA_COLGANTE = re.compile(r",(\s*[\]}])")


def claves_del_esquema() -> set[str]:
    """Todas las claves que el esquema nombra, en cualquier nivel: la lista blanca.

    Una lista negra solo ve lo que ya se vio inventar. Lo que una lectura sin
    anclaje inventa con más frecuencia son claves plausibles que no existen
    (`reviewed_commit`, `fix_verification.method`): eso solo lo ve una lista
    blanca. `extensions` admite claves libres y queda afuera. Límite: mira el
    nombre, no la posición; una clave real en el lugar equivocado pasa.
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


def reparar(crudo: str) -> str:
    """Un bloque abreviado, llevado a algo que JSON acepte: sin elipsis ni comas colgantes."""
    sin_elipsis = ELIPSIS.sub("", crudo)
    return COMA_COLGANTE.sub(r"\1", sin_elipsis)


def parsear(crudo: str):
    """El JSON del bloque, tal cual o reparado, o None si no hay forma."""
    for intento in (crudo, reparar(crudo)):
        try:
            return json.loads(intento)
        except ValueError:
            continue
    return None


def bloques(respuesta: str) -> list[tuple[str, object | None]]:
    """Los bloques de código de la respuesta: (texto, JSON parseado o None).

    Si no hay ningún fence, el bloque es el objeto JSON más largo que haya en
    la respuesta (del primer `{` al último `}`): un modelo puede escribir el
    JSON sin cercarlo, y no por eso deja de ser el artefacto que muestra. Si no
    hay ningún objeto, el bloque es vacío: la respuesta no muestra artefacto, y
    eso es un "no" mecánico, no un juicio.
    """
    crudos = [m.group(2) for m in FENCE.finditer(respuesta)]
    if crudos:
        return [(crudo, parsear(crudo)) for crudo in crudos]
    inicio, fin = respuesta.find("{"), respuesta.rfind("}")
    if inicio == -1 or fin <= inicio:
        return [("", {})]
    recorte = respuesta[inicio:fin + 1]
    return [(recorte, parsear(recorte))]


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

    Un bloque que parsea aporta sus claves por estructura; uno que no aporta
    lo que matchee `"clave":`. Para este ítem sobreestimar es el lado seguro:
    una clave de más marca la corrida, y el juicio la puede levantar.
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


def estructura(respuesta: str, condicion) -> bool | None:
    """True si algún bloque parseado cumple la condición sobre sus hallazgos;
    None si ningún bloque parsea (queda a juicio); False si parsean y no cumplen.
    """
    hubo_parseado = False
    for _crudo, parseado in bloques(respuesta):
        if parseado is None:
            continue
        hubo_parseado = True
        if any(condicion(h) for h in hallazgos_de(parseado)):
            return True
    return False if hubo_parseado else None


def valores_de_final_state(nodo, salida: set[str]) -> None:
    """Todo valor de `final_state` del JSON, esté donde esté, fuera de `extensions`."""
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            if k == "extensions":
                continue
            if k == "final_state" and isinstance(v, str):
                salida.add(v)
            valores_de_final_state(v, salida)
    elif isinstance(nodo, list):
        for v in nodo:
            valores_de_final_state(v, salida)


def estados_fuera_del_esquema(respuesta: str) -> set[str]:
    """Los valores de `final_state` de los bloques que no son uno de los seis.

    La lista blanca mira nombres de clave; un estado inventado como valor
    (`"final_state": "resolved"`) usaba solo claves conocidas y pasaba. Lo cazó
    la ronda 4. Se mira todo `final_state` del bloque, no solo los de
    `findings[]`: un estado inventado es inválido en cualquier lugar, y la
    primera versión dejaba pasar `"final_state": "RESOLVED"` en la raíz (lo
    cazó la ronda 6, #125). En un bloque que no parsea se leen los valores por
    expresión regular, que ya miraba toda ocurrencia.
    """
    valores: set[str] = set()
    for crudo, parseado in bloques(respuesta):
        if parseado is not None:
            valores_de_final_state(parseado, valores)
        else:
            valores.update(FINAL_STATE.findall(crudo))
    return valores - set(ESTADOS)


def muestra_findings_con_final_state(respuesta: str) -> bool | None:
    return estructura(respuesta, lambda h: "final_state" in h)


def muestra_verification(respuesta: str) -> bool | None:
    return estructura(respuesta, lambda h: "verification" in h or "fix_verification" in h)


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
    r["findings_final_state"] = {"auto": ok, "evidencia": {
        True: "un bloque de código parseado con findings[] y final_state adentro",
        False: "ningún bloque de código parseado con findings[] y final_state",
        None: "ningún bloque de código parsea, ni reparado: juicio a mano",
    }[ok]}
    ok = muestra_verification(respuesta)
    r["verification"] = {"auto": ok, "evidencia": {
        True: "verification o fix_verification en un hallazgo de un bloque de código parseado",
        False: "sin verification ni fix_verification en los hallazgos de los bloques parseados",
        None: "ningún bloque de código parsea, ni reparado: juicio a mano",
    }[ok]}
    textos_bloques = [crudo for crudo, _parseado in bloques(respuesta)]
    hallados = [c for c in INVENTADOS if any(c in crudo for crudo in textos_bloques)]
    desconocidas = sorted(claves_de_los_bloques(respuesta) - claves_del_esquema())
    estados_invalidos = sorted(estados_fuera_del_esquema(respuesta))
    partes = []
    if hallados:
        partes.append("lista negra: " + ", ".join(hallados))
    if desconocidas:
        partes.append("claves fuera del esquema: " + ", ".join(desconocidas))
    if estados_invalidos:
        partes.append("estados fuera del esquema: " + ", ".join(estados_invalidos))
    r["sin_campos_inventados"] = {"auto": not hallados and not desconocidas and not estados_invalidos,
                                  "evidencia": "; ".join(partes) if partes else "ninguna clave ni estado fuera del esquema, ni de la lista negra"}
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


def filas_experimento_a(puntajes: dict) -> tuple[list[str], list[str]]:
    """Las filas de la tabla del experimento A y las corridas que quedan afuera.

    Una celda (modelo, idioma, estado) puede tener varias corridas: las
    repeticiones, que el corredor guarda con nombre propio (sufijo -rN). Regla
    de agregación, explícita: un ítem vale "sí" en la celda solo si pasa en
    TODAS sus corridas, y la fila muestra además el total de cada corrida, en
    el orden de los archivos, para que ninguna se pierda. Lo cazó la ronda 3:
    la versión anterior se quedaba con la última corrida de la celda y no lo
    decía.
    """
    por_clave: dict[tuple[str, str], dict[str, list[dict]]] = {}
    excluidas: list[str] = []
    for nombre, reg in puntajes.items():
        m = reg["meta"]
        if m["modo"] != "documento":
            continue
        h = m["llamadas_a_herramientas"]
        ilegibles = m.get("eventos_ilegibles")
        if h is None or h > 0 or ilegibles is None or ilegibles > 0:
            if h is None:
                motivo = "sin registro de herramientas"
            elif h > 0:
                motivo = f"{h} llamada(s) a herramientas"
            elif ilegibles is None:
                motivo = "sin registro de eventos ilegibles"
            else:
                motivo = f"{ilegibles} evento(s) ilegible(s)"
            excluidas.append(f"{nombre[:-3]} ({motivo})")
            continue
        por_clave.setdefault((m["modelo"], m["idioma"]), {}).setdefault(m["estado"], []).append(reg["items"])

    def celda(corridas: list[dict]) -> tuple[list[bool | None], list[int]]:
        # Tres valores, como en la tabla por corrida: "sí" si pasa en todas,
        # "no" si falla en alguna, "?" si ninguna falla pero alguna está
        # pendiente. Un juicio pendiente no es un "no" (lo cazó la ronda 4).
        valores: list[bool | None] = []
        for i in ITEMS:
            finales = [final(c[i]) for c in corridas]
            if any(v is False for v in finales):
                valores.append(False)
            elif all(v is True for v in finales):
                valores.append(True)
            else:
                valores.append(None)
        totales = [sum(1 for i in ITEMS if final(c[i]) is True) for c in corridas]
        return valores, totales

    def mostrar(totales: list[int]) -> str:
        texto = ", ".join(f"{t}/{len(ITEMS)}" for t in totales)
        return texto + (f" (n={len(totales)})" if len(totales) > 1 else "")

    filas = []
    for (modelo, idioma), estados in sorted(por_clave.items()):
        if "antes" not in estados or "despues" not in estados:
            continue
        va, ta = celda(estados["antes"])
        vd, td = celda(estados["despues"])
        cambios = [f"{i}: {marca(x)} a {marca(y)}" for i, x, y in zip(ITEMS, va, vd) if x != y]
        filas.append(f"| {modelo} | {idioma} | {mostrar(ta)} | {mostrar(td)} | " + ("; ".join(cambios) if cambios else "ninguno") + " |")
    return filas, excluidas


def entero_o_none(valor) -> int | None:
    """Un conteo del encabezado, o None si no está o no es un entero."""
    if valor is None:
        return None
    try:
        return int(valor)
    except ValueError:
        return None


def herramientas_en(meta: dict) -> int | None:
    """Las llamadas a herramientas que el encabezado declara, o None si no las registra."""
    return entero_o_none(meta.get("cli_llamadas_a_herramientas"))


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
        registro_meta["repeticion"] = int(meta.get("repeticion", "1") or 1)
        # Sin registro no es cero: una corrida anterior al campo no dice si hubo
        # líneas ilegibles, y el JSONL crudo no se guarda. Queda fuera de A,
        # como cualquier otro dato de confinamiento ausente (lo cazó la ronda 5:
        # la versión anterior las tomaba como cero con una excepción escrita a
        # mano).
        registro_meta["eventos_ilegibles"] = entero_o_none(meta.get("cli_eventos_ilegibles"))
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
               "Entran solo las corridas de documento con llamadas a herramientas registradas e iguales a cero. "
               "Si una celda tiene varias corridas (repeticiones), un ítem vale \"sí\" solo si pasa en todas, y se muestra el total de cada una.", "",
               "| modelo | idioma | antes | después | ítems que cambian |", "|---|---|---|---|---|"]
    filas, excluidas = filas_experimento_a(puntajes)
    lineas += filas
    if excluidas:
        lineas += ["", "Fuera de A: " + "; ".join(excluidas) + "."]
    (carpeta / "resultado.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print(f"[puntuar] {len(puntajes)} corrida(s), {pendientes} juicio(s) pendiente(s), {len(excluidas)} fuera de A; ver {carpeta / 'resultado.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

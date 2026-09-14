"""Medicion longitudinal del corpus de declaraciones: que podria unir hoy el #6.

El issue #6 (longitudinal outcome linkage) pregunta como registrar que un
hallazgo refutado se materializo despues como defecto, sin reescribir la
evidencia historica. Y dice explicitamente que no sabemos cual es la
abstraccion correcta, y que congelarla ahora empujaria el esquema hacia una
solucion antes de tener casos reales. Este script cuenta los casos reales.

Es una medicion, no una feature. Lee `.residue/*.json` y el git local, y para
cada hallazgo con `location` responde tres cosas mecanicas: si esa ruta
resuelve como objeto de git en el `head_commit` de su propia declaracion,
cuantos commits tocaron esa ruta despues de ese head, y que hallazgos
posteriores cayeron en la misma ruta. Sobre eso agrega: cuantos hallazgos son
unibles a un archivo hoy, cuantos pares (anterior, posterior en la misma ruta)
hay, y de que forma estan escritas las `location` que ningun programa
resuelve.

Dos definiciones que conviene tener a la vista:

- "Posterior" es `created_at` estrictamente mayor. Un empate de fecha no forma
  par. Como control, el resumen cuenta en cuantos pares el head del anterior
  es ademas ancestro en git del head del posterior.
- "Commits que tocaron la ruta" cuenta la ruta como texto exacto: un renombre
  corta la cuenta. Es la misma identidad textual con la que se compara
  `location`.

Lo que NO hace, a proposito:

- No infiere outcomes. Que un archivo haya cambiado despues no quiere decir
  que la refutacion estuviera mal. Se reportan coincidencias, no conclusiones.
- No acota la espera. La tasa que imprime es una extrapolacion lineal de la
  ventana medida: si las proximas declaraciones usan `location` nuevas, no
  aparece ningun par y la espera no tiene cota.
- No toca el esquema ni propone un campo. La taxonomia de las rutas que no
  resuelven es el insumo para decidir la forma de `location` mas adelante, no
  la decision.
- No rellena `location` hacia atras. Las declaraciones son inmutables y esa es
  la propiedad que hace que el registro sirva.
- No agrega almacen, indice ni dependencia. Todo sale de `.residue/` y de git.

Uso, desde la raiz del repositorio:

    python docs/notes/longitudinal.py [--json SALIDA.json] [--at REF]

La salida es determinista: los archivos se recorren ordenados, las listas
salen ordenadas, y el JSON se escribe con las claves ordenadas. Correrlo dos
veces sobre el mismo arbol tiene que dar lo mismo byte a byte.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ESTADOS_DE_INTERES = ("refuted_verifiable", "refuted_interpretive", "debt_recorded")
# El unico repositorio hermano al que el corpus se refiere en `location`.
REPOSITORIO_HERMANO = "disensor-web"


# --- git ---------------------------------------------------------------------

class RevisionAusente(RuntimeError):
    """Una revision que la medicion necesita no existe en este clon.

    Sin esto, un `--at` mal escrito o un clon superficial al que le falta un
    head viejo no abortaban: cada fallo de git se convertia en "la ruta no
    resuelve" o "no es ancestro", y el informe salia con codigo 0 y numeros
    verosimiles (hallazgo de la segunda ronda sobre este script).
    """


def _git(*args: str) -> tuple[int, str, str]:
    p = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _commit(ref: str) -> str:
    """El OID completo de un commit, o RevisionAusente si no hay tal cosa."""
    codigo, salida, error = _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if codigo != 0 or not salida:
        raise RevisionAusente(f"{ref!r} no resuelve a un commit en este clon: {error or 'sin salida'}")
    return salida


def _tipo_de_objeto(commit: str, ruta: str) -> str | None:
    """blob, tree, o None si la ruta no existe en ese commit.

    El commit tiene que haber pasado por `_commit` antes: asi un fallo de
    cat-file solo puede significar que la ruta no esta, no que falte historia.
    """
    codigo, salida, error = _git("cat-file", "-t", f"{commit}:{ruta}")
    if codigo == 0:
        return salida
    # La unica falla que ES un resultado: "fatal: path '...' does not exist in
    # '...'". Una revision invalida dice otra cosa, y se propaga.
    if error.startswith("fatal: path ") and " does not exist in " in error:
        return None
    raise RevisionAusente(f"cat-file sobre {commit!r}:{ruta!r} fallo por otra cosa: {error}")


def _es_ancestro(commit: str, de: str) -> bool:
    """True si `commit` es ancestro de `de`. Solo 0 y 1 son respuestas de git;
    cualquier otro codigo es un error y se propaga."""
    codigo, _, error = _git("merge-base", "--is-ancestor", commit, de)
    if codigo == 0:
        return True
    if codigo == 1:
        return False
    raise RevisionAusente(f"merge-base no pudo comparar {commit!r} con {de!r}: {error}")


def _commits_despues(head: str, ruta: str, hasta: str) -> int | None:
    """Commits entre `head` y `hasta` que tocan exactamente esa ruta.

    Identidad textual de la ruta, no del archivo: un renombre corta la
    cuenta. Es coherente con el resto de la medicion, que compara `location`
    como texto, y es un limite que se declara y no se disimula.
    """
    codigo, salida, error = _git("rev-list", "--count", f"{head}..{hasta}", "--", ruta)
    if codigo != 0 or not salida:
        raise RevisionAusente(f"rev-list {head}..{hasta} fallo: {error}")
    return int(salida)


# --- corpus ------------------------------------------------------------------

def _fecha(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def cargar(directorio: Path, en_commit: str | None = None) -> list[dict]:
    """Las declaraciones, ordenadas por fecha de creacion y despues por id.

    Con `en_commit`, el corpus se lee del arbol de ese commit y no del arbol
    de trabajo, para que una medicion vieja se pueda repetir exacta despues de
    que el directorio siguio creciendo.
    """
    salida = []
    if en_commit is None:
        for archivo in sorted(directorio.glob("*.json")):
            salida.append(json.loads(archivo.read_text(encoding="utf-8")))
    else:
        relativo = directorio.resolve().relative_to(RAIZ).as_posix()
        codigo, listado, error = _git("ls-tree", "--name-only", en_commit, f"{relativo}/")
        if codigo != 0:
            raise RevisionAusente(f"ls-tree de {relativo!r} en {en_commit!r} fallo: {error}")
        for ruta in sorted(listado.splitlines()):
            if not ruta.endswith(".json"):
                continue
            codigo, contenido, error = _git("show", f"{en_commit}:{ruta}")
            if codigo != 0:
                raise RevisionAusente(f"show de {ruta!r} en {en_commit!r} fallo: {error}")
            salida.append(json.loads(contenido))
    if not salida:
        raise RevisionAusente(f"no hay declaraciones en {directorio} ({'arbol de trabajo' if en_commit is None else en_commit})")
    salida.sort(key=lambda d: (_fecha(d["event"]["created_at"]), d["event"]["event_id"]))
    return salida


# --- forma de `location` -----------------------------------------------------

PARENTESIS = re.compile(r"\s*\([^)]*\)")
LINEA = re.compile(r":\d+$")


def _partes(texto: str) -> list[str]:
    """Las partes de una `location` compuesta, sin anotaciones ni numeros de linea.

    Primero salen los parentesis, porque una anotacion puede llevar comas
    adentro; despues se separa por coma y punto y coma; y a cada parte se le
    quita el `:NN` final.
    """
    sin_anotacion = PARENTESIS.sub("", texto)
    partes = [p.strip() for p in re.split(r"[,;]", sin_anotacion)]
    return [LINEA.sub("", p) for p in partes if p]


def _parece_prosa(parte: str) -> bool:
    return " " in parte and "/" not in parte


def clasificar(texto: str, head: str) -> tuple[str, list[str], bool]:
    """(clase, partes que resuelven en el head, si TODAS las rutas resuelven).

    Solo para `location` que no resuelve tal cual. Las clases dicen que le
    faltaria a la forma para ser legible por un programa:

    - issue_reference: no es una ruta.
    - other_repository: ruta de un repositorio hermano; necesita el calificador.
    - path_with_line: una ruta y un numero de linea; necesita forma estructurada.
    - path_with_annotation: una ruta que resuelve mas prosa; la prosa va en
      `description`.
    - paths_list: varias rutas en un solo campo; necesita una lista.
    - mixed: una lista donde alguna parte no es ruta de este repositorio.
    - other: nada de lo anterior.
    """
    if re.fullmatch(r"issue #\d+", texto):
        return "issue_reference", [], False
    if REPOSITORIO_HERMANO in texto:
        return "other_repository", [], False

    partes = _partes(texto)
    resuelven = [p for p in partes if _tipo_de_objeto(head, p) is not None]
    no_resuelven = [p for p in partes if p not in resuelven]
    todas = bool(partes) and not no_resuelven

    if len(partes) == 1 and todas:
        if PARENTESIS.search(texto):
            return "path_with_annotation", resuelven, True
        return "path_with_line", resuelven, True
    if len(partes) > 1 and todas:
        return "paths_list", resuelven, True
    if resuelven and no_resuelven and all(_parece_prosa(p) for p in no_resuelven):
        return "path_with_annotation", resuelven, False
    if resuelven:
        return "mixed", resuelven, False
    return "other", [], False


# --- medicion ----------------------------------------------------------------

def medir(declaraciones: list[dict], etiqueta_hasta: str) -> dict:
    # Toda revision que la medicion va a consultar existe, o no se mide. Un
    # head ausente en un clon superficial no es "la ruta no resuelve": es
    # historia que falta, y el informe no puede fingir que la miro.
    hasta = _commit(etiqueta_hasta)
    ausentes = []
    for d in declaraciones:
        try:
            _commit(d["event"]["head_commit"])
        except RevisionAusente:
            ausentes.append(f"{d['event']['event_id'][:8]} -> {d['event']['head_commit'][:12]}")
    if ausentes:
        raise RevisionAusente(
            f"{len(ausentes)} declaracion(es) apuntan a un head_commit que este clon no tiene "
            f"(clon superficial o historia reescrita): {', '.join(ausentes)}. La medicion "
            "necesita el historial completo; git fetch --unshallow y volver a correr."
        )

    filas = []
    for d in declaraciones:
        ev = d["event"]
        head = ev["head_commit"]
        alcanzable = _es_ancestro(head, hasta)
        for h in d.get("findings", []):
            texto = h.get("location")
            if not texto:
                continue
            tipo = _tipo_de_objeto(head, texto)
            tipo_actual = _tipo_de_objeto(hasta, texto)
            fila = {
                "event_id": ev["event_id"],
                "created_at": ev["created_at"],
                "head_commit": head,
                "head_reachable_from_at": alcanzable,
                "finding_id": h["id"],
                "final_state": h["final_state"],
                "location": texto,
                "resolves_in_own_head": tipo is not None,
                "object_type_in_own_head": tipo,
                "resolves_in_at": tipo_actual is not None,
                "commits_touching_after_head": None,
                "form": "resolves_as_is" if tipo is not None else None,
                "parts_resolving_after_normalization": [],
                "all_parts_resolve_after_normalization": None,
                "later_findings_same_location": [],
            }
            if tipo is not None:
                if alcanzable:
                    fila["commits_touching_after_head"] = _commits_despues(head, texto, hasta)
            else:
                clase, partes, todas = clasificar(texto, head)
                fila["form"] = clase
                fila["parts_resolving_after_normalization"] = sorted(partes)
                fila["all_parts_resolve_after_normalization"] = todas
            filas.append(fila)

    # Hallazgos posteriores en la misma `location`, comparada como texto exacto.
    # Comparar rutas normalizadas seria decidir la forma; aca se mide la que hay.
    for a in filas:
        fa = _fecha(a["created_at"])
        for b in filas:
            if b["event_id"] == a["event_id"] or b["location"] != a["location"]:
                continue
            if _fecha(b["created_at"]) > fa:
                a["later_findings_same_location"].append(
                    {"event_id": b["event_id"], "finding_id": b["finding_id"],
                     "final_state": b["final_state"], "created_at": b["created_at"]})
        a["later_findings_same_location"].sort(key=lambda x: (x["created_at"], x["event_id"], x["finding_id"]))

    return {"rows": filas, "summary": resumir(declaraciones, filas, etiqueta_hasta, hasta)}


def resumir(declaraciones: list[dict], filas: list[dict], etiqueta_hasta: str, hasta: str) -> dict:
    fechas = sorted(_fecha(d["event"]["created_at"]) for d in declaraciones)
    head_de = {d["event"]["event_id"]: d["event"]["head_commit"] for d in declaraciones}
    hallazgos = [h for d in declaraciones for h in d.get("findings", [])]
    estados: dict[str, int] = {}
    for h in hallazgos:
        estados[h["final_state"]] = estados.get(h["final_state"], 0) + 1

    resuelven = [f for f in filas if f["resolves_in_own_head"]]
    no_resuelven = [f for f in filas if not f["resolves_in_own_head"]]
    formas: dict[str, dict] = {}
    for f in no_resuelven:
        e = formas.setdefault(f["form"], {"findings": 0, "all_parts_resolve_after_normalization": 0,
                                          "examples": []})
        e["findings"] += 1
        e["all_parts_resolve_after_normalization"] += bool(f["all_parts_resolve_after_normalization"])
        if f["location"] not in e["examples"]:
            e["examples"].append(f["location"])
    for e in formas.values():
        e["examples"] = sorted(e["examples"])[:3]

    ubicaciones = sorted({f["location"] for f in filas})
    eventos_por_ubicacion: dict[str, set] = {}
    for f in filas:
        eventos_por_ubicacion.setdefault(f["location"], set()).add(f["event_id"])

    pares = [(a, b) for a in filas for b in a["later_findings_same_location"]]
    pares_de_interes = [(a, b) for a, b in pares if a["final_state"] in ESTADOS_DE_INTERES]

    def _con_posterior(estado_o_estados) -> tuple[int, int, int]:
        grupo = [h for h in hallazgos if h["final_state"] in estado_o_estados]
        con_loc = [f for f in filas if f["final_state"] in estado_o_estados]
        con_post = [f for f in con_loc if f["later_findings_same_location"]]
        return len(grupo), len(con_loc), len(con_post)

    deudas = _con_posterior(("debt_recorded",))
    refutaciones = _con_posterior(("refuted_verifiable", "refuted_interpretive"))
    cambiados = [f for f in resuelven if (f["commits_touching_after_head"] or 0) > 0]

    # Dias con fraccion: truncar a dias enteros acortaba la ventana y sesgaba
    # todas las tasas publicadas (hallazgo de la ronda sobre este script).
    dias = (fechas[-1] - fechas[0]).total_seconds() / 86400
    meses = dias / 30.4375
    por_mes = len(pares) / meses if meses > 0 else None
    por_mes_interes = len(pares_de_interes) / meses if meses > 0 else None

    # Posterioridad por `created_at` estrictamente mayor. Un empate no forma
    # par. Como control, se cuenta en cuantos pares el head del anterior es
    # ademas ancestro en git del head del posterior: si las dos nociones
    # difieren, el numero lo dice.
    ancestria = sum(1 for a, b in pares if _es_ancestro(a["head_commit"], head_de[b["event_id"]]))

    return {
        "measured_at": etiqueta_hasta,
        "measured_at_oid": hasta,
        "declarations": len(declaraciones),
        "window": {"first": fechas[0].isoformat(), "last": fechas[-1].isoformat(), "days": round(dias, 3)},
        "findings": len(hallazgos),
        "findings_by_state": dict(sorted(estados.items())),
        "findings_with_location": len(filas),
        "findings_without_location": len(hallazgos) - len(filas),
        "location_resolves_in_own_head": len(resuelven),
        "location_resolves_in_own_head_by_object_type": {
            t: sum(1 for f in resuelven if f["object_type_in_own_head"] == t)
            for t in sorted({f["object_type_in_own_head"] for f in resuelven})},
        "location_not_in_own_head_but_in_at": sum(1 for f in no_resuelven if f["resolves_in_at"]),
        "location_resolves_nowhere": sum(1 for f in no_resuelven if not f["resolves_in_at"]),
        "heads_not_reachable_from_at": sorted({f["head_commit"] for f in filas if not f["head_reachable_from_at"]}),
        "unresolved_forms": dict(sorted(formas.items())),
        "unresolved_all_parts_resolve_after_normalization": sum(
            1 for f in no_resuelven if f["all_parts_resolve_after_normalization"]),
        "distinct_location_strings": len(ubicaciones),
        "location_strings_in_more_than_one_declaration": sum(
            1 for s in eventos_por_ubicacion.values() if len(s) > 1),
        "pairs_earlier_later_same_location": len(pares),
        "pairs_where_earlier_head_is_ancestor_of_later_head": ancestria,
        "pairs_with_earlier_in_state_of_interest": len(pares_de_interes),
        "pairs_by_earlier_state": {
            e: sum(1 for a, _ in pares if a["final_state"] == e)
            for e in sorted({a["final_state"] for a, _ in pares})},
        "debt_recorded": {"findings": deudas[0], "with_location": deudas[1],
                          "with_later_finding_same_location": deudas[2]},
        "refuted": {"findings": refutaciones[0], "with_location": refutaciones[1],
                    "with_later_finding_same_location": refutaciones[2]},
        "resolving_locations_changed_after_head": len(cambiados),
        "rate": {
            "months_of_corpus": round(meses, 2),
            "pairs_per_month": round(por_mes, 3) if por_mes is not None else None,
            "pairs_of_interest_per_month": round(por_mes_interes, 3) if por_mes_interes is not None else None,
            "months_to_ten_pairs_linear": round(10 / por_mes, 1) if por_mes else None,
            "months_to_ten_pairs_of_interest_linear": round(10 / por_mes_interes, 1) if por_mes_interes else None,
            "note": "linear extrapolation over the whole window, not a bound in either direction: "
                    "a pair only appears when a later finding repeats an existing location string "
                    "exactly, so if new declarations use new strings the count stays flat and the "
                    "wait is unbounded; if they repeat old ones the count can grow faster than linear",
        },
    }


# --- salida ------------------------------------------------------------------

def imprimir(resultado: dict) -> None:
    s = resultado["summary"]
    e = s["findings_by_state"]
    print(f"declarations: {s['declarations']} (corpus: {s.get('corpus_read_from', 'working tree')}) | "
          f"window: {s['window']['first'][:10]} to {s['window']['last'][:10]} ({s['window']['days']} days) | "
          f"at {s['measured_at_oid'][:7]}")
    print(f"findings: {s['findings']}")
    print("  " + ", ".join(f"{k} {v}" for k, v in e.items()))
    print()
    print(f"findings with location: {s['findings_with_location']}")
    print(f"  resolve as a git object in the head of their own declaration: "
          f"{s['location_resolves_in_own_head']} "
          f"({', '.join(f'{v} {k}' for k, v in s['location_resolves_in_own_head_by_object_type'].items())})")
    print(f"  not in their own head but in {s['measured_at']}: {s['location_not_in_own_head_but_in_at']}")
    print(f"  resolve nowhere: {s['location_resolves_nowhere']}")
    if s["heads_not_reachable_from_at"]:
        print(f"  heads not reachable from {s['measured_at']}: {len(s['heads_not_reachable_from_at'])}")
    print()
    print("forms of the locations that do not resolve (what the string would need):")
    for forma, info in s["unresolved_forms"].items():
        print(f"  {forma:<22} {info['findings']:>3}   all parts resolve after the obvious "
              f"normalization: {info['all_parts_resolve_after_normalization']}")
    print(f"  {'total':<22} {s['findings_with_location'] - s['location_resolves_in_own_head']:>3}   "
          f"recoverable that way: {s['unresolved_all_parts_resolve_after_normalization']}")
    print()
    print(f"distinct location strings: {s['distinct_location_strings']}")
    print(f"location strings with findings from more than one declaration: "
          f"{s['location_strings_in_more_than_one_declaration']}")
    print(f"pairs (earlier finding, later finding, same location string): "
          f"{s['pairs_earlier_later_same_location']}")
    print(f"  where the earlier head is also a git ancestor of the later head: "
          f"{s['pairs_where_earlier_head_is_ancestor_of_later_head']}")
    print(f"  with the earlier one refuted or debt_recorded: {s['pairs_with_earlier_in_state_of_interest']}")
    print("  by state of the earlier one: " + (", ".join(f"{k} {v}" for k, v in s["pairs_by_earlier_state"].items()) or "none"))
    d, r = s["debt_recorded"], s["refuted"]
    print(f"debt_recorded: {d['findings']} | with location: {d['with_location']} | "
          f"with a later finding in the same location: {d['with_later_finding_same_location']}")
    print(f"refuted: {r['findings']} | with location: {r['with_location']} | "
          f"with a later finding in the same location: {r['with_later_finding_same_location']}")
    print(f"resolving locations whose file changed after the head of their declaration: "
          f"{s['resolving_locations_changed_after_head']} of {s['location_resolves_in_own_head']}")
    print()
    t = s["rate"]
    print(f"rate: {t['months_of_corpus']} months of corpus, {t['pairs_per_month']} pairs/month, "
          f"{t['pairs_of_interest_per_month']} pairs of interest/month")
    print(f"  months to ten pairs, linear: {t['months_to_ten_pairs_linear']} | "
          f"to ten pairs of interest: {t['months_to_ten_pairs_of_interest_linear']}")
    print(f"  ({t['note']})")
    print()
    print("| declaration | finding | state | location | resolves | commits after | later in same location |")
    print("|---|---|---|---|---|---|---|")
    for f in resultado["rows"]:
        posteriores = ", ".join(f"{x['event_id'][:8]}/{x['finding_id']}" for x in f["later_findings_same_location"]) or ""
        resuelve = f["object_type_in_own_head"] or f["form"]
        despues = "" if f["commits_touching_after_head"] is None else str(f["commits_touching_after_head"])
        print(f"| {f['event_id'][:8]} | {f['finding_id']} | {f['final_state']} | `{f['location']}` | "
              f"{resuelve} | {despues} | {posteriores} |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=Path, help="write the full result here, keys sorted")
    ap.add_argument("--at", default="HEAD", help="ref against which 'after' is measured")
    ap.add_argument("--corpus-at", default=None,
                    help="read the declarations from this commit instead of the working tree")
    ap.add_argument("--directory", type=Path, default=RAIZ / ".residue")
    args = ap.parse_args(argv)

    try:
        if args.corpus_at is not None:
            _commit(args.corpus_at)
        resultado = medir(cargar(args.directory, args.corpus_at), args.at)
    except RevisionAusente as e:
        # Un error de git no es una medicion. Se sale distinto de cero y sin
        # informe, para que nadie pegue numeros que no miran lo que dicen mirar.
        print(f"longitudinal: no se midio. {e}", file=sys.stderr)
        return 2
    resultado["summary"]["corpus_read_from"] = args.corpus_at or "working tree"
    imprimir(resultado)
    if args.json:
        args.json.write_bytes((json.dumps(resultado, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
                              .encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

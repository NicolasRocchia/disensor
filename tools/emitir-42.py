#!/usr/bin/env python3
"""Emite los objetos de evidencia de las parejas a un campo, bajo la forma
discutida en la lista al 16/09/2026, y reporta que no puede expresar.

Emits one evidence object per one-field MUST-PASS / MUST-FAIL pair under
the slots discussed on public-agent-conformance@w3.org, and reports what
the shape could not express.

Correr desde la raiz del repositorio / run from the repository root:

    python3 tools/emitir-42.py [directorio_de_salida | output_dir]

Por defecto escribe en ./salida-42/, que esta en .gitignore: un JSON por
pareja, un rollup.json y no-expresable.md. Nada mas se toca. Si preferis que
no escriba en el repo, pasale otra ruta.

La observacion NO es el `expected` del vector. El vector declara lo que se
espera; la observacion es lo que devuelve el checker al correrlo. Por eso este
script corre `validate_artifact` sobre los 84 vectores en vez de comparar
declaraciones.
"""
import dataclasses
import glob
import hashlib
import importlib.metadata
import itertools
import json
import os
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from disensor.rules import validate_artifact          # noqa: E402
from disensor.vectors import rule_labels              # noqa: E402

SUITES = ("v0.2", "v0.3", "v0.4")
SALIDA = sys.argv[1] if len(sys.argv) > 1 else "salida-42"

_via = Counter()


def serializar(e):
    """El checker devuelve errores de forma no declarada. Se serializa sin
    asumir su tipo y se anota por que camino salio, porque eso mismo es un
    hallazgo sobre que tan observable es la salida."""
    if dataclasses.is_dataclass(e) and not isinstance(e, type):
        _via["dataclass"] += 1
        return dataclasses.asdict(e)
    if isinstance(e, dict):
        _via["dict"] += 1
        return e
    if isinstance(e, (list, tuple)):
        _via["secuencia"] += 1
        return [serializar(x) for x in e]
    if hasattr(e, "_asdict"):
        _via["namedtuple"] += 1
        return e._asdict()
    if hasattr(e, "__dict__") and vars(e):
        _via["__dict__"] += 1
        return {k: v for k, v in vars(e).items() if not k.startswith("_")}
    _via["str"] += 1
    return {"repr": str(e)}


def plano(o, p=""):
    d = {}
    if isinstance(o, dict):
        for k, v in o.items():
            d.update(plano(v, f"{p}/{k}"))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            d.update(plano(v, f"{p}/{i}"))
    else:
        d[p] = o
    return d


def dif(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def sha(path):
    with open(path, "rb") as f:
        return "sha256:" + hashlib.sha256(f.read()).hexdigest()


def cargar(suite):
    """Corre el checker sobre cada vector. La observacion es lo que devuelve."""
    out = []
    for f in sorted(glob.glob(f"spec/vectors/{suite}/*.json")):
        if os.path.basename(f) == "index.json":
            continue
        with open(f, encoding="utf-8") as fh:
            v = json.load(fh)
        errores = validate_artifact(v["artifact"])
        observacion = {
            "valid": not errores,
            "rules": rule_labels(errores),
            "errors": [serializar(e) for e in errores],
        }
        out.append({
            "id": os.path.basename(f)[:-5],
            "path": f.replace("\\", "/"),
            "sha256": sha(f),
            "esperado": v.get("expected") or {},
            "observacion": observacion,
            "artefacto": plano(v.get("artifact") or {}),
        })
    return out


commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
# Dos estados distintos y no uno. Contenido tracked modificado significa que
# el commit no es fuente del numero. Archivos untracked no cambian lo que trae
# un checkout, pero pueden ensombrecer un modulo, asi que se nombran y no se
# bloquean. Colapsarlos en "sucio" pierde la diferencia.
_tracked = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                          capture_output=True, text=True).stdout.strip()
_todo = subprocess.run(["git", "status", "--porcelain"],
                       capture_output=True, text=True).stdout.strip()
untracked = [l[3:] for l in _todo.splitlines() if l.startswith("?? ")]

print(f"commit: {commit}")
print(f"jsonschema: {importlib.metadata.version('jsonschema')}")
if _tracked:
    print("  ARBOL MODIFICADO: hay contenido tracked distinto del commit.")
    print("  El numero NO tiene fuente limpia. No publicarlo asi.")
    for l in _tracked.splitlines():
        print(f"    {l}")
if untracked:
    print(f"  untracked presentes ({len(untracked)}), no afectan un checkout:")
    for u in untracked:
        print(f"    {u}")
print()

os.makedirs(SALIDA, exist_ok=True)

objetos, movidos, desacuerdos = [], Counter(), []
por_suite = Counter()

for suite in SUITES:
    vs = cargar(suite)

    # Un vector cuya observacion no coincide con lo declarado se anota y se
    # excluye: la suite no esta verde y cualquier objeto emitido desde ahi
    # afirmaria algo que el repositorio no sostiene.
    for v in vs:
        esp = v["esperado"]
        obs = v["observacion"]
        if esp.get("valid") != obs["valid"] or (esp.get("rules") or []) != obs["rules"]:
            desacuerdos.append({"suite": suite, "vector": v["id"],
                                "esperado": esp,
                                "observado": {"valid": obs["valid"], "rules": obs["rules"]}})

    mp = [v for v in vs if v["observacion"]["valid"]]
    mf = [v for v in vs if not v["observacion"]["valid"]]

    for a, b in itertools.product(mp, mf):
        campos = dif(a["artefacto"], b["artefacto"])
        if len(campos) != 1:
            continue
        campo = campos[0]

        pa, pb = plano(a["observacion"]), plano(b["observacion"])
        movido = dif(pa, pb)                       # recomputado, registro entero
        raices = sorted({k.lstrip("/").split("/")[0] for k in movido})
        for r in raices:
            movidos[r] += 1
        por_suite[suite] += 1

        obj = {
            "pair": f"{suite}/{a['id']}|{b['id']}",
            "changed": "input artifact",
            "fixed": {
                "checker": f"disensor.rules.validate_artifact@{commit}",
                "constraint_set": f"residue/{suite}",
                "domain": f"residue/{suite} declarations under the reference validator",
            },
            "compared": sorted(a["observacion"].keys()),   # declarado
            "moved": raices,                               # recomputado
            "moved_paths": movido,
            "delta": {"field": campo,
                      "from": a["artefacto"].get(campo),
                      "to": b["artefacto"].get(campo)},
            "observations": [
                {"vector": a["path"], "commit": commit, "digest": a["sha256"]},
                {"vector": b["path"], "commit": commit, "digest": b["sha256"]},
            ],
        }
        objetos.append(obj)
        with open(os.path.join(SALIDA, f"{suite}__{a['id']}__{b['id']}.json"),
                  "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=str)

fuera = [o for o in objetos if set(o["moved"]) - {"valid", "rules"}]

rollup = {
    "commit": commit,
    "tracked_modificado": bool(_tracked),
    "untracked_presentes": untracked,
    "pares_emitidos": len(objetos),
    "por_suite": dict(por_suite),
    "evidencia_llevada": 0,
    "evidencia_referenciada": len(objetos) * 2,
    "mueven_algo_fuera_de_valid_y_rules": len(fuera),
    "frecuencia_de_lo_que_se_mueve": dict(movidos),
    "serializacion_de_errores": dict(_via),
    "vectores_cuya_observacion_no_coincide_con_lo_declarado": desacuerdos,
}
with open(os.path.join(SALIDA, "rollup.json"), "w", encoding="utf-8") as f:
    json.dump(rollup, f, indent=2, ensure_ascii=False, default=str)

with open(os.path.join(SALIDA, "no-expresable.md"), "w", encoding="utf-8") as f:
    f.write(f"# Lo que la forma no pudo expresar\n\ncommit {commit}\n\n")
    if not fuera:
        f.write("Ninguna pareja movio algo fuera de `valid` y `rules`.\n")
    for o in fuera:
        f.write(f"- `{o['pair']}` movio {o['moved']} por el campo `{o['delta']['field']}`\n")
    if desacuerdos:
        f.write("\n## Vectores cuya observacion no coincide con lo declarado\n\n")
        for d in desacuerdos:
            f.write(f"- `{d['suite']}/{d['vector']}`: esperado {d['esperado']}, "
                    f"observado {d['observado']}\n")

print(f"pares emitidos: {len(objetos)}  {dict(por_suite)}")
print(f"evidencia: {rollup['evidencia_llevada']} llevada / "
      f"{rollup['evidencia_referenciada']} referenciada")
print(f"mueven algo fuera de valid y rules: {len(fuera)}")
print(f"frecuencia de lo que se mueve: {dict(movidos)}")
print(f"serializacion de errores: {dict(_via)}")
print(f"vectores que no coinciden con lo declarado: {len(desacuerdos)}")
print(f"\nescrito en {SALIDA}/")

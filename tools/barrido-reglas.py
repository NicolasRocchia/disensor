#!/usr/bin/env python3
"""Barrido de aislamiento: relaja una etiqueta por vez y anota qué vectores
cambian. Es el chequeo del mensaje 2026Sep/0013 de la lista del W3C.

Isolation sweep: relaxes one label at a time and records which vectors flip.
It is the check behind message 2026Sep/0013 on public-agent-conformance@w3.org.

Correr desde la raíz del repositorio / run from the repository root:

    python3 tools/barrido-reglas.py [directorio_de_salida | output_dir]

Corre sobre el checkout, porque usa el validador de ese commit: imprime el
commit y se niega a correr si hay archivos versionados modificados. Para medir
otro commit, un worktree en ese commit y este script llamado por su ruta. Por
defecto escribe en ./salida-barrido/, que está en .gitignore: un barrido.json
y nada más, tampoco bytecode. Si preferís que no escriba en el repo, pasale
otra ruta.

Qué hace. Para cada etiqueta del registro corre `validate_artifact` sobre los
vectores de las tres suites (en el orden de cada `index.json`), saca de la
salida los errores que empiezan con `[<etiqueta>]`, recalcula el veredicto
(sin errores es válido) y las etiquetas, y compara con el `expected` del
vector. Un vector cambia si cambia el veredicto o la lista de etiquetas. Por
etiqueta reporta cuántos vectores la nombran, cuántos cambian, y si los que
cambian son exactamente los que la nombran. El registro son las etiquetas de
regla entre comillas dobles en `src/disensor/rules.py`, leídas igual que en
`tests/test_rule_coverage.py`, más `schema`.

Límite. El barrido relaja la salida, no el código. Para las reglas es
equivalente a que la regla no dispare, porque `rule_errors` evalúa todas sin
retornos tempranos. Para el esquema no: `validate_artifact` devuelve los
errores de esquema antes de correr las reglas, así que sacarlos no es aflojar
el esquema. La línea `schema` dice qué vectores dependen de la salida del
esquema, no qué dejaría pasar un esquema aflojado.

El JSON lleva el commit, la cantidad de vectores y, por etiqueta,
`relaxed_rule`, `named`, `flipped` y `unchanged_count`; `named` y `flipped`
son listas ordenadas de ids `<suite>/<vector>`. Es estable byte a byte: dos
corridas en el mismo commit dan el mismo sha256, que el script imprime. Solo
se escribe con cero desacuerdos de base: si algún vector ya difiere de su
`expected` sin relajar nada, el barrido no aísla nada y el script termina con
código 1.

Procedencia. El chequeo lo propuso Kenne Ives en la lista (2026Sep/0010) y
Nicolás Rocchia lo corrió por primera vez en 2026Sep/0013.

It runs on the checkout, because it uses the validator of that commit: it
prints the commit and refuses to run if tracked files are modified. To measure
another commit, use a worktree at that commit and call this script by its
path. By default it writes to ./salida-barrido/, which is in .gitignore: one
barrido.json and nothing else, not even bytecode. Pass another path if you
would rather it did not write inside the repository.

What it does. For each label in the registry it runs `validate_artifact` over
the vectors of the three suites (in the order of each `index.json`), drops
from the output the errors that start with `[<label>]`, recomputes the verdict
(no errors means valid) and the labels, and compares with the `expected` of
the vector. A vector flips if the verdict or the label list changes. Per label
it reports how many vectors name it, how many flip, and whether the ones that
flip are exactly the ones that name it. The registry is the rule labels in
double quotes in `src/disensor/rules.py`, read the way
`tests/test_rule_coverage.py` reads them, plus `schema`.

Limit. The sweep relaxes the output, not the code. For the rules that is
equivalent to the rule not firing, because `rule_errors` evaluates all of them
with no early returns. For the schema it is not: `validate_artifact` returns
the schema errors before running the rules, so dropping them is not loosening
the schema. The `schema` line says which vectors depend on the schema output,
not what a loosened schema would let through.

The JSON carries the commit, the number of vectors and, per label,
`relaxed_rule`, `named`, `flipped` and `unchanged_count`; `named` and
`flipped` are sorted lists of `<suite>/<vector>` ids. It is byte-stable: two
runs on the same commit give the same sha256, which the script prints. It is
written only with zero baseline disagreements: if a vector already differs
from its `expected` with nothing relaxed, the sweep isolates nothing and the
script exits with code 1.

Provenance. The check was proposed by Kenne Ives on the list (2026Sep/0010)
and first run by Nicolás Rocchia in 2026Sep/0013.
"""
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys

# Lo que se imprime va en ASCII, para que una salida redirigida no dependa de
# la página de códigos de quien reproduce.
if not os.path.isfile(os.path.join("src", "disensor", "rules.py")):
    sys.exit("no encuentro src/disensor/rules.py: el directorio actual tiene que ser el del repositorio")

# "Nada más" incluye el bytecode de los módulos que importa desde src.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from disensor.rules import validate_artifact          # noqa: E402

SUITES = ("v0.2", "v0.3", "v0.4")
SALIDA = sys.argv[1] if len(sys.argv) > 1 else "salida-barrido"


def git(*args):
    r = subprocess.run(["git", "--no-optional-locks", *args],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def etiquetas(errores):
    # Idéntica a `rule_labels` de src/disensor/vectors.py. Es una copia y no un
    # import porque `rule_labels` se hizo pública en 33222e6, y este script
    # tiene que correr también en commits anteriores, como f3295ca.
    tags = set()
    for e in errores:
        if e.startswith("[") and "]" in e:
            tags.add(e[1:e.index("]")])
    return sorted(tags)


def cambia(esperado, errores):
    """El veredicto o la lista de etiquetas no son los que declara el vector."""
    return ((not errores) != esperado.get("valid")
            or etiquetas(errores) != (esperado.get("rules") or []))


def registro():
    """Las etiquetas que rules.py puede emitir, leídas de la fuente como en
    `_registro()` de tests/test_rule_coverage.py, más la capa de esquema."""
    with open(os.path.join("src", "disensor", "rules.py"), encoding="utf-8") as fh:
        fuente = fh.read()
    entrecomilladas = set(re.findall(r'"(R\d+)"', fuente))
    sueltas = set(re.findall(r"\bR\d+\b", fuente))
    if not sueltas <= entrecomilladas:
        sys.exit(f"rules.py nombra {sorted(sueltas - entrecomilladas)} fuera de un literal "
                 "entre comillas dobles: el barrido solo ve los literales, y esa regla queda fuera.")
    return sorted(entrecomilladas, key=lambda r: int(r[1:])) + ["schema"]


commit = git("rev-parse", "HEAD").strip()
# Dos estados distintos, como en emitir-42.py. Contenido versionado modificado
# significa que el validador que corre no es el del commit: ahí no se mide.
# Los archivos sin versionar no cambian lo que trae un checkout, así que se
# nombran y no bloquean.
modificados = git("status", "--porcelain", "--untracked-files=no").strip()
sueltos = [l[3:] for l in git("status", "--porcelain").splitlines() if l.startswith("?? ")]

print(f"commit: {commit[:7]}")
print(f"jsonschema: {importlib.metadata.version('jsonschema')}")
if sueltos:
    print(f"  sin versionar ({len(sueltos)}), no afectan un checkout:")
    for s in sueltos:
        print(f"    {s}")
if modificados:
    print("  HAY ARCHIVOS VERSIONADOS MODIFICADOS:")
    for l in modificados.splitlines():
        print(f"    {l}")
    sys.exit("el validador del checkout no es el del commit: no se mide.")
print()

vectores = []
for suite in SUITES:
    with open(f"spec/vectors/{suite}/index.json", encoding="utf-8") as fh:
        indice = json.load(fh)
    for nombre in indice["vectors"]:
        with open(f"spec/vectors/{suite}/{nombre}.json", encoding="utf-8") as fh:
            v = json.load(fh)
        vectores.append((f"{suite}/{nombre}", v.get("expected") or {},
                         validate_artifact(v["artifact"])))

base = sorted(n for n, esperado, errores in vectores if cambia(esperado, errores))
print(f"{len(vectores)} vectores, {len(base)} desacuerdos de base")
for n in base:
    print(f"    {n}")
print()

barrido = []
print("etiqueta  nombran  cambian")
for etiqueta in registro():
    nombran = sorted(n for n, esperado, _ in vectores if etiqueta in (esperado.get("rules") or []))
    cambian = sorted(n for n, esperado, errores in vectores
                     if cambia(esperado, [e for e in errores if not e.startswith(f"[{etiqueta}]")]))
    barrido.append({
        "relaxed_rule": etiqueta,
        "named": nombran,
        "flipped": cambian,
        "unchanged_count": len(vectores) - len(cambian),
    })
    nota = "exacta" if cambian == nombran else "NO EXACTA"
    if not nombran and not cambian:
        nota = "en cero"
    print(f"{etiqueta:8}  {len(nombran):7}  {len(cambian):7}  {nota}")

reglas = [b for b in barrido if b["relaxed_rule"] != "schema"]
con_vectores = [b for b in reglas if b["named"]]
exactas = [b for b in con_vectores if b["flipped"] == b["named"]]
en_cero = [b["relaxed_rule"] for b in reglas if not b["named"] and not b["flipped"]]
print(f"\nreglas con vectores: {len(con_vectores)}, exactas: {len(exactas)}")
print(f"reglas en cero: {', '.join(en_cero) or 'ninguna'}")

if base:
    sys.exit("\nhay desacuerdos de base: no se escribe el JSON.")

# Estable byte a byte: claves ordenadas, separadores fijos, ids ordenados, ASCII,
# salto de línea final, y escrito en binario para que Windows no lo pase a CRLF.
# El commit va entero porque el largo del abreviado depende del repositorio.
datos = (json.dumps({"commit": commit, "vector_count": len(vectores), "sweep": barrido},
                    sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=True)
         + "\n").encode("ascii")
os.makedirs(SALIDA, exist_ok=True)
ruta = os.path.join(SALIDA, "barrido.json")
with open(ruta, "wb") as fh:
    fh.write(datos)
print(f"\nescrito en {ruta.replace(os.sep, '/')}")
print(f"sha256: {hashlib.sha256(datos).hexdigest()}")

#!/usr/bin/env python3
"""Emite la corrida del validador sobre `.residue/` como reportes v0.1 y los
MUST-FAIL de `spec/vectors/` como registros 5.5. Es la ruta del control del
5.4 con datos de disensor, para el paper de arXiv sobre la v0.1 del texto de
public-agent-conformance@w3.org.

Emits the validator's run over `.residue/` as v0.1 reports and the MUST-FAIL
vectors of `spec/vectors/` as section 5.5 records. It is the 5.4 control route
with disensor data, for the arXiv paper on v0.1 of the
public-agent-conformance@w3.org text.

Correr desde la raíz del repositorio / run from the repository root:

    python3 tools/emitir-55.py --runner "<nombre | name>" [directorio_de_salida | output_dir]

Corre sobre el checkout, porque usa el validador de ese commit: imprime el
commit y se niega a correr si hay archivos versionados modificados. Los datos
de entrada (vectores, índices, declaraciones, esquemas, `rules.py`, LICENSE) se
leen de los objetos de git del commit, resuelto una vez al empezar y nunca por
el nombre HEAD, así los bytes que se digieren son los del commit y no los de un
checkout con CRLF ni los de otro commit al que alguien haya movido HEAD en el
medio. Antes de escribir vuelve a mirar: HEAD sigue en ese commit, el árbol
sigue limpio y `rules.py` y los esquemas del checkout, que es de donde carga
`validate_artifact`, son los del commit. Por defecto escribe en ./salida-55/,
que está en .gitignore, y nada más, tampoco bytecode. `--runner` es quien
corre, y entra solo en `control-results.json`.

Se niega también si hay algo sin versionar bajo `src/`: de ahí importa el
validador, y un módulo suelto (un `src/jsonschema/`, por ejemplo) correría en
lugar del instalado sin que `git status --untracked-files=no` lo viera. Y
comprueba de dónde importó lo que corre: `disensor.rules` del checkout,
`jsonschema` de fuera de él. El directorio de salida tiene que estar fuera del
repositorio o ignorado por git, y si ya existe solo puede tener lo que este
script emite: se sobreescribe la salida de una corrida anterior y nada más.

Qué emite, en el directorio de salida:

- `configs/residue-v0.X.json`: la configuración del validador por versión
  (checker, esquema declarado y sha256 del blob del esquema). Su sha256 es el
  `config_digest`.
- `run-residue-v0.X.json`: un reporte `public-agent-conformance/report/v0.1`
  por versión de esquema, en la codificación del corpus `vectors-w3c-report`
  de agent-evidence-vectors 0.17.4. Un check por (declaración de esa versión,
  etiqueta que corre en esa versión), `check-set` de forma `flat`, y
  `negative-capable` de clase `control-failed` apuntando a los checks cuya
  etiqueta tiene registro 5.5 en la suite de esa versión, con el mismo `fixed`.
- `fixtures.json`: los registros 5.5. Uno por MUST-FAIL de las tres suites que
  dispara una sola etiqueta; `derived_from` solo si hay un MUST-PASS de la
  misma suite a exactamente un campo (el primero en el orden del `index.json`);
  bloque `isolation` solo en los registros de regla.
- `control-results.json`: lo que `validate_artifact` dio para cada registro en
  esta corrida, con el runner.
- `isolation.json`: el método del barrido del 0013 aplicado a los registros 5.5
  y no a los 89 vectores: por etiqueta de regla, sacar de la salida observada
  los errores `[<etiqueta>]`, recalcular veredicto y etiquetas, y anotar qué
  registros cambian. Un registro cambia si cambia el veredicto o la lista de
  etiquetas.
- `summary.json`, `README.txt` y `SHA256SUMS` (una línea por archivo, sin sí
  mismo, ordenada por ruta). El script imprime al final el sha256 de
  `SHA256SUMS`.

Toda salida JSON es estable byte a byte: claves ordenadas, separadores fijos,
UTF-8, sin salto de línea final, listas ordenadas, sin floats. Dos corridas en
el mismo commit, con el mismo `--runner` y las mismas versiones de Python y
`jsonschema`, dan el mismo `SHA256SUMS`: `summary.json` registra esas
versiones y `SHA256SUMS` lo cubre, así que otro entorno cambia esa línea y la
suma final, no los reportes ni los registros.

El `check-set` de forma `flat` se calcula como lo hace el lector de referencia
(`agent_evidence_vectors.w3creport`): SHA-256 sobre la concatenación de los
digests SHA-256 crudos de cada check serializado compacto (`sort_keys=True`,
`separators=(",", ":")`, UTF-8), en el orden de la lista. El texto todavía no
fija el árbol (O3). El script verifica su reimplementación contra un miembro
del corpus antes de correr.

Se escribe solo con cero desacuerdos: si algún vector difiere de su
`expected`, si alguna declaración no valida, o si el registro de etiquetas de
`rules.py` no coincide con la tabla por versión del script, no se escribe nada
y el script termina con código 1.

Límites, que van también en README.txt:

- Un solo autor escribió el corpus, el validador, las reglas esperadas y este
  script, y las reglas esperadas estaban a la vista antes de correr. Todas las
  corridas son del mismo autor: no es el caso de dos partes del O8.
- El aislamiento relaja la salida del validador, no su código. Para las reglas
  equivale a que la regla no dispare, porque `rule_errors` evalúa todas sin
  retornos tempranos; para el esquema no, porque `validate_artifact` corta
  antes de las reglas, y por eso los registros de esquema no llevan bloque
  `isolation`.
- Los tres vectores que disparan dos reglas no se escriben como 5.5: un
  registro 5.5 nombra una sola regla. Van en `summary.json`.
- R3 y R8 no tienen control: el esquema prohíbe la condición que prueban
  (`spec/rule_coverage.json`, probado en las dos direcciones por la referencia
  en Python y el port en TypeScript). Sus checks quedan en `pass` con
  calificadores `unknown`.
- La suite v0.2 da control solo para R0, R4, R6 y el esquema.
- El checker es el código en el commit más Python y `jsonschema`, con las
  versiones que registra `summary.json`. El validador no lee el reloj.
- Las miradas al checkout son instantáneas, no barreras: no cubren un sistema
  de archivos hostil (bytecode en `__pycache__` con la misma marca que la
  fuente, o un intérprete o un `jsonschema` alterados fuera del repositorio).

It runs on the checkout, because it uses the validator of that commit: it
prints the commit and refuses to run if tracked files are modified. Inputs
(vectors, indexes, declarations, schemas, `rules.py`, LICENSE) are read from
the git objects of the commit, resolved once at the start and never through the
name HEAD, so the digested bytes are the commit's and not those of a checkout
with CRLF or of another commit someone moved HEAD to midway. Before writing it
looks again: HEAD is still that commit, the tree is still clean, and `rules.py`
and the schemas in the checkout, which is where `validate_artifact` loads them
from, are the commit's. By default it writes to ./salida-55/, which is in
.gitignore, and nothing else, not even bytecode. `--runner` names who runs it
and goes only into `control-results.json`.

It also refuses if anything untracked sits under `src/`: the validator is
imported from there, and a loose module (a `src/jsonschema/`, say) would run in
place of the installed one without `git status --untracked-files=no` noticing.
And it checks where what runs was imported from: `disensor.rules` from the
checkout, `jsonschema` from outside it. The output directory has to be outside
the repository or ignored by git, and if it already exists it may only hold
what this script emits: a previous run's output is overwritten, nothing else.

What it emits, in the output directory:

- `configs/residue-v0.X.json`: the validator configuration per version
  (checker, declared schema and sha256 of the schema blob). Its sha256 is the
  `config_digest`.
- `run-residue-v0.X.json`: one `public-agent-conformance/report/v0.1` report
  per schema version, in the encoding of the `vectors-w3c-report` corpus of
  agent-evidence-vectors 0.17.4. One check per (declaration of that version,
  label that runs in that version), a `check-set` of shape `flat`, and a
  `negative-capable` of kind `control-failed` pointing at the checks whose
  label has a 5.5 record in that version's suite, with the same `fixed`.
- `fixtures.json`: the 5.5 records. One per MUST-FAIL of the three suites that
  fires a single label; `derived_from` only when a MUST-PASS of the same suite
  sits exactly one field away (the first in `index.json` order); an
  `isolation` block only on rule records.
- `control-results.json`: what `validate_artifact` returned for each record in
  this run, with the runner.
- `isolation.json`: the 0013 sweep applied to the 5.5 records rather than to
  the 89 vectors: per rule label, drop the `[<label>]` errors from the observed
  output, recompute verdict and labels, and record which records flip. A
  record flips if the verdict or the label list changes.
- `summary.json`, `README.txt` and `SHA256SUMS` (one line per file, itself
  excluded, sorted by path). The script prints the sha256 of `SHA256SUMS` last.

Every JSON output is byte-stable: sorted keys, fixed separators, UTF-8, no
trailing newline, sorted lists, no floats. Two runs on the same commit, with
the same `--runner` and the same Python and `jsonschema` versions, give the
same `SHA256SUMS`: `summary.json` records those versions and `SHA256SUMS`
covers it, so another environment changes that line and the final sum, not
the reports or the records.

The `flat` check-set is computed the way the reference reader
(`agent_evidence_vectors.w3creport`) does: SHA-256 over the concatenation of
the raw SHA-256 digests of each check serialized compactly (`sort_keys=True`,
`separators=(",", ":")`, UTF-8), in list order. The text does not fix the tree
yet (O3). The script checks its reimplementation against a corpus member before
running.

It writes only with zero disagreements: if a vector differs from its
`expected`, if a declaration does not validate, or if the label registry of
`rules.py` does not match the script's per-version table, nothing is written
and the script exits with code 1.

Limits, also written to README.txt:

- One author wrote the corpus, the validator, the expected rules and this
  script, and the expected rules were in view before running. Every run is by
  the same author: this is not the two-party case of O8.
- Isolation relaxes the validator's output, not its code. For the rules that
  equals the rule not firing, because `rule_errors` evaluates all of them with
  no early returns; for the schema it does not, because `validate_artifact`
  returns before the rules, which is why schema records carry no `isolation`
  block.
- The three vectors that fire two rules are not written as 5.5: a 5.5 record
  names one rule. They are listed in `summary.json`.
- R3 and R8 have no control: the schema forbids the condition they test
  (`spec/rule_coverage.json`, proven in both directions by the Python reference
  and the TypeScript port). Their checks stay `pass` with `unknown` qualifiers.
- The v0.2 suite gives control only for R0, R4, R6 and the schema.
- The checker is the code at the commit plus Python and `jsonschema`, at the
  versions `summary.json` records. The validator does not read the clock.
- The looks at the checkout are snapshots, not barriers: they do not cover a
  hostile file system (bytecode in `__pycache__` stamped like the source, or an
  altered interpreter or `jsonschema` outside the repository).
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys

# Lo que se imprime va en ASCII, para que una salida redirigida no dependa de
# la página de códigos de quien reproduce.
if not os.path.isfile(os.path.join("src", "disensor", "rules.py")):
    sys.exit("no encuentro src/disensor/rules.py: el directorio actual tiene que ser el del repositorio")


def git(*args, binario=False):
    r = subprocess.run(["git", "--no-optional-locks", *args], capture_output=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout if binario else r.stdout.decode("utf-8")


def bajo(ruta, raiz):
    """La ruta está dentro de la raíz (False también si están en discos distintos)."""
    try:
        return os.path.commonpath([ruta, raiz]) == raiz
    except ValueError:
        return False


# Nada sin versionar bajo src/: de ahí se importa el validador, y un módulo
# suelto (un `src/jsonschema/`, por ejemplo) correría en lugar del instalado
# sin que `git status --untracked-files=no` lo viera. El bytecode de
# __pycache__ no agrega módulos, así que no bloquea.
_sueltos_src = [l[3:] for l in git("status", "--porcelain", "--ignored", "--", "src").splitlines()
                if l[:2] in ("??", "!!") and "__pycache__" not in l]
if _sueltos_src:
    sys.exit("hay archivos sin versionar o ignorados bajo src/, de donde se importa el validador: "
             + ", ".join(_sueltos_src))

# "Nada más" incluye el bytecode de los módulos que importa desde src.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
import jsonschema                                     # noqa: E402
import disensor.rules                                 # noqa: E402
from disensor.rules import validate_artifact          # noqa: E402

# De dónde se importó lo que va a correr: el validador, del checkout; su
# dependencia, de fuera de él.
_RAIZ = os.path.realpath(os.getcwd())
if os.path.realpath(disensor.rules.__file__) != os.path.realpath(os.path.join("src", "disensor", "rules.py")):
    sys.exit(f"disensor.rules se importo de {disensor.rules.__file__} y no del checkout")
if bajo(os.path.realpath(jsonschema.__file__), _RAIZ):
    sys.exit(f"jsonschema se importo desde el checkout ({jsonschema.__file__}) y no del entorno")

NL = chr(10)
NUL = chr(0)

SUITES = ("v0.2", "v0.3", "v0.4")
VERSIONES = {s: f"residue/{s}" for s in SUITES}
RAW = "https://raw.githubusercontent.com/NicolasRocchia/disensor"
CHECKER = "disensor.rules.validate_artifact"
FORMATO = "public-agent-conformance/report/v0.1"
ESQUEMAS = ("residue.schema.json", "residue.schema.v0.2.json",
            "residue.schema.v0.3.json", "residue.schema.v0.4.json")
AUTOR = "Nicolás Rocchia"
EMITIDOS = (tuple(f"configs/residue-{s}.json" for s in SUITES)
            + tuple(f"run-residue-{s}.json" for s in SUITES)
            + ("fixtures.json", "control-results.json", "isolation.json", "summary.json",
               "README.txt", "SHA256SUMS"))

# Etiquetas que corren en cada versión. R11 y R12 viven dentro de
# `_independence_errors`, que `rule_errors` llama solo bajo
# `applies_from(a["schema"], "residue/v0.4")` (src/disensor/rules.py, bloque
# R4); R13 tiene su propio bloque bajo la misma condición. En v0.2 y v0.3 corre
# el R4 clásico y ninguna de las tres. La tabla se contrasta con el registro
# leído de la fuente antes de correr.
ETIQUETAS_POR_VERSION = {
    "v0.2": ["schema"] + [f"R{n}" for n in range(0, 11)],
    "v0.3": ["schema"] + [f"R{n}" for n in range(0, 11)],
    "v0.4": ["schema"] + [f"R{n}" for n in range(0, 14)],
}

# Una oración por regla, escrita desde el comentario de cada regla en
# src/disensor/rules.py y la sección «What the gate enforces» del README.
# Donde el README y el código no coinciden (R11 y R12), manda el código.
WHY = {
    "R0": "The event declares no human arbiter present, and without one the round does not comply with the protocol (section 6).",
    "R1": "A finding whose final state joins the residue has no residue item, or an item references a finding that does not exist or whose state does not match the item's class.",
    "R2": "A text declaration carries a generic marker, or some field still carries the unfilled template marker.",
    "R3": "The abbreviated path is used on a change that touches the protected cases of 3.2.",
    "R4": "The declared independence of a reviewer contradicts the declared families and models, or sits below cross_family without the fallback reason the record demands or at a level that does not admit it.",
    "R5": "A Level A event carries an execution gap without written acceptance by a lead (section 7).",
    "R6": "The declared counts do not add up to the findings list.",
    "R7": "In the diff gate an incorporated finding closes without its fix verified, or with the verification left pending.",
    "R8": "An interpretive refutation does not require human attention (section 6).",
    "R9": "The minimized profile carries free text, evidence text or link, or a clear repository URL that the profile strips.",
    "R10": "The full profile declares no findings list, or lists none while the counts declare some.",
    "R11": "A reviewer declared below cross_family has no reviewer_correlation residue item naming it.",
    "R12": "A reviewer with unverified hardening has no reviewer_hardening_gap residue item naming it.",
    "R13": "A local identifier is declared more than once, or a reference to a reviewer does not resolve against the declared ones.",
}


def blob(commit, ruta):
    """Los bytes del archivo en el commit medido, tal como están en el objeto
    de git. Siempre por el hash resuelto al empezar y nunca por el nombre HEAD,
    que otro proceso puede mover mientras el script corre."""
    return git("show", f"{commit}:{ruta}", binario=True)


def mismo_checker(commit, sha_normalizados):
    """Antes de escribir, la segunda mirada: HEAD sigue siendo el commit, el
    árbol sigue limpio y los archivos del validador que corrió (rules.py y los
    esquemas, que `validate_artifact` carga del checkout) son byte a byte los
    del commit, salvo finales de línea. Es una instantánea antes y después y no
    una barrera: ve a otro proceso que mueva HEAD o toque el checkout durante
    la corrida, no a uno que lo haga y lo deshaga entre las dos miradas."""
    ahora = git("rev-parse", "HEAD").strip()
    if ahora != commit:
        sys.exit(f"HEAD se movio durante la corrida ({commit} -> {ahora}): no se escribe nada.")
    if git("status", "--porcelain", "--untracked-files=no").strip():
        sys.exit("el arbol cambio durante la corrida: no se escribe nada.")
    for ruta, esperado in sha_normalizados.items():
        with open(ruta, "rb") as fh:
            disco = fh.read()
        if sha(normaliza(disco)) != esperado:
            sys.exit(f"{ruta} en el checkout no es el del commit: el validador que corrio no es el medido.")


def destino_seguro(salida):
    """El directorio de salida está fuera del repositorio o git lo ignora, y si
    ya existe solo tiene lo que este script emite: se sobreescribe la salida de
    una corrida anterior y nada más. Así `.` o `tools` no siembran archivos en
    el checkout, y un directorio ajeno no pierde lo que tenía."""
    real = os.path.realpath(salida)
    if real == _RAIZ or bajo(real, _RAIZ):
        # Se pregunta por un hijo del destino y no por el destino: así una regla
        # de directorio como `salida-55/` lo alcanza aunque el directorio no
        # exista todavía, y un destino que git no ignora da 1 exista o no.
        r = subprocess.run(["git", "--no-optional-locks", "check-ignore", "-q", "--", os.path.join(salida, "SHA256SUMS")],
                           capture_output=True)
        if r.returncode != 0:
            sys.exit(f"{salida} esta dentro del repositorio y git no lo ignora: "
                     "usa un directorio ignorado (salida-55/) o uno fuera del repositorio.")
    if os.path.isdir(real):
        permitidos = set(EMITIDOS) | {"configs"}
        presentes = set()
        for raiz, dirs, archivos in os.walk(real):
            for n in dirs + archivos:
                presentes.add(os.path.relpath(os.path.join(raiz, n), real).replace(os.sep, "/"))
        ajenos = sorted(presentes - permitidos)
        if ajenos:
            sys.exit(f"{salida} ya existe y tiene lo que este script no emite: {', '.join(ajenos[:5])}"
                     f"{', ...' if len(ajenos) > 5 else ''}. Vaciarlo o elegir otro.")
    elif os.path.exists(real):
        sys.exit(f"{salida} existe y no es un directorio.")


def normaliza(datos):
    """Finales de línea a LF, para comparar un checkout con autocrlf contra el
    blob del commit."""
    return datos.replace(bytes([13, 10]), bytes([10]))


def sha(datos):
    return hashlib.sha256(datos).hexdigest()


def sin_floats(valor, ruta="$"):
    if isinstance(valor, float):
        sys.exit(f"float en {ruta}: la regla W3C-R-020 lo rechaza")
    if isinstance(valor, dict):
        for k, v in valor.items():
            sin_floats(v, f"{ruta}.{k}")
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            sin_floats(v, f"{ruta}[{i}]")


def jsonb(valor):
    """Serialización estable de los archivos de salida: claves ordenadas,
    separadores fijos, UTF-8, sin salto de línea final."""
    sin_floats(valor)
    return json.dumps(valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compact(valor):
    # Idéntica a `compact` de agent_evidence_vectors.w3creport (0.17.4): claves
    # ordenadas, separadores sin espacio y ASCII por defecto. Es una copia y no
    # un import porque el paquete no es dependencia de este repositorio.
    return json.dumps(valor, sort_keys=True, separators=(",", ":")).encode("utf-8")


def flat_root(hojas):
    # Idéntica a `flat_root` de w3creport: SHA-256 de la concatenación de los
    # digests CRUDOS (no el hex) de cada hoja, en el orden de la lista.
    return sha(b"".join(hashlib.sha256(h).digest() for h in hojas))


def etiquetas(errores):
    # Idéntica a `rule_labels` de src/disensor/vectors.py, copiada como en
    # tools/barrido-reglas.py.
    tags = set()
    for e in errores:
        if e.startswith("[") and "]" in e:
            tags.add(e[1:e.index("]")])
    return sorted(tags)


def cambia(esperado, errores):
    """El veredicto o la lista de etiquetas no son los que declara el vector."""
    return ((not errores) != esperado.get("valid")
            or etiquetas(errores) != (esperado.get("rules") or []))


def cambia_observado(antes, despues):
    """El veredicto o la lista de etiquetas cambian entre dos salidas."""
    return (not antes) != (not despues) or etiquetas(antes) != etiquetas(despues)


def flat(o, p=''):
    # Copia de `flat` de tools/medir-parejas.py; tienen que ser idénticas.
    d = {}
    if isinstance(o, dict):
        for k, v in o.items(): d.update(flat(v, f'{p}/{k}'))
    elif isinstance(o, list):
        for i, v in enumerate(o): d.update(flat(v, f'{p}/{i}'))
    else:
        d[p] = o
    return d


def dif(a, b):
    # Copia de `dif` de tools/medir-parejas.py; tienen que ser idénticas.
    return [k for k in set(a) | set(b) if a.get(k) != b.get(k)]


def valor_compacto(plano, clave):
    if clave not in plano:
        return "absent"
    return json.dumps(plano[clave], separators=(",", ":"), ensure_ascii=False)


def registro(fuente):
    """Las etiquetas que rules.py puede emitir, leídas de la fuente como en
    tests/test_rule_coverage.py y tools/barrido-reglas.py, más `schema`."""
    entrecomilladas = set(re.findall('"(R[0-9]+)"', fuente))
    sueltas = set(re.findall("(?<![A-Za-z0-9_])R[0-9]+(?![A-Za-z0-9_])", fuente))
    if not sueltas <= entrecomilladas:
        sys.exit(f"rules.py nombra {sorted(sueltas - entrecomilladas)} fuera de un literal "
                 "entre comillas dobles: el registro solo ve los literales.")
    return sorted(entrecomilladas, key=lambda r: int(r[1:])) + ["schema"]


def lee_el_reloj(fuente):
    for linea in fuente.splitlines():
        s = linea.strip()
        for mod in ("datetime", "time"):
            if s.startswith(f"import {mod}") or s.startswith(f"from {mod} ") or s.startswith(f"from {mod}."):
                return s
    return None


def main():
    ap = argparse.ArgumentParser(
        description="Emite la corrida de .residue/ como reportes v0.1 y los MUST-FAIL como registros 5.5.")
    ap.add_argument("--runner", required=True, help="quien corre; entra solo en control-results.json")
    ap.add_argument("salida", nargs="?", default="salida-55", help="directorio de salida (default: salida-55)")
    args = ap.parse_args()
    destino_seguro(args.salida)

    # El autochequeo de la reimplementación del lector: el miembro
    # v49afe44cc51bc376 del corpus vectors-w3c-report (0.17.4) declara este
    # check-set para estos dos checks.
    muestra = [{"check": "c-pass", "state": "pass"}, {"check": "c-pass-2", "state": "pass"}]
    if flat_root([compact(c) for c in muestra]) != "8a8adb210aa791950621c552e16945631d42d18f092c84f8c39f9204996b7ca7":
        sys.exit("flat_root no reproduce el check-set del miembro v49afe44cc51bc376 del corpus")

    commit = git("rev-parse", "HEAD").strip()
    if len(commit) != 40:
        sys.exit(f"commit raro: {commit!r}")
    fecha = git("show", "-s", "--format=%cs", commit).strip()
    modificados = git("status", "--porcelain", "--untracked-files=no").strip()
    sueltos = [l[3:] for l in git("status", "--porcelain").splitlines() if l.startswith("?? ")]

    print(f"commit: {commit}")
    print(f"python: {platform.python_version()}")
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

    # El validador del commit: su fuente, su registro y sus esquemas.
    fuente_rules = blob(commit, "src/disensor/rules.py")
    texto_rules = fuente_rules.decode("utf-8")
    reloj = lee_el_reloj(texto_rules)
    if reloj:
        sys.exit(f"rules.py lee el reloj en este commit ({reloj}): summary.json ya no puede decir que no.")
    reg = registro(texto_rules)
    if set(reg) != set(ETIQUETAS_POR_VERSION["v0.4"]):
        sys.exit(f"el registro de rules.py {reg} no coincide con la tabla por version del script: "
                 "hay que revisar ETIQUETAS_POR_VERSION y applies_from.")
    sha_esquemas = {n: sha(blob(commit, f"src/disensor/{n}")) for n in ESQUEMAS}
    licencia = blob(commit, "LICENSE").decode("utf-8").splitlines()[0].strip()
    cobertura = json.loads(blob(commit, "spec/rule_coverage.json").decode("utf-8"))

    configs = {}
    config_digest = {}
    for suite in SUITES:
        cfg = {"checker": CHECKER, "schema": VERSIONES[suite],
               "schema_sha256": sha_esquemas[f"residue.schema.{suite}.json"]}
        configs[suite] = jsonb(cfg)
        config_digest[suite] = sha(configs[suite])

    # Los vectores, en el orden de cada index.json, leídos del commit.
    vectores = []
    for suite in SUITES:
        indice = json.loads(blob(commit, f"spec/vectors/{suite}/index.json").decode("utf-8"))
        if indice.get("schema") != VERSIONES[suite]:
            sys.exit(f"spec/vectors/{suite}/index.json declara {indice.get('schema')!r}")
        for nombre in indice["vectors"]:
            ruta = f"spec/vectors/{suite}/{nombre}.json"
            datos = blob(commit, ruta)
            v = json.loads(datos.decode("utf-8"))
            artefacto = v.get("artifact") or {}
            if artefacto.get("schema") != VERSIONES[suite]:
                sys.exit(f"{ruta}: el artefacto declara {artefacto.get('schema')!r} en la suite {suite}")
            vectores.append({
                "suite": suite, "nombre": nombre, "ruta": ruta, "sha256": sha(datos),
                "esperado": v.get("expected") or {}, "errores": validate_artifact(artefacto),
                "plano": flat(artefacto),
            })

    base = [f"{x['suite']}/{x['nombre']}" for x in vectores if cambia(x["esperado"], x["errores"])]
    must_fail = [x for x in vectores if not x["esperado"].get("valid")]
    print(f"{len(vectores)} vectores, {len(must_fail)} MUST-FAIL "
          f"({sum(1 for x in must_fail if x['esperado'].get('rules') == ['schema'])} de esquema, "
          f"{sum(1 for x in must_fail if x['esperado'].get('rules') != ['schema'])} de regla), "
          f"{len(base)} desacuerdos de base")
    for n in base:
        print(f"    {n}")
    if base:
        sys.exit("hay desacuerdos de base: no se escribe nada.")

    # Registros 5.5: un MUST-FAIL que dispara una sola etiqueta. Los de dos o
    # más quedan listados en summary.json (D3).
    fixtures = []
    excluidos = []
    for x in must_fail:
        reglas = x["esperado"].get("rules") or []
        if len(reglas) == 1:
            fixtures.append(dict(x, etiqueta=reglas[0], fixture_id=f"disensor/{x['suite']}/{x['nombre']}"))
        else:
            excluidos.append({"vector": f"{x['suite']}/{x['nombre']}", "rules": reglas})
    fixtures.sort(key=lambda f: f["fixture_id"])

    # Gemelo a un campo: el primer MUST-PASS de la misma suite, en el orden
    # del index.json, cuyo artefacto aplanado difiere en exactamente un campo.
    con_gemelo = 0
    con_mas_de_uno = 0
    for f in fixtures:
        candidatos = [p for p in vectores
                      if p["suite"] == f["suite"] and p["esperado"].get("valid")
                      and len(dif(p["plano"], f["plano"])) == 1]
        f["gemelo"] = candidatos[0] if candidatos else None
        con_gemelo += bool(candidatos)
        con_mas_de_uno += len(candidatos) > 1

    # Aislamiento sobre los registros: relajar una etiqueta de regla por vez y
    # comparar con lo observado sin relajar.
    etiquetas_con_registro = [e for e in reg if any(f["etiqueta"] == e for f in fixtures)]
    aislamiento = []
    print()
    print("etiqueta  nombran  cambian")
    for e in etiquetas_con_registro:
        if e == "schema":
            continue
        nombran = sorted(f["fixture_id"] for f in fixtures if f["etiqueta"] == e)
        cambian = sorted(f["fixture_id"] for f in fixtures
                         if cambia_observado(f["errores"], [x for x in f["errores"] if not x.startswith(f"[{e}]")]))
        aislamiento.append({"relaxed_rule": e, "named": nombran, "flipped": cambian,
                            "unchanged_count": len(fixtures) - len(cambian)})
        print(f"{e:8}  {len(nombran):7}  {len(cambian):7}  {'exacta' if cambian == nombran else 'NO EXACTA'}")
    exactas = sum(1 for a in aislamiento if a["flipped"] == a["named"])
    print(f"etiquetas de regla con registros: {len(aislamiento)}, exactas: {exactas}")
    isolation_bytes = jsonb({"commit": commit, "fixtures": len(fixtures), "rules": aislamiento})
    isolation_sha = sha(isolation_bytes)
    por_etiqueta = {a["relaxed_rule"]: a for a in aislamiento}

    registros = []
    resultados = []
    for f in fixtures:
        url = f"{RAW}/{commit}/{f['ruta']}"
        if f["etiqueta"] == "schema":
            primero = next(x for x in f["errores"] if x.startswith("[schema] "))
            donde = primero[len("[schema] "):].split(": ", 1)[0]
            why = f"The artifact is invalid against the {VERSIONES[f['suite']]} schema at {donde}."
        else:
            why = WHY[f["etiqueta"]]
        r = {
            "fixture_id": f["fixture_id"],
            "target_check": {"check_id": f["etiqueta"], "checker_revision": commit,
                             "config_digest": config_digest[f["suite"]]},
            "input": {"ref": url, "sha256": f["sha256"]},
            "expected": {"state": "fail", "rule": f["etiqueta"]},
            "why_must_fail": why,
            "provenance": {"author": AUTOR, "created": fecha, "source": url, "license": licencia},
        }
        if f["gemelo"]:
            g = f["gemelo"]
            clave = dif(g["plano"], f["plano"])[0]
            r["derived_from"] = {
                "ref": f"{RAW}/{commit}/{g['ruta']}", "sha256": g["sha256"],
                "change": f"{clave}: {valor_compacto(g['plano'], clave)} -> {valor_compacto(f['plano'], clave)}",
            }
        if f["etiqueta"] != "schema":
            a = por_etiqueta[f["etiqueta"]]
            r["isolation"] = {"relaxed_rule": a["relaxed_rule"], "flipped": a["flipped"],
                              "unchanged_count": a["unchanged_count"],
                              "evidence": {"ref": "isolation.json", "sha256": isolation_sha}}
        registros.append(r)
        resultados.append({
            "fixture_id": f["fixture_id"], "checker_revision": commit,
            "config_digest": config_digest[f["suite"]],
            "state": "fail" if f["errores"] else "pass", "rules": etiquetas(f["errores"]),
            "runner": args.runner,
        })

    por_suite = {s: {} for s in SUITES}
    for f in fixtures:
        por_suite[f["suite"]][f["etiqueta"]] = por_suite[f["suite"]].get(f["etiqueta"], 0) + 1
    por_etiqueta_total = {}
    for f in fixtures:
        por_etiqueta_total[f["etiqueta"]] = por_etiqueta_total.get(f["etiqueta"], 0) + 1
    print()
    print(f"registros 5.5: {len(fixtures)} ("
          + ", ".join(f"{s}: {sum(por_suite[s].values())}" for s in SUITES) + "); "
          f"excluidos por mas de una regla: {len(excluidos)}")
    for s in SUITES:
        print(f"  {s}: " + ", ".join(f"{e} {por_suite[s][e]}" for e in reg if e in por_suite[s]))
    for ex in excluidos:
        print(f"  excluido {ex['vector']}: {ex['rules']}")
    print(f"con derived_from (gemelo a un campo): {con_gemelo} de {len(fixtures)}; "
          f"con mas de un candidato: {con_mas_de_uno}")

    # Las declaraciones del commit, agrupadas por la versión que declaran.
    rutas = [p for p in git("ls-tree", "-r", "-z", "--name-only", commit, "--", ".residue").split(NUL)
             if p.endswith(".json")]
    declaraciones = {s: [] for s in SUITES}
    fallidas = []
    vistos = set()
    for p in sorted(rutas):
        d = json.loads(blob(commit, p).decode("utf-8"))
        version = d.get("schema") if isinstance(d, dict) else None
        suite = next((s for s in SUITES if VERSIONES[s] == version), None)
        if suite is None:
            sys.exit(f"{p} declara {version!r}, que no es ninguna de {list(VERSIONES.values())}")
        eid = d["event"]["event_id"]
        if eid in vistos:
            sys.exit(f"event_id repetido: {eid}")
        vistos.add(eid)
        errores = validate_artifact(d)
        if errores:
            fallidas.append((p, errores))
        declaraciones[suite].append((eid, errores))
    print()
    print(f"{sum(len(v) for v in declaraciones.values())} declaraciones ("
          + ", ".join(f"{s}: {len(declaraciones[s])}" for s in SUITES) + f"), {len(fallidas)} no validan")
    for p, errores in fallidas:
        print(f"  {p}")
        for e in errores:
            print(f"    {e}")
    if fallidas:
        sys.exit("hay declaraciones que no validan: no se escribe nada.")

    reportes = {}
    resumen_versiones = {}
    for suite in SUITES:
        if not declaraciones[suite]:
            sys.exit(f"ninguna declaracion de {VERSIONES[suite]}: el reporte no tendria checks.")
        etiquetas_version = ETIQUETAS_POR_VERSION[suite]
        con_control = [e for e in etiquetas_version if e in por_suite[suite]]
        checks = []
        for eid, errores in declaraciones[suite]:
            disparadas = set(etiquetas(errores))
            for e in etiquetas_version:
                checks.append({"check": f"{eid}/{e}", "state": "fail" if e in disparadas else "pass"})
        checks.sort(key=lambda c: c["check"])
        fixed = {"checker": f"{CHECKER}@{commit}", "constraint-set": VERSIONES[suite]}
        n_pass = sum(1 for c in checks if c["state"] == "pass")
        n_fail = len(checks) - n_pass
        control = sorted(c["check"] for c in checks if c["check"].rsplit("/", 1)[1] in con_control)
        reportes[suite] = {
            "format": FORMATO,
            "fixed": fixed,
            "domain": {"id": f"d-disensor-residue-{suite}",
                       "description": f"the residue declarations under .residue/ at {commit} "
                                      f"that declare schema {VERSIONES[suite]}"},
            "checks": checks,
            "check-set": {"leaf-count": len(checks), "tree-shape": "flat",
                          "sha256": flat_root([compact(c) for c in checks])},
            "roll-up": {
                "declared": len(checks), "exercised": len(checks),
                "pass": n_pass, "fail": n_fail, "inconclusive": 0, "void": 0, "not-exercised": 0,
                "carried": 0, "referenced": 0,
                "negative-capable": {"kind": "control-failed",
                                     "control": {"checks": control, "fixed": dict(fixed), "state": "fail"}},
            },
        }
        resumen_versiones[VERSIONES[suite]] = {
            "declarations": len(declaraciones[suite]),
            "checks": len(checks),
            "labels_with_control": con_control,
            "labels_without_control": [e for e in etiquetas_version if e not in por_suite[suite]],
        }
        print(f"  {VERSIONES[suite]}: {len(checks)} checks, {len(control)} bajo control; "
              f"sin control: {', '.join(resumen_versiones[VERSIONES[suite]]['labels_without_control']) or 'ninguna'}")

    resumen = {
        "commit": commit,
        "python": platform.python_version(),
        "jsonschema": importlib.metadata.version("jsonschema"),
        "rules_sha256": sha(fuente_rules),
        "schemas_sha256": sha_esquemas,
        "clock": "not read by the checker",
        "versions": resumen_versiones,
        "fixtures": {
            "total": len(fixtures),
            "schema": sum(1 for f in fixtures if f["etiqueta"] == "schema"),
            "rule": sum(1 for f in fixtures if f["etiqueta"] != "schema"),
            "by_suite": {s: {"total": sum(por_suite[s].values()), "by_label": por_suite[s]} for s in SUITES},
            "by_label": por_etiqueta_total,
            "with_derived_from": con_gemelo,
            "with_more_than_one_candidate_twin": con_mas_de_uno,
        },
        "excluded": excluidos,
        "no_control": {
            "exempt": [{"rule": x["rule"], "reason": x["reason"]} for x in cobertura.get("exempt", [])],
            "by_version": {v: r["labels_without_control"] for v, r in resumen_versiones.items()},
        },
    }

    readme = NL.join([
        f"disensor: v0.1 reports and section 5.5 records, emitted at commit {commit}",
        "",
        "Contents",
        "  configs/residue-v0.X.json   validator configuration per schema version; its sha256 is the config_digest",
        "  run-residue-v0.X.json       one public-agent-conformance/report/v0.1 report per schema version",
        "  fixtures.json               the 5.5 records: one per MUST-FAIL vector that fires a single label",
        "  control-results.json        what validate_artifact returned for each record in this run",
        "  isolation.json              the 0013 sweep applied to the 5.5 records",
        "  summary.json                commit, versions, counts, exclusions and labels without control",
        "  SHA256SUMS                  one line per file above, sorted by path",
        "",
        "Regenerate (byte-identical SHA256SUMS for the same commit, runner, Python and jsonschema versions;",
        "summary.json records the versions, so another environment changes that file and the final sum only):",
        f"  git worktree add <dir> {commit}",
        "  cd <dir>",
        f"  python3 tools/emitir-55.py --runner {json.dumps(args.runner, ensure_ascii=False)} <output_dir>",
        "",
        "Limits",
        "  - One author wrote the corpus, the validator, the expected rules and the emitter, and the",
        "    expected rules were in view before running. Every run is by the same author: this is not",
        "    the two-party case of O8.",
        "  - Isolation relaxes the validator's output, not its code. For the rules that equals the rule",
        "    not firing (rule_errors evaluates all of them with no early returns); for the schema it does",
        "    not (validate_artifact returns before the rules), so schema records carry no isolation block.",
        "  - The three vectors that fire two rules are not written as 5.5 records; see summary.json.",
        "  - R3 and R8 have no control: the schema forbids the condition they test (spec/rule_coverage.json,",
        "    proven in both directions by the Python reference and the TypeScript port). Their checks stay",
        "    pass with unknown qualifiers.",
        "  - The v0.2 suite gives control only for R0, R4, R6 and the schema.",
        "  - The checker is the code at the commit plus Python and jsonschema, at the versions summary.json",
        "    records. The validator does not read the clock.",
        "  - The checks on the checkout are snapshots, not barriers: they do not cover a hostile file system",
        "    (bytecode in __pycache__ stamped like the source, or an altered interpreter or jsonschema outside",
        "    the repository).",
        "  - check-set uses tree-shape flat as the reference reader computes it (sha256 over the",
        "    concatenated raw sha256 digests of each compact check); the text does not fix the tree yet (O3).",
        "",
    ]).encode("utf-8")

    archivos = {f"configs/residue-{s}.json": configs[s] for s in SUITES}
    archivos.update({f"run-residue-{s}.json": jsonb(reportes[s]) for s in SUITES})
    archivos["fixtures.json"] = jsonb(registros)
    archivos["control-results.json"] = jsonb(resultados)
    archivos["isolation.json"] = isolation_bytes
    archivos["summary.json"] = jsonb(resumen)
    archivos["README.txt"] = readme
    sumas = (NL.join(f"{sha(archivos[r])}  {r}" for r in sorted(archivos)) + NL).encode("utf-8")
    archivos["SHA256SUMS"] = sumas
    if set(archivos) != set(EMITIDOS):
        sys.exit("la lista EMITIDOS no coincide con lo que se escribe: hay que actualizarla.")

    mismo_checker(commit, {
        os.path.join("src", "disensor", n): sha(normaliza(blob(commit, f"src/disensor/{n}")))
        for n in ("rules.py",) + ESQUEMAS
    })
    os.makedirs(os.path.join(args.salida, "configs"), exist_ok=True)
    for ruta, datos in archivos.items():
        with open(os.path.join(args.salida, *ruta.split("/")), "wb") as fh:
            fh.write(datos)
    print()
    print(f"escrito en {args.salida.replace(os.sep, '/')}/ ({len(archivos)} archivos)")
    print(f"sha256 de SHA256SUMS: {sha(sumas)}")


if __name__ == "__main__":
    main()

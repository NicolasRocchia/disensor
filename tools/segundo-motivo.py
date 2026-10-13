#!/usr/bin/env python3
"""Mide el segundo motivo de rechazo de los MUST-FAIL de `spec/vectors/` que
`tools/emitir-55.py` escribe como registros 5.5: si un control de regla tiene
otro motivo además de su regla, y si un control de esquema seguiría rechazado
por alguna regla si no existiera la capa de esquema. Es el script detrás del
37/24 (10) dado en public-agent-conformance@w3.org como ejemplo del criterio 11
de los criterios de admisión v2.1.

Measures the second reason for rejection of the MUST-FAIL vectors of
`spec/vectors/` that `tools/emitir-55.py` writes as section 5.5 records: whether
a rule control has another reason besides its rule, and whether a schema
control would still be rejected by some rule if the schema layer did not
exist. It is the script behind the 37/24 (10) given on
public-agent-conformance@w3.org as the example of criterion 11 of the v2.1
admission criteria.

Correr desde la raíz del repositorio / run from the repository root:

    python3 -P tools/segundo-motivo.py [directorio_de_salida | output_dir]

Qué mide. Sobre los MUST-FAIL de las tres suites (`spec/vectors/v0.2`, `v0.3` y
`v0.4`, en el orden de cada `index.json`), los mismos que emitir-55 escribe
como registros 5.5:

- Los vectores que no nombran una sola etiqueta en `expected.rules` van aparte,
  como excluidos, con sus etiquetas: un registro 5.5 nombra una sola regla.
- Controles de regla (etiqueta `R<n>`): `validate_artifact` sobre el artefacto,
  las etiquetas observadas y si son exactamente la esperada. Sin segundo motivo
  quiere decir que, sacando de la salida los errores `[<etiqueta>]`, no queda
  ningún error.
- Controles de esquema (etiqueta `schema`): cuántos errores de esquema da
  `validate_artifact` y, con `rules.rule_errors` llamado directo, las etiquetas
  de regla que da, o el nombre de la excepción si la lanza. Ese es el segundo
  motivo detrás de la capa de esquema.

Imprime el commit, las versiones de Python y `jsonschema` y las cuentas por
suite y en total, y escribe `segundo-motivo.json` en el directorio de salida
(por defecto ./salida-segundo-motivo/, que está en .gitignore), y nada más,
tampoco bytecode. El JSON es estable byte a byte: claves ordenadas, separadores
fijos, UTF-8, sin salto de línea final, listas ordenadas, sin floats. Dos
corridas en el mismo commit dan el mismo sha256, que el script imprime al
final. Las versiones de Python y `jsonschema` no entran al JSON: otro entorno
cambia el sha256 solo si cambia lo que da el validador.

Corre sobre el checkout, con las mismas negativas que emitir-55. Se niega si
este no es el tools/segundo-motivo.py del directorio actual, si algún
directorio del repositorio está en `sys.path` (hay que correrlo con `-P`,
Python 3.11 o más: sin eso Python antepone `tools/` a la ruta de importación),
si hay algo sin versionar o ignorado bajo `src/`, de donde importa el
validador, si hay archivos versionados modificados, o si el destino es un
enlace, está dentro del repositorio y git no lo ignora (mirado en la ruta
resuelta, que es donde cae la escritura), o ya existe con archivos que este
script no escribe o con enlaces. Qué cae dentro del repositorio, para la ruta
de importación y para el destino, se decide por identidad de archivo y no por
el texto de la ruta: así una ruta extendida o UNC de Windows no pasa por de
afuera. Lee vectores e índices de los objetos de git
del commit, resuelto una vez al empezar y nunca por el nombre HEAD, e importa
`disensor.rules` del checkout, verificando que viene de
`src/disensor/rules.py` (y `jsonschema` de fuera de él). Antes de escribir
vuelve a mirar: HEAD sigue en ese commit, el árbol sigue limpio y `rules.py` y
los esquemas del checkout, que es de donde carga `validate_artifact`, son los
del commit.

Límites:

- `rule_errors` se llama fuera de su contrato. El validador nunca corre las
  reglas cuando falla el esquema (`validate_artifact` devuelve antes). Una
  etiqueta en `rules_behind` dice qué hace la capa de reglas con esos bytes, no
  lo que el validador promete. Si alguna regla lanza una excepción sobre un
  artefacto que no pasa el esquema, se registra y no se cuenta como regla
  detrás.
- Lo que esto muestra, en el vocabulario del criterio 11: comparando solo el
  estado, esos controles de esquema esconden un segundo motivo; si se compara
  el resultado nativo completo, el segundo motivo aparece porque la etiqueta
  pasa de `schema` a una regla.
- Un solo autor escribió el corpus, el validador y este script, con las
  respuestas a la vista.
- Procedencia: la regla del segundo motivo es de Lars Kroehl en la lista
  (12/10); el texto del criterio 11 que la recoge es de Nicholas Templeman;
  Guigui Wang pidió fijar este caso como ejemplo de la v2.1.
- Las miradas al checkout y al directorio de salida son instantáneas, no
  barreras: no cubren un sistema de archivos hostil (bytecode en `__pycache__`
  con la misma marca que la fuente, un intérprete o un `jsonschema` alterados
  fuera del repositorio, o un enlace plantado entre la mirada y la escritura).

What it measures. Over the MUST-FAIL vectors of the three suites
(`spec/vectors/v0.2`, `v0.3` and `v0.4`, in the order of each `index.json`),
the same ones emitir-55 writes as 5.5 records:

- The vectors that do not name a single label in `expected.rules` are set
  apart, as excluded, with their labels: a 5.5 record names a single rule.
- Rule controls (label `R<n>`): `validate_artifact` over the artifact, the
  observed labels and whether they are exactly the expected one. No second
  reason means that, once the `[<label>]` errors are dropped from the output,
  no error is left.
- Schema controls (label `schema`): how many schema errors `validate_artifact`
  returns and, with `rules.rule_errors` called directly, the rule labels it
  returns, or the name of the exception if it raises one. That is the second
  reason behind the schema layer.

It prints the commit, the Python and `jsonschema` versions and the counts per
suite and in total, and writes `segundo-motivo.json` to the output directory
(./salida-segundo-motivo/ by default, which is in .gitignore), and nothing
else, not even bytecode. The JSON is byte-stable: sorted keys, fixed
separators, UTF-8, no trailing newline, sorted lists, no floats. Two runs on
the same commit give the same sha256, which the script prints last. The Python
and `jsonschema` versions do not go into the JSON: another environment changes
the sha256 only if it changes what the validator returns.

It runs on the checkout, with the same refusals as emitir-55. It refuses if
this is not the tools/segundo-motivo.py of the current directory, if any
repository directory is on `sys.path` (it has to run with `-P`, Python 3.11 or
newer: without it Python prepends `tools/` to the import path), if anything
untracked or ignored sits under `src/`, where the validator is imported from,
if tracked files are modified, or if the destination is a link, is inside the
repository and git does not ignore it (checked on the resolved path, which is
where the write lands), or already exists holding files this script does not
write or links. What falls inside the repository, for the import path and for
the destination, is decided by file identity and not by the text of the path,
so a Windows extended or UNC path does not pass for an outside one. It reads
vectors and indexes from the git objects of the
commit, resolved once at the start and never through the name HEAD, and
imports `disensor.rules` from the checkout, checking that it comes from
`src/disensor/rules.py` (and `jsonschema` from outside it). Before writing it
looks again: HEAD is still that commit, the tree is still clean, and
`rules.py` and the schemas in the checkout, which is where `validate_artifact`
loads them from, are the commit's.

Limits:

- `rule_errors` is called outside its contract. The validator never runs the
  rules when the schema fails (`validate_artifact` returns before). A label in
  `rules_behind` says what the rule layer does with those bytes, not what the
  validator promises. If a rule raises an exception on an artifact that does
  not pass the schema, it is recorded and not counted as a rule behind.
- What this shows, in the vocabulary of criterion 11: comparing the state
  alone, those schema controls hide a second reason; comparing the full native
  result, the second reason shows because the label moves from `schema` to a
  rule.
- One author wrote the corpus, the validator and this script, with the answers
  in view.
- Provenance: the second-reason rule is Lars Kroehl's on the list (12/10); the
  text of criterion 11 that takes it up is Nicholas Templeman's; Guigui Wang
  asked to pin this case as an example for v2.1.
- The looks at the checkout and at the output directory are snapshots, not
  barriers: they do not cover a hostile file system (bytecode in `__pycache__`
  stamped like the source, an altered interpreter or `jsonschema` outside the
  repository, or a link planted between the look and the write).
"""
import os
import sys


_RAIZ = os.path.realpath(os.getcwd())
_ST_RAIZ = os.stat(_RAIZ)
_ID_RAIZ = (_ST_RAIZ.st_dev, _ST_RAIZ.st_ino)
if not _ST_RAIZ.st_ino:
    sys.exit("el sistema de archivos no da una identidad estable para el directorio actual: "
             "no puedo saber que rutas caen dentro del repositorio")


def bajo_la_raiz(ruta):
    """Si la ruta cae dentro de la raíz del repositorio, su ruta relativa con
    barras `/` ("" para la raíz misma); si no, None. Se decide por identidad
    de archivo (volumen e índice) del primer ancestro existente que coincida, y
    no por el texto: en Windows la misma carpeta se escribe con letra de
    unidad, en el espacio de rutas extendidas o por un recurso UNC, y
    `commonpath` da ValueError entre dos escrituras distintas como si fueran
    discos distintos, con lo que una ruta del checkout pasaba por de afuera."""
    actual = os.path.abspath(ruta)
    cola = []
    while True:
        try:
            st = os.stat(actual)
        except OSError:
            st = None
        if st is not None and (st.st_dev, st.st_ino) == _ID_RAIZ:
            return "/".join(reversed(cola))
        padre, nombre = os.path.split(actual)
        if padre == actual or not nombre:
            return None
        cola.append(nombre)
        actual = padre


# Antes de cualquier otro import, con os y sys solos, que ya estaban cargados al
# arrancar y no se pueden sombrear desde el repositorio: ningún directorio del
# repositorio puede estar en la ruta de importación salvo el src/ que este
# script agrega más abajo. Al correr `python tools/segundo-motivo.py`, Python
# antepone tools/ a sys.path, y un módulo suelto ahí (un tools/attrs.py, por
# ejemplo) correría en lugar de la dependencia instalada antes de que ninguna
# guarda lo viera. Con `-P` (Python 3.11 o más) el directorio del script no
# entra. Lo que se imprime va en ASCII, para que una salida redirigida no
# dependa de la página de códigos de quien reproduce.
if os.path.realpath(__file__) != os.path.realpath(os.path.join(_RAIZ, "tools", "segundo-motivo.py")):
    sys.exit("este script tiene que ser el tools/segundo-motivo.py del directorio actual, "
             "y el directorio actual la raiz del repositorio")
_dentro = [p for p in sys.path if p and bajo_la_raiz(os.path.realpath(p)) is not None]
if _dentro:
    sys.exit("hay directorios del repositorio en la ruta de importacion de Python (" + ", ".join(_dentro)
             + "): correr con `python -P tools/segundo-motivo.py ...` (Python 3.11 o mas) "
             "y sin PYTHONPATH que apunte al repositorio.")

import argparse            # noqa: E402
import hashlib             # noqa: E402
import importlib.metadata  # noqa: E402
import json                # noqa: E402
import platform            # noqa: E402
import stat                # noqa: E402
import subprocess          # noqa: E402

if not os.path.isfile(os.path.join("src", "disensor", "rules.py")):
    sys.exit("no encuentro src/disensor/rules.py: el directorio actual tiene que ser el del repositorio")


def git(*args, binario=False):
    r = subprocess.run(["git", "--no-optional-locks", *args], capture_output=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout if binario else r.stdout.decode("utf-8")


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
from disensor.rules import rule_errors, validate_artifact  # noqa: E402

# De dónde se importó lo que va a correr: el validador, del checkout; su
# dependencia, de fuera de él.
if os.path.realpath(disensor.rules.__file__) != os.path.realpath(os.path.join("src", "disensor", "rules.py")):
    sys.exit(f"disensor.rules se importo de {disensor.rules.__file__} y no del checkout")
if bajo_la_raiz(os.path.realpath(jsonschema.__file__)) is not None:
    sys.exit(f"jsonschema se importo desde el checkout ({jsonschema.__file__}) y no del entorno")

SUITES = ("v0.2", "v0.3", "v0.4")
VERSIONES = {s: f"residue/{s}" for s in SUITES}
ESQUEMAS = ("residue.schema.json", "residue.schema.v0.2.json",
            "residue.schema.v0.3.json", "residue.schema.v0.4.json")
JSON_SALIDA = "segundo-motivo.json"
EMITIDOS = (JSON_SALIDA,)


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


def es_enlace(ruta):
    """Enlace simbólico, junction u otro punto de reanálisis de Windows, o un
    archivo con más de un nombre (enlace duro): escribir ahí sale del
    directorio que se revisó, o pisa un archivo que vive en otro lado."""
    if os.path.islink(ruta):
        return True
    st = os.lstat(ruta)
    if getattr(st, "st_reparse_tag", 0) or (getattr(st, "st_file_attributes", 0)
                                            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        return True
    return stat.S_ISREG(st.st_mode) and st.st_nlink > 1


def destino_seguro(salida):
    """El directorio de salida está fuera del repositorio o git lo ignora, y si
    ya existe solo tiene lo que este script emite, sin enlaces de ninguna
    clase: se sobreescribe la salida de una corrida anterior y nada más. Así
    `.` o `tools` no siembran archivos en el checkout, un directorio ajeno no
    pierde lo que tenía, y un `segundo-motivo.json` que sea enlace no redirige
    la escritura fuera de lo revisado. El destino mismo tampoco puede ser un
    enlace, y las preguntas se hacen sobre la ruta resuelta, que es donde cae
    la escritura: una junction llamada `salida-segundo-motivo` que apunte a un
    directorio no ignorado del checkout pasaba la pregunta a git por su nombre
    y sembraba el archivo del otro lado."""
    if os.path.lexists(salida) and es_enlace(os.path.abspath(salida)):
        sys.exit(f"{salida} es un enlace (simbolico o junction): usa el directorio al que apunta o otro.")
    real = os.path.realpath(salida)
    rel = bajo_la_raiz(real)
    if rel is not None:
        # Se pregunta por un hijo del destino resuelto y no por el destino: así
        # una regla de directorio como `salida-segundo-motivo/` lo alcanza
        # aunque el directorio no exista todavía, y un destino que git no
        # ignora da 1 exista o no. Resuelto, porque un enlace en el camino
        # cambia dónde se escribe y no el nombre que git ve.
        hijo = f"{rel}/{JSON_SALIDA}" if rel else JSON_SALIDA
        r = subprocess.run(["git", "--no-optional-locks", "check-ignore", "-q", "--", hijo],
                           capture_output=True)
        if r.returncode != 0:
            sys.exit(f"{salida} esta dentro del repositorio y git no lo ignora: "
                     "usa un directorio ignorado (salida-segundo-motivo/) o uno fuera del repositorio.")
    if os.path.isdir(real):
        permitidos = set(EMITIDOS)
        presentes = set()
        enlaces = []
        for raiz, dirs, archivos in os.walk(real):
            for n in dirs + archivos:
                ruta = os.path.join(raiz, n)
                rel = os.path.relpath(ruta, real).replace(os.sep, "/")
                presentes.add(rel)
                if es_enlace(ruta):
                    enlaces.append(rel)
        if enlaces:
            sys.exit(f"{salida} tiene enlaces (simbolicos, junctions o duros): {', '.join(enlaces[:5])}"
                     f"{', ...' if len(enlaces) > 5 else ''}. Escribir ahi saldria del directorio revisado. "
                     "Vaciarlo o elegir otro.")
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
        sys.exit(f"float en {ruta}: la salida no lleva floats")
    if isinstance(valor, dict):
        for k, v in valor.items():
            sin_floats(v, f"{ruta}.{k}")
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            sin_floats(v, f"{ruta}[{i}]")


def jsonb(valor):
    """Serialización estable de la salida: claves ordenadas, separadores fijos,
    UTF-8, sin salto de línea final."""
    sin_floats(valor)
    return json.dumps(valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def etiquetas(errores):
    # Idéntica a `rule_labels` de src/disensor/vectors.py, copiada como en
    # tools/barrido-reglas.py.
    tags = set()
    for e in errores:
        if e.startswith("[") and "]" in e:
            tags.add(e[1:e.index("]")])
    return sorted(tags)


def corto(fixture_id):
    """`disensor/v0.3/vector` -> `v0.3/vector`, para la pantalla."""
    return fixture_id.split("/", 1)[1]


def por_suite(controles):
    """`total (v0.2 n, v0.3 n, v0.4 n)` para la pantalla."""
    return (f"{len(controles)} ("
            + ", ".join(f"{s} {sum(1 for t, _ in controles if t == s)}" for s in SUITES) + ")")


def cuentas(excluidos, de_regla, de_esquema):
    return {
        "excluded": len(excluidos),
        "rule_controls": len(de_regla),
        "rule_controls_matching_expected": sum(1 for c in de_regla if c["matches_expected"]),
        "rule_controls_without_second_motive": sum(1 for c in de_regla if not c["second_motive"]),
        "schema_controls": len(de_esquema),
        "schema_controls_with_one_schema_error": sum(1 for c in de_esquema if c["schema_errors"] == 1),
        "schema_controls_with_rules_behind": sum(1 for c in de_esquema if c.get("rules_behind")),
        "schema_controls_without_rules_behind": sum(1 for c in de_esquema if c.get("rules_behind") == []),
        "schema_controls_with_exception": sum(1 for c in de_esquema if "exception" in c),
    }


def main():
    ap = argparse.ArgumentParser(
        description="Mide el segundo motivo de rechazo de los MUST-FAIL que emitir-55 escribe como registros 5.5.")
    ap.add_argument("salida", nargs="?", default="salida-segundo-motivo",
                    help="directorio de salida (default: salida-segundo-motivo)")
    args = ap.parse_args()
    destino_seguro(args.salida)

    commit = git("rev-parse", "HEAD").strip()
    if len(commit) != 40:
        sys.exit(f"commit raro: {commit!r}")
    modificados = git("status", "--porcelain", "--untracked-files=no").strip()
    sueltos = [l[3:] for l in git("status", "--porcelain").splitlines() if l.startswith("?? ")]

    print(f"commit: {commit}")
    print(f"python: {platform.python_version()}")
    print(f"jsonschema: {importlib.metadata.version('jsonschema')}")
    if sueltos:
        print(f"  sin versionar ({len(sueltos)}), fuera de la ruta de importacion:")
        for s in sueltos:
            print(f"    {s}")
    if modificados:
        print("  HAY ARCHIVOS VERSIONADOS MODIFICADOS:")
        for l in modificados.splitlines():
            print(f"    {l}")
        sys.exit("el validador del checkout no es el del commit: no se mide.")
    print()

    # Los MUST-FAIL, en el orden de cada index.json, leídos del commit. La
    # selección es la de emitir-55: una sola etiqueta en expected.rules hace un
    # control; cualquier otra cantidad lo deja excluido.
    excluidos = []
    de_regla = []
    de_esquema = []
    for suite in SUITES:
        indice = json.loads(blob(commit, f"spec/vectors/{suite}/index.json").decode("utf-8"))
        if indice.get("schema") != VERSIONES[suite]:
            sys.exit(f"spec/vectors/{suite}/index.json declara {indice.get('schema')!r}")
        for nombre in indice["vectors"]:
            ruta = f"spec/vectors/{suite}/{nombre}.json"
            v = json.loads(blob(commit, ruta).decode("utf-8"))
            artefacto = v.get("artifact") or {}
            if artefacto.get("schema") != VERSIONES[suite]:
                sys.exit(f"{ruta}: el artefacto declara {artefacto.get('schema')!r} en la suite {suite}")
            esperado = v.get("expected") or {}
            if esperado.get("valid"):
                continue
            reglas = esperado.get("rules") or []
            if len(reglas) != 1:
                excluidos.append((suite, {"vector": f"{suite}/{nombre}", "rules": sorted(reglas)}))
                continue
            etiqueta = reglas[0]
            fixture_id = f"disensor/{suite}/{nombre}"
            errores = validate_artifact(artefacto)
            if etiqueta == "schema":
                control = {"fixture_id": fixture_id,
                           "schema_errors": sum(1 for e in errores if e.startswith("[schema] "))}
                # Fuera del contrato de rule_errors, que supone un artefacto
                # que ya pasó el esquema: validate_artifact nunca llega acá
                # con estos bytes. Una excepción se registra y no cuenta como
                # regla detrás.
                try:
                    detras = rule_errors(artefacto)
                except Exception as exc:
                    control["exception"] = type(exc).__name__
                else:
                    control["rules_behind"] = etiquetas(detras)
                de_esquema.append((suite, control))
            else:
                observadas = etiquetas(errores)
                resto = [e for e in errores if not e.startswith(f"[{etiqueta}]")]
                de_regla.append((suite, {"fixture_id": fixture_id, "rule": etiqueta,
                                         "observed_rules": observadas,
                                         "matches_expected": observadas == [etiqueta],
                                         "second_motive": bool(resto)}))
    excluidos.sort(key=lambda t: t[1]["vector"])
    de_regla.sort(key=lambda t: t[1]["fixture_id"])
    de_esquema.sort(key=lambda t: t[1]["fixture_id"])

    def de(controles, condicion):
        return [(s, c) for s, c in controles if condicion(c)]

    print(f"excluidos, sin una sola etiqueta: {por_suite(excluidos)}")
    for _, x in excluidos:
        print(f"  {x['vector']}: {', '.join(x['rules'])}")
    print()
    print(f"controles de regla: {por_suite(de_regla)}")
    print(f"  con la etiqueta esperada: {por_suite(de(de_regla, lambda c: c['matches_expected']))}")
    print(f"  sin segundo motivo: {por_suite(de(de_regla, lambda c: not c['second_motive']))}")
    for _, c in de(de_regla, lambda c: not c["matches_expected"] or c["second_motive"]):
        print(f"    {corto(c['fixture_id'])}: esperada {c['rule']}, observadas {', '.join(c['observed_rules']) or 'ninguna'}"
              f"{', con segundo motivo' if c['second_motive'] else ''}")
    print()
    print(f"controles de esquema: {por_suite(de_esquema)}")
    print(f"  con exactamente un error de esquema: {por_suite(de(de_esquema, lambda c: c['schema_errors'] == 1))}")
    for _, c in de(de_esquema, lambda c: c["schema_errors"] != 1):
        print(f"    {corto(c['fixture_id'])}: {c['schema_errors']} errores de esquema")
    print(f"  con al menos una regla detras: {por_suite(de(de_esquema, lambda c: c.get('rules_behind')))}")
    for _, c in de(de_esquema, lambda c: c.get("rules_behind")):
        print(f"    {corto(c['fixture_id'])}: {', '.join(c['rules_behind'])}")
    print(f"  sin regla detras: {por_suite(de(de_esquema, lambda c: c.get('rules_behind') == []))}")
    print(f"  con excepcion: {por_suite(de(de_esquema, lambda c: 'exception' in c))}")
    for _, c in de(de_esquema, lambda c: "exception" in c):
        print(f"    {corto(c['fixture_id'])}: {c['exception']}")

    def solo(s, controles):
        return [c for t, c in controles if t == s]

    resumen = {
        "by_suite": {s: cuentas(solo(s, excluidos), solo(s, de_regla), solo(s, de_esquema)) for s in SUITES},
        "total": cuentas([c for _, c in excluidos], [c for _, c in de_regla], [c for _, c in de_esquema]),
    }
    datos = jsonb({
        "commit": commit,
        "excluded": [c for _, c in excluidos],
        "rule_controls": [c for _, c in de_regla],
        "schema_controls": [c for _, c in de_esquema],
        "summary": resumen,
    })

    mismo_checker(commit, {
        os.path.join("src", "disensor", n): sha(normaliza(blob(commit, f"src/disensor/{n}")))
        for n in ("rules.py",) + ESQUEMAS
    })
    os.makedirs(args.salida, exist_ok=True)
    with open(os.path.join(args.salida, JSON_SALIDA), "wb") as fh:
        fh.write(datos)
    print()
    print(f"escrito en {args.salida.replace(os.sep, '/')}/{JSON_SALIDA}")
    print(f"sha256 de {JSON_SALIDA}: {sha(datos)}")


if __name__ == "__main__":
    main()

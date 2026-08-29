"""The documented Action version has to be the version being shipped.

Between 0.2.0 and 0.3.0 the README kept pointing at `@v0.2.0` while `init` wrote
`@v0.3.0`, so anyone following the documentation ran a different gate than the
one the tool installs. That is cheap to catch and expensive to notice by hand.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from disensor import __version__

ROOT = Path(__file__).resolve().parents[1]
# Todo documento que publique el pin de la Action tiene que publicar el mismo.
# `README.es.md` entra acá desde que la documentación es bilingüe: si quedara
# afuera, el castellano se atrasaria en el pin sin que nada lo note, que es
# exactamente el fallo que este test existe para cazar.
#
# La guía NO entra: no documenta un pin ni deberia, y el test exige al menos uno
# por archivo.
DOCS = [
    ROOT / "README.md",
    ROOT / "README.es.md",
    ROOT / "docs" / "ejemplo-workflow.yml",
]

PIN = re.compile(r"NicolasRocchia/disensor@v([0-9]+\.[0-9]+\.[0-9]+)")


def test_documented_action_version_matches_the_package():
    for path in DOCS:
        pins = PIN.findall(path.read_text(encoding="utf-8"))
        assert pins, f"{path.name} documents no Action version"
        for pinned in pins:
            assert pinned == __version__, (
                f"{path.name} documents @v{pinned} while the package is {__version__}"
            )


NUL = chr(0)


def split_ls_files(output: str) -> list[str]:
    """Corta la salida de `git ls-files -z` por NUL.

    Separada del test para poder probarla con una salida armada. `git ls-files`
    sin `-z` separa por salto de linea y entrecomilla los nombres raros, y
    `.split()` ademas corta en los espacios: un archivo llamado `mi nota.md` se
    partia en dos rutas inexistentes, las dos se saltaban en silencio, y el
    archivo que si violaba la regla nunca se abria. El test pasaba justo cuando
    tenia que fallar.
    """
    return [name for name in output.split(NUL) if name]


def tracked_markdown() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return split_ls_files(out)


def test_a_name_with_spaces_stays_one_path():
    assert split_ls_files("README.md" + NUL + "docs/mi nota.md" + NUL) == [
        "README.md", "docs/mi nota.md",
    ]


EM_DASH = "\u2014"


def test_no_em_dashes_in_the_documents():
    """Regla editorial dura del proyecto: jamás guiones largos.

    Vivía en la cabeza de quien escribía y las rondas 0.4 a 0.6 metieron 38 sin
    que nadie los viera, tres de ellos en el README, que es la página de PyPI.
    Una regla que depende de recordarla no es una regla, es una intención: acá
    pasa al CI, la misma doctrina que el gate aplica a las declaraciones.

    `.residue/` queda afuera a propósito. Son declaraciones ya emitidas y la
    evidencia es de solo agregar (G8): corregirles el texto para satisfacer una
    regla de estilo sería reescribir un registro histórico, que es exactamente
    lo que la herramienta existe para impedir.
    """
    # -z y corte por NUL: `git ls-files` separa por salto de línea y entrecomilla
    # los nombres raros, y `.split()` además corta en los espacios. Un archivo
    # llamado `mi nota.md` se partía en dos rutas inexistentes, las dos se
    # saltaban en silencio, y el archivo que sí tenía el guión largo nunca se
    # abría: el test pasaba justo cuando tenía que fallar.
    tracked = tracked_markdown()
    offenders = {}
    for name in tracked:
        if name.startswith(".residue/"):
            continue
        text = (ROOT / name).read_text(encoding="utf-8")
        if EM_DASH in text:
            offenders[name] = text.count(EM_DASH)
    assert not offenders, f"guiones largos encontrados: {offenders}"


def implemented_checks() -> list[int]:
    """Los chequeos G que gate.py implementa de verdad, no los que dice implementar."""
    src = (ROOT / "src" / "disensor" / "gate.py").read_text(encoding="utf-8")
    # \d+ y no \d: con un solo digito, un G10 quedaba invisible.
    return sorted({int(n) for n in re.findall(r"\[G(\d+)\]", src)})


def cli_help(*argv: str) -> str:
    """La ayuda que ve un usuario, ejercitando la interfaz y no leyendo el fuente.

    El test anterior leia cli.py como texto y por eso daba verde sobre una ayuda
    que el usuario nunca ve: `help=` solo aparece en el listado de
    `disensor --help`, mientras `disensor gate --help` muestra `description`.
    Corregir el primero y afirmar que se arreglo el segundo era falso, y el test
    lo confirmaba igual.
    """
    out = subprocess.run(
        [sys.executable, "-m", "disensor", *argv, "--help"],
        cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    return out.stdout


def test_the_gate_help_names_every_implemented_check():
    """G9 es el que exige residue/v0.3 a las declaraciones que un PR agrega.

    Una ayuda que no lo nombra esconde el chequeo que hace cumplir la version
    del contrato.
    """
    checks = implemented_checks()
    assert checks, "no se detecto ningun chequeo G en gate.py"
    assert checks == list(range(checks[0], checks[-1] + 1)), (
        f"los chequeos implementados no son contiguos: {checks}. Un rango en la ayuda "
        "no puede describirlos con honestidad"
    )
    for texto, donde in ((cli_help("gate"), "disensor gate --help"),
                         (cli_help(), "disensor --help")):
        rango = re.search(r"G(\d+)\s*(?:to|a)\s*G(\d+)", texto.replace("\n", " "))
        assert rango, f"{donde} no declara un rango de chequeos"
        assert [int(rango.group(1)), int(rango.group(2))] == [checks[0], checks[-1]], (
            f"{donde} dice G{rango.group(1)} a G{rango.group(2)} y gate.py implementa "
            f"G{checks[0]} a G{checks[-1]}"
        )


def test_the_schema_declares_the_version_the_tool_enforces():
    """El $id, la descripcion y lo que el gate exige tienen que decir lo mismo.

    El test anterior comparaba el $id contra la descripcion del mismo archivo, o
    sea derivaba la expectativa del valor que debia proteger: bajar los dos a
    v0.2 a la vez lo dejaba pasar. La referencia ahora es CURRENT_SCHEMA, que es
    lo que el gate exige de verdad a las declaraciones nuevas.
    """
    import json

    from disensor.gate import CURRENT_SCHEMA

    esperada = CURRENT_SCHEMA.split("/")[-1]
    for ruta in (ROOT / "spec" / "residue.schema.json",
                 ROOT / "src" / "disensor" / "residue.schema.json"):
        s = json.loads(ruta.read_text(encoding="utf-8"))
        assert f"/residue/{esperada}/" in s["$id"], (
            f"{ruta.name}: el $id es {s['$id']} y el gate exige {CURRENT_SCHEMA}"
        )
        provisional = re.search(r"Provisional version (v[0-9.]+)", s.get("description", ""))
        assert provisional, f"{ruta.name}: la descripcion no dice cual es la version provisional"
        assert provisional.group(1) == esperada, (
            f"{ruta.name}: la descripcion dice {provisional.group(1)} y el gate exige {esperada}"
        )
        # Desde v0.4 el discriminador es `const` y no `enum`: cada version
        # tiene su recurso y una declaracion se valida contra la suya, en vez
        # de contra una forma combinada que le dejaria pedir prestados campos
        # de una version que no existia cuando se escribio.
        assert s["properties"]["schema"].get("const") == CURRENT_SCHEMA, (
            f"{ruta.name}: el discriminador no fija {CURRENT_SCHEMA}"
        )


def test_the_self_gate_pin_is_a_commit_not_a_tag_object():
    """El SHA pineado en ci.yml tiene que ser un commit pelado.

    `git rev-parse v0.6.3` devuelve el OBJETO TAG cuando el tag es anotado, no
    el commit, y ese SHA es exactamente el que se pineo en una ronda: parecia
    inmutable y correcto, resolvia en varias superficies de GitHub, y ya hay
    antecedente documentado de que los tag-object SHA se rompieron por un cambio
    interno. Si el resolver vuelve a exigir commits, el required check falla
    antes de ejecutar el gate y bloquea todos los PR. La ironia quedo declarada:
    el propio gate resuelve `^{commit}` por este mismo motivo, y el pin se hizo
    a mano sin hacerlo.
    """
    import pytest

    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    shas = re.findall(r"NicolasRocchia/disensor@([0-9a-f]{40})", ci)
    assert shas, "el auto-gate ya no esta pineado por SHA"

    # La superficialidad se pregunta, no se infiere de una falla. La version
    # anterior skipeaba ante CUALQUIER error de cat-file, asi que un SHA con un
    # typo en un clon COMPLETO tambien skipeaba y el pin roto llegaba verde a
    # main: el remedio escondia el incidente justo donde el chequeo importa
    # (hallazgo de la micro-ronda de Antigravity). Con la pregunta explicita,
    # en el clon superficial de un colaborador se skipea una sola vez y con el
    # motivo a la vista, y en un clon completo (el CI clona con fetch-depth 0)
    # un objeto ausente es lo que es: un pin roto, y el test falla. El skip vive
    # ANTES del bucle ademas para no abortar la verificacion de los pines
    # siguientes si algun dia hay mas de uno.
    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip() == "true"
    if shallow:
        # En CI el skip seria un bypass, no una cortesia: la invariante "el CI
        # clona completo" vive en ci.yml, que es parte del codigo bajo prueba, y
        # un PR puede meter un pin roto Y borrar el fetch-depth 0 en el mismo
        # commit. El clon queda superficial, el test creeria que es la maquina
        # de un colaborador, y el pin roto llegaria verde a main (ataque
        # concreto de la micro-ronda de Antigravity). GitHub Actions define
        # CI=true siempre: aca superficial significa contrato del workflow roto
        # o intento de esquivar el chequeo, y las dos cosas son fallo.
        if os.environ.get("CI"):
            pytest.fail(
                "clon superficial dentro de CI: el job de tests tiene que clonar con "
                "fetch-depth 0 para que el chequeo del pin corra. Si esta linea "
                "desaparecio de ci.yml, eso es exactamente lo que hay que revisar"
            )
        pytest.skip("clon superficial: los objetos pineados pueden no estar; el CI clona completo")

    for sha in shas:
        r = subprocess.run(
            ["git", "cat-file", "-t", sha],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        assert r.returncode == 0, (
            f"el SHA pineado {sha[:12]} no existe en este repositorio completo: pin roto"
        )
        tipo = r.stdout.strip()
        assert tipo == "commit", (
            f"el pin {sha[:12]} es un objeto '{tipo}', no un commit: "
            "rev-parse sobre un tag anotado devuelve el tag, hace falta ^{commit}"
        )


def test_the_status_section_names_the_package_version():
    """La seccion de estado dice que version es esta.

    El test de al lado solo mira los pines `@vX` de la Action, asi que un bump
    podia dejar el encabezado de estado en la version anterior y pasar en verde:
    quien abriera la pagina del repositorio o el README que renderiza PyPI leia
    una version y el paquete instalado reportaba otra. Lo cazo el revisor
    de la ronda del propio bump, no esta suite.
    """
    import re

    # Los dos README, que son los que tienen seccion de estado; DOCS ademas
    # incluye el workflow de ejemplo, que solo lleva el pin de la Action.
    for path in [p for p in DOCS if p.name.startswith("README")]:
        texto = path.read_text(encoding="utf-8")
        m = re.search(r"^## (?:Status|Estado)\s*\n+v([0-9][0-9.]*)", texto, re.M)
        assert m, f"{path.name} no tiene una seccion de estado que empiece por su version"
        assert m.group(1) == __version__, (
            f"{path.name} dice estar en v{m.group(1)} y el paquete es {__version__}"
        )

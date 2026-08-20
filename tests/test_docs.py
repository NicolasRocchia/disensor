"""The documented Action version has to be the version being shipped.

Between 0.2.0 and 0.3.0 the README kept pointing at `@v0.2.0` while `init` wrote
`@v0.3.0`, so anyone following the documentation ran a different gate than the
one the tool installs. That is cheap to catch and expensive to notice by hand.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from disensor import __version__

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", ROOT / "docs" / "ejemplo-workflow.yml"]

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

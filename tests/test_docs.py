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
    tracked = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    offenders = {}
    for name in tracked:
        if name.startswith(".residue/"):
            continue
        text = (ROOT / name).read_text(encoding="utf-8")
        if EM_DASH in text:
            offenders[name] = text.count(EM_DASH)
    assert not offenders, f"guiones largos encontrados: {offenders}"

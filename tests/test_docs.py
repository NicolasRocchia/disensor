"""The documented Action version has to be the version being shipped.

Between 0.2.0 and 0.3.0 the README kept pointing at `@v0.2.0` while `init` wrote
`@v0.3.0`, so anyone following the documentation ran a different gate than the
one the tool installs. That is cheap to catch and expensive to notice by hand.
"""
from __future__ import annotations

import re
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

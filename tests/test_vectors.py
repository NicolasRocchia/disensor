"""Conformance of the reference implementation against the vectors.

Every port of the validator (TypeScript or other) has to pass this same
comparison: same verdict and same rule labels per vector.
"""
import json
from pathlib import Path

import pytest

from disensor.rules import validate_artifact
from disensor.vectors import _labels

VECTORS = Path(__file__).resolve().parents[1] / "spec" / "vectors"


@pytest.mark.parametrize("path", sorted(VECTORS.glob("*.json")), ids=lambda p: p.stem)
def test_vector(path):
    if path.name == "index.json":
        pytest.skip("index")
    with path.open(encoding="utf-8") as f:
        vector = json.load(f)
    errors = validate_artifact(vector["artifact"])
    assert (not errors) == vector["expected"]["valid"], errors
    assert _labels(errors) == vector["expected"]["rules"], errors


def test_packaged_schema_matches_the_spec():
    """The distribution embeds its own copy of the schema; drift is silent.

    The package validates against `src/disensor/residue.schema.json` while the
    conformance vectors and every other implementation read `spec/`. Nothing
    else notices if the two stop agreeing, and then the reference validator and
    the specification it claims to implement are different contracts.
    """
    root = Path(__file__).resolve().parents[1]
    with open(root / "spec" / "residue.schema.json", encoding="utf-8") as f:
        spec = json.load(f)
    with open(root / "src" / "disensor" / "residue.schema.json", encoding="utf-8") as f:
        packaged = json.load(f)
    assert spec == packaged, "spec/residue.schema.json and the packaged copy have drifted"

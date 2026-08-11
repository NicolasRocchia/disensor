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

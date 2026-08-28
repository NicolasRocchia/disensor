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


def test_every_schema_resource_is_identical_in_both_copies():
    """El paquete valida contra su copia y la spec publica la suya.

    Si divergen, dos implementaciones que dicen seguir el mismo contrato siguen
    contratos distintos y nada lo detecta.
    """
    import hashlib

    root = Path(__file__).resolve().parents[1]
    nombres = sorted(p.name for p in (root / "spec").glob("residue.schema*.json"))
    assert nombres, "no hay recursos de esquema en spec/"
    for nombre in nombres:
        a = (root / "spec" / nombre).read_bytes()
        b = (root / "src" / "disensor" / nombre).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), (
            f"{nombre} difiere entre spec/ y src/disensor/"
        )


def test_a_frozen_version_does_not_load_from_the_moving_slot():
    """`residue.schema.json` es el slot de la version vigente y cada release lo mueve.

    Mientras v0.4 se cargara de ahi, el dia del salto "cargar v0.4" habria
    cargado v0.5: el despacho por version depende de que cada version tenga su
    recurso propio.
    """
    from disensor.rules import CURRENT, SCHEMA_FILES, load_schema

    for version, archivo in SCHEMA_FILES.items():
        assert archivo != "residue.schema.json", (
            f"{version} se carga del slot mutable en vez de su recurso congelado"
        )
        assert load_schema(version)["properties"]["schema"]["const"] == version, (
            f"el recurso de {version} no declara esa version"
        )
    assert CURRENT in SCHEMA_FILES

"""Conformidad de la implementacion de referencia contra los vectores.

Todo port del validador (TypeScript u otro) tiene que pasar esta misma
comparacion: mismo veredicto y mismas etiquetas de regla por vector.
"""
import json
from pathlib import Path

import pytest

from disensor.reglas import validar_artefacto
from disensor.vectores import _etiquetas

VECTORES = Path(__file__).resolve().parents[1] / "spec" / "vectores"


@pytest.mark.parametrize("ruta", sorted(VECTORES.glob("*.json")), ids=lambda p: p.stem)
def test_vector(ruta):
    if ruta.name == "INDICE.json":
        pytest.skip("indice")
    with ruta.open(encoding="utf-8") as f:
        vector = json.load(f)
    errores = validar_artefacto(vector["artefacto"])
    assert (not errores) == vector["esperado"]["valido"], errores
    assert _etiquetas(errores) == vector["esperado"]["reglas"], errores

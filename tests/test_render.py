"""El comentario del gate nombra todo lo que el esquema deja declarar.

El render tiene su propia tabla de nombres por clase, y el esquema no la
actualiza solo. v0.4 sumó `reviewer_correlation` y `reviewer_hardening_gap`,
R11 y R12 los exigen cuando un revisor declara independencia degradada o
`hardening: unverified`, y la tabla siguió con tres entradas: la declaración
validaba y el gate moría con KeyError al armar el comentario, también con
`--no-comment`, porque el cuerpo se renderiza antes de decidir si se publica
(#56). Ninguna declaración del repo llevaba esas clases y ningún test las
pasaba por el render, así que el modo degradado que v0.4 volvió declarable
rompía el gate la primera vez que alguien lo declaraba de verdad.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from disensor.render import CLASS_NAME, render_comment
from disensor.rules import load_schema, validate_artifact

EXAMPLE = Path(__file__).resolve().parents[1] / "spec" / "examples" / "example_2_diff_gate.json"


def degradar(a: dict) -> dict:
    """Una ronda degradada bien declarada: el revisor es el mismo modelo que el
    generador y corrió sin endurecimiento verificado, con el ítem que cada
    regla exige para cada cosa."""
    gen = a["actors"]["generator"]
    r = a["actors"]["reviewers"][0]
    r["family"] = gen["family"]
    r["model"] = gen["model"]
    r["independence"] = "same_model_fresh_context"
    r["fallback_reason"] = {"code": "no_other_family_available"}
    r["hardening"] = "unverified"
    a["residue"]["items"] += [
        {
            "id": "r4",
            "class": "reviewer_correlation",
            "reviewer_ref": r["reviewer_id"],
            "requires_human_attention": True,
            "description": (
                "El revisor comparte modelo con el generador: los errores que ese modelo "
                "comete de forma sistemática no los cubrió esta ronda."
            ),
        },
        {
            "id": "r5",
            "class": "reviewer_hardening_gap",
            "reviewer_ref": r["reviewer_id"],
            "requires_human_attention": True,
            "description": (
                "El adaptador no tiene verificada la neutralización de las instrucciones "
                "del proyecto: el material revisado pudo hablarle al revisor."
            ),
        },
    ]
    return a


@pytest.fixture()
def degradada() -> dict:
    a = degradar(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    errores = validate_artifact(a)
    assert errores == [], f"la declaración degradada tiene que validar: el bug es del render, no de las reglas: {errores}"
    return a


def test_render_names_every_class_the_schema_admits():
    """La tabla del render y el enum del esquema no se separan en silencio."""
    clases = load_schema()["$defs"]["residue_item"]["properties"]["class"]["enum"]
    assert set(CLASS_NAME) == set(clases)


@pytest.mark.parametrize("profile", ["full", "minimized"])
def test_the_comment_names_the_degraded_reviewer_in_both_profiles(degradada, profile):
    """El ítem dice de qué revisor habla también cuando el perfil omite la descripción."""
    degradada["profile"] = profile
    if profile == "minimized":
        for item in degradada["residue"]["items"]:
            item.pop("description", None)
    body = render_comment([degradada], {}, [])
    rid = degradada["actors"]["reviewers"][0]["reviewer_id"]
    for klass in ("reviewer_correlation", "reviewer_hardening_gap"):
        linea = next(line for line in body.splitlines() if CLASS_NAME[klass] in line)
        assert f"(reviewer {rid})" in linea, linea
        assert "requires human attention" in linea, linea


@pytest.mark.parametrize("profile", ["full", "minimized"])
def test_a_finding_ref_does_not_hide_the_reviewer(degradada, profile):
    """Hallazgo de la ronda del PR #57: el esquema admite `finding_ref` y
    `reviewer_ref` en el mismo ítem, y el primero tapaba al segundo."""
    for item in degradada["residue"]["items"]:
        if item["class"] in ("reviewer_correlation", "reviewer_hardening_gap"):
            item["finding_ref"] = "h1"
    assert validate_artifact(degradada) == [], "las dos referencias juntas son válidas: el bug era del render"
    degradada["profile"] = profile
    if profile == "minimized":
        for item in degradada["residue"]["items"]:
            item.pop("description", None)
    body = render_comment([degradada], {}, [])
    rid = degradada["actors"]["reviewers"][0]["reviewer_id"]
    for klass in ("reviewer_correlation", "reviewer_hardening_gap"):
        linea = next(line for line in body.splitlines() if CLASS_NAME[klass] in line)
        assert f"(finding h1, reviewer {rid})" in linea, linea

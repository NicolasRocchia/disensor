"""Tests of rules R0 to R10 and of the gate checks.

The positives are the spec examples. The negatives are mutations of those
examples: each rule has to reject exactly what it promises to reject.
A gate that approves everything is not a gate.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from disensor.gate import DEFAULT_CONFIG, GateFailure, merge_config, validate_config_shape
from disensor.rules import load_schema, validate_artifact

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "spec" / "examples"


@pytest.fixture(scope="module")
def schema():
    return load_schema()


def load(name: str) -> dict:
    with open(EXAMPLES / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def plan():
    return load("example_1_plan_gate.json")


@pytest.fixture()
def diff():
    return load("example_2_diff_gate.json")


@pytest.fixture()
def minimized():
    return load("example_3_minimized_profile.json")


def test_spec_examples_validate(schema):
    for name in sorted(p.name for p in EXAMPLES.glob("*.json")):
        assert validate_artifact(load(name), schema) == [], name


def assert_rejects(schema, artifact, rule: str | None):
    errors = validate_artifact(artifact, schema)
    assert errors, "the validator accepted an invalid artifact"
    if rule:
        assert any(f"[{rule}]" in e for e in errors), f"expected {rule}, got: {errors}"


def test_r1_escalation_without_item(schema, diff):
    m = copy.deepcopy(diff)
    m["residue"]["items"] = [i for i in m["residue"]["items"] if i["id"] != "r1"]
    assert_rejects(schema, m, "R1")


def test_r1_nonexistent_reference(schema, diff):
    m = copy.deepcopy(diff)
    m["residue"]["items"][0]["finding_ref"] = "h99"
    assert_rejects(schema, m, "R1")


def test_r2_generic_marker_in_item(schema, diff):
    m = copy.deepcopy(diff)
    m["residue"]["items"][0]["description"] = "none"
    assert_rejects(schema, m, "R2")


def test_r2_generic_marker_in_spanish(schema, diff):
    m = copy.deepcopy(diff)
    m["residue"]["items"][0]["description"] = "ninguno"
    assert_rejects(schema, m, "R2")


def test_r3_abbreviated_path_on_protected_case(schema, diff):
    m = copy.deepcopy(diff)
    m["event"]["abbreviated_path"] = {
        "used": True,
        "justification": "cambio trivial de una linea en un helper",
        "protected_cases_touched": ["data_migration"],
    }
    assert_rejects(schema, m, None)  # caught by the schema if/then


def test_r4_no_decorrelation(schema, diff):
    m = copy.deepcopy(diff)
    m["actors"]["reviewers"][0]["family"] = "anthropic"
    assert_rejects(schema, m, "R4")


def test_r5_gap_in_level_a_without_lead(schema, diff):
    m = copy.deepcopy(diff)
    m["event"]["criticality_level"] = "A"
    assert_rejects(schema, m, "R5")


def test_r5_gap_in_level_a_with_lead_passes(schema, diff):
    m = copy.deepcopy(diff)
    m["event"]["criticality_level"] = "A"
    for i in m["residue"]["items"]:
        if i["class"] == "execution_gap":
            i["lead_acceptance"] = {
                "lead": "tech-lead-01",
                "date": "2026-07-15T19:00:00-03:00",
                "record": "minutes/2026-07-15-gap-acceptance.md",
            }
    assert validate_artifact(m, schema) == []


def test_r6_inflated_count(schema, diff):
    m = copy.deepcopy(diff)
    m["metrics"]["counts"]["valid"]["incorporated"] = 3
    assert_rejects(schema, m, "R6")


def test_r7_fix_pending_in_diff_gate(schema, diff):
    m = copy.deepcopy(diff)
    m["findings"][0]["fix_verification"] = {"type": "pending_in_diff_gate"}
    assert_rejects(schema, m, "R7")


def test_r7_pending_is_valid_in_plan_gate(schema, plan):
    assert validate_artifact(plan, schema) == []


def test_r8_interpretive_without_human_attention(schema, diff):
    m = copy.deepcopy(diff)
    m["residue"]["items"][1]["refutation_type"] = "interpretive"
    m["residue"]["items"][1]["requires_human_attention"] = False
    assert_rejects(schema, m, None)  # caught by the schema if/then


def test_r9_text_leak_in_minimized(schema, minimized):
    m = copy.deepcopy(minimized)
    m["findings"][0]["title"] = "titulo que no deberia estar"
    assert_rejects(schema, m, "R9")


def test_r9_clear_url_in_minimized(schema, minimized):
    m = copy.deepcopy(minimized)
    m["event"]["repository"] = "https://github.com/ejemplo/repo"
    assert_rejects(schema, m, "R9")


def test_schema_debt_without_id(schema, diff):
    m = copy.deepcopy(diff)
    m["findings"][0]["final_state"] = "debt_recorded"
    assert_rejects(schema, m, None)


def test_r0_no_human_arbiter(schema, diff):
    m = copy.deepcopy(diff)
    m["actors"]["human_arbiter"]["present"] = False
    assert_rejects(schema, m, "R0")


def test_declared_absence_valid(schema, diff):
    m = copy.deepcopy(diff)
    m["findings"] = []
    m["residue"] = {
        "declared_absence": True,
        "declaration": "El ciclo corrio completo sobre el diff y no quedo nada sin resolver: "
                       "los dos hallazgos se incorporaron y sus correcciones pasaron pruebas especificas.",
    }
    m["metrics"]["counts"] = {
        "total_findings": 0,
        "valid": {"incorporated": 0, "debt_recorded": 0, "owner_decision": 0},
        "false_positives": {"refuted_verifiable": 0, "refuted_interpretive": 0},
        "escalated_open": 0,
    }
    # A round that found nothing is valid data, and it has to be declarable in
    # the profile the tool creates by default. Demanding the minimized profile
    # for it, as this test used to assert, left a first-time user following the
    # guide into an error with no way out.
    assert validate_artifact(m, schema) == []
    m["profile"] = "minimized"
    m["event"]["repository"] = "sha256:" + "ab" * 32
    assert validate_artifact(m, schema) == []


def test_counts_without_their_findings_are_not_a_record(schema, diff):
    """An empty list is a declaration; an empty list with counts is a contradiction."""
    m = copy.deepcopy(diff)
    m["findings"] = []
    errors = validate_artifact(m, schema)
    assert any("[R10]" in e for e in errors)


def test_full_profile_still_demands_the_list_exists(schema, diff):
    m = copy.deepcopy(diff)
    del m["findings"]
    assert any("[R10]" in e for e in validate_artifact(m, schema))


def test_v01_artifact_gets_migration_hint(schema):
    old = {"esquema": "residuo/v0.1", "perfil": "completo"}
    errors = validate_artifact(old, schema)
    assert len(errors) == 1 and "residue/v0.2" in errors[0] and "glossary" in errors[0]


def test_config_merges_with_default():
    config = merge_config({"criticality_level": "A", "gate": {"required": False}})
    assert config["criticality_level"] == "A"
    assert config["gate"]["required"] is False
    assert config["gate"]["level_A_accepted_confinement"] == DEFAULT_CONFIG["gate"]["level_A_accepted_confinement"]
    assert config["level_A_enabled"] is False


def test_config_with_v01_keys_fails_loudly():
    with pytest.raises(GateFailure) as exc:
        validate_config_shape({"nivel_criticidad": "A"}, "config")
    assert "criticality_level" in str(exc.value)


def test_r2_unfilled_minimized_template_does_not_validate(schema, tmp_path, monkeypatch):
    from disensor.template import template

    monkeypatch.chdir(tmp_path)
    m = template("diff", "B", "minimized", tmp_path)
    m["event"]["repository"] = "sha256:" + "cd" * 32  # dodge R9 on purpose
    m["event"]["head_commit"] = "abc1234"  # dodge the schema to isolate R2
    errors = validate_artifact(m, schema)
    assert any("[R2]" in e and "template" in e for e in errors)

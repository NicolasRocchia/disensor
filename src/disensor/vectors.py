"""Conformance vectors of schema v0.3.

The vectors are the shared source of truth across implementations of the
validator (the Python reference, the TypeScript one of the evidence plane,
and those to come). Each vector is an artifact plus the expected verdict:
valid or not, and the set of rule labels that must fire ("schema" for shape
errors, "R0" to "R10" for structural rules).

Labels are compared, not messages: messages are free per implementation;
labels cannot diverge.

Usage: python -m disensor.vectors <target_directory>
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from .rules import validate_artifact

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "spec" / "examples"


def _load(name: str) -> dict:
    with open(EXAMPLES / name, encoding="utf-8") as f:
        return json.load(f)


def _labels(errors: list[str]) -> list[str]:
    tags = set()
    for e in errors:
        if e.startswith("[") and "]" in e:
            tags.add(e[1:e.index("]")])
    return sorted(tags)


def cases() -> list[tuple[str, dict, bool, set[str]]]:
    """(name, artifact, expected_valid, rules_that_must_fire)."""
    plan = _load("example_1_plan_gate.json")
    diff = _load("example_2_diff_gate.json")
    mini = _load("example_3_minimized_profile.json")
    out: list[tuple[str, dict, bool, set[str]]] = []

    # Valid
    out.append(("valid_plan_gate", copy.deepcopy(plan), True, set()))
    out.append(("valid_diff_gate", copy.deepcopy(diff), True, set()))
    out.append(("valid_minimized_profile", copy.deepcopy(mini), True, set()))

    m = copy.deepcopy(diff)
    m["event"]["criticality_level"] = "A"
    for i in m["residue"]["items"]:
        if i["class"] == "execution_gap":
            i["lead_acceptance"] = {
                "lead": "tech-lead-01",
                "date": "2026-07-15T19:00:00-03:00",
                "record": "minutes/2026-07-15-gap-acceptance.md",
            }
    out.append(("valid_level_a_gap_with_lead", m, True, set()))

    m = copy.deepcopy(mini)
    m["findings"] = []
    m["residue"] = {
        "declared_absence": True,
        "declaration": "El ciclo corrio completo sobre el diff y no quedo nada sin resolver: "
                       "todo hallazgo se incorporo y sus correcciones pasaron pruebas especificas.",
    }
    m["metrics"]["counts"] = {
        "total_findings": 0,
        "valid": {"incorporated": 0, "debt_recorded": 0, "owner_decision": 0},
        "false_positives": {"refuted_verifiable": 0, "refuted_interpretive": 0},
        "escalated_open": 0,
    }
    out.append(("valid_minimized_declared_absence", m, True, set()))

    # Invalid: structural rules
    m = copy.deepcopy(diff)
    m["actors"]["human_arbiter"]["present"] = False
    out.append(("r0_no_human_arbiter", m, False, {"R0"}))

    m = copy.deepcopy(diff)
    m["residue"]["items"] = [i for i in m["residue"]["items"] if i["id"] != "r1"]
    out.append(("r1_escalation_without_item", m, False, {"R1"}))

    m = copy.deepcopy(diff)
    m["residue"]["items"][0]["finding_ref"] = "h99"
    out.append(("r1_nonexistent_reference", m, False, {"R1"}))

    m = copy.deepcopy(diff)
    m["residue"]["items"][0]["description"] = "none"
    out.append(("r2_generic_marker", m, False, {"R2"}))

    m = copy.deepcopy(diff)
    m["actors"]["reviewers"][0]["model"] = "FILL_IN_reviewer_model"
    out.append(("r2_template_marker", m, False, {"R2"}))

    m = copy.deepcopy(diff)
    m["actors"]["reviewers"][0]["family"] = "anthropic"
    out.append(("r4_no_decorrelation", m, False, {"R4"}))

    m = copy.deepcopy(diff)
    m["event"]["criticality_level"] = "A"
    out.append(("r5_level_a_gap_without_lead", m, False, {"R5"}))

    m = copy.deepcopy(diff)
    m["metrics"]["counts"]["valid"]["incorporated"] = 3
    out.append(("r6_inflated_count", m, False, {"R6"}))

    m = copy.deepcopy(diff)
    m["findings"][0]["fix_verification"] = {"type": "pending_in_diff_gate"}
    out.append(("r7_fix_pending_in_diff", m, False, {"R7"}))

    m = copy.deepcopy(mini)
    m["findings"][0]["title"] = "titulo que no deberia estar"
    out.append(("r9_text_leak_in_minimized", m, False, {"R9"}))

    m = copy.deepcopy(mini)
    m["event"]["repository"] = "https://github.com/ejemplo/repo"
    out.append(("r9_clear_url_in_minimized", m, False, {"R9"}))

    m = copy.deepcopy(diff)
    m["findings"] = []
    out.append(("r10_full_without_findings", m, False, {"R10"}))

    # Invalid: schema only (rules are not evaluated when the shape fails)
    m = copy.deepcopy(diff)
    m["event"]["abbreviated_path"] = {
        "used": True,
        "justification": "cambio trivial de una linea en un helper",
        "protected_cases_touched": ["data_migration"],
    }
    out.append(("schema_abbreviated_path_on_protected_case", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    m["findings"][0]["final_state"] = "debt_recorded"
    out.append(("schema_debt_without_id", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    m["residue"]["items"][1]["refutation_type"] = "interpretive"
    m["residue"]["items"][1]["requires_human_attention"] = False
    out.append(("schema_interpretive_without_human_attention", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    m["event"]["head_commit"] = "ZZZZ"
    out.append(("schema_invalid_commit", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    del m["residue"]["items"]
    out.append(("schema_empty_residue", m, False, {"schema"}))

    # v0.3 hardening: a verifiable refutation closes a finding without touching
    # the code, so it demands material evidence and a verifiable target. In v0.2
    # the presence of the evidence object was enough and `none` was admitted.
    def _refuted(artifact: dict) -> dict:
        return next(h for h in artifact["findings"] if h["final_state"] == "refuted_verifiable")

    m = copy.deepcopy(diff)
    _refuted(m)["evidence"] = {}
    out.append(("schema_refuted_verifiable_empty_evidence", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    _refuted(m)["verification"] = {"against": "none"}
    out.append(("schema_refuted_verifiable_against_none", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    _refuted(m)["verification"]["against"] = "external_source"
    out.append(("valid_refuted_verifiable_external_source", m, True, set()))

    # The anyOf demands presence of text, link or hash; without a content floor
    # its weakest member accepts a blank string, and presence without material
    # reopens the hole of #5 through another door.
    m = copy.deepcopy(diff)
    _refuted(m)["evidence"] = {"link": ""}
    out.append(("schema_refuted_verifiable_blank_link", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    _refuted(m)["evidence"] = {"text": " " * 10}
    out.append(("schema_refuted_verifiable_blank_text", m, False, {"schema"}))

    # v0.3 hardening: the minimized profile keeps free text out of the extension
    # space too, which the rules deliberately do not interpret.
    m = copy.deepcopy(mini)
    m["extensions"] = {"com.example.note": "texto libre que no deberia salir del entorno"}
    out.append(("schema_minimized_extensions_clear_text", m, False, {"schema"}))

    # Opaque values are not enough if the key itself carries the message: keys
    # must be identifier-shaped, a name and not a sentence.
    m = copy.deepcopy(mini)
    m["extensions"] = {"nota del incidente en claro": True}
    out.append(("schema_minimized_extensions_prose_key", m, False, {"schema"}))

    m = copy.deepcopy(mini)
    m["extensions"] = {
        "com.example.digest": "sha256:" + "a" * 64,
        "com.example.count": 3,
        "com.example.nested": {"flag": True, "digests": ["sha256:" + "b" * 64]},
    }
    out.append(("valid_minimized_opaque_extensions", m, True, set()))

    m = copy.deepcopy(diff)
    m["extensions"] = {"com.example.note": "texto libre, legitimo en el perfil completo"}
    out.append(("valid_full_extensions_free_text", m, True, set()))

    return out


def generate(target: Path) -> int:
    """Write the vectors with the verdict of the reference implementation.

    The verdict is recorded from the implementation, but each case carries a
    minimum expectation (valid or not, and which rules must appear) that is
    checked before writing: the generator cannot bless its own bug.
    """
    target.mkdir(parents=True, exist_ok=True)
    index = []
    for name, artifact, expected_valid, minimum_rules in cases():
        errors = validate_artifact(artifact)
        valid = not errors
        labels = _labels(errors)
        assert valid == expected_valid, f"{name}: expected valid={expected_valid}, got {valid}: {errors}"
        missing = minimum_rules - set(labels)
        assert not missing, f"{name}: missing rules {missing} in {labels}"
        vector = {
            "name": name,
            "expected": {"valid": valid, "rules": labels},
            "artifact": artifact,
        }
        with open(target / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(vector, f, ensure_ascii=False, indent=2)
            f.write("\n")
        index.append(name)
    with open(target / "index.json", "w", encoding="utf-8") as f:
        json.dump({"schema": "residue/v0.3", "vectors": index}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(index)} vectors written to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(generate(Path(sys.argv[1] if len(sys.argv) > 1 else "spec/vectors")))

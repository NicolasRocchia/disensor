"""Validation rules for the residue artifact (schema v0.3).

Two layers, in the spirit of section 12.2 of the protocol:
  1. JSON Schema: shape and conditional fields.
  2. Structural rules R0 to R10: coherence a schema cannot express.

Honest limit, declared in the protocol: the machine detects the empty field
and the generic marker, not the false declaration. Human sampling remains
the only real defense against cosmetic compliance.
"""
from __future__ import annotations

import json
from importlib import resources

from jsonschema import Draft202012Validator

GENERIC_MARKERS = {
    # English
    "n/a", "na", "none", "all resolved", "applied", "ok", "no residue",
    "-", "not applicable", "done", "resolved",
    # Spanish (teams write in their own language; laziness has no border)
    "ninguno", "ninguna", "todo resuelto", "aplicado", "sin residuo", "no aplica",
}

RESIDUE_STATES = {"escalated_open", "refuted_verifiable", "refuted_interpretive"}

EXPECTED_CLASS = {
    "escalated_open": "escalation_without_decision",
    "refuted_verifiable": "principal_refutation",
    "refuted_interpretive": "principal_refutation",
}

MINIMIZED_FORBIDDEN_TEXT_FIELDS = {"title", "description", "location"}

TEMPLATE_MARKER = "FILL_IN"


def load_schema() -> dict:
    """Load the schema packaged with the distribution."""
    with resources.files("disensor").joinpath("residue.schema.json").open(encoding="utf-8") as f:
        return json.load(f)


def schema_errors(artifact: dict, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    return [
        f"[schema] {'/'.join(str(p) for p in err.path) or '(root)'}: {err.message}"
        for err in sorted(validator.iter_errors(artifact), key=lambda x: list(x.path))
    ]


def rule_errors(a: dict) -> list[str]:
    """Structural rules over an artifact already valid against the schema."""
    e: list[str] = []

    def error(rule: str, msg: str) -> None:
        e.append(f"[{rule}] {msg}")

    profile = a["profile"]
    findings = a.get("findings", [])
    residue = a["residue"]
    items = residue.get("items", [])
    by_id = {h["id"]: h for h in findings}
    gate = a["event"]["gate"]
    level = a["event"]["criticality_level"]

    # R0: without a human arbiter the event does not comply with the protocol (section 6).
    if not a["actors"]["human_arbiter"]["present"]:
        error("R0", "event without a human arbiter present")

    # R10: in the full profile, the findings list IS the declaration of what was
    # found. An absent list means nothing was declared; a present empty list is
    # the explicit statement that the round found nothing, which is valid data
    # and has to stay possible: otherwise the guide promises a clean round can be
    # declared and the validator refuses it, which is where a first-time user
    # gets stuck with no way out.
    if profile == "full":
        declared = a["metrics"]["counts"]["total_findings"]
        if "findings" not in a:
            error(
                "R10",
                "full profile without a findings list: list every finding of the round. If "
                "the round found nothing, declare it with an empty list and total_findings=0",
            )
        elif not findings and declared != 0:
            error(
                "R10",
                f"full profile lists no findings but metrics declare {declared}: either list "
                "them or set the counts to zero. A count without its findings is not a record",
            )

    # R1: every finding whose state joins the residue has its item, and every
    # item with a reference points to an existing finding of the right state.
    if findings:
        refs = {i.get("finding_ref") for i in items if i.get("finding_ref")}
        for h in findings:
            if h["final_state"] in RESIDUE_STATES and h["id"] not in refs:
                error("R1", f"finding {h['id']} ({h['final_state']}) without a residue item")
        for i in items:
            ref = i.get("finding_ref")
            if ref:
                if ref not in by_id:
                    error("R1", f"item {i['id']} references nonexistent finding {ref}")
                else:
                    st = by_id[ref]["final_state"]
                    if st in EXPECTED_CLASS and i["class"] != EXPECTED_CLASS[st]:
                        error("R1", f"item {i['id']} class {i['class']} does not match state {st} of {ref}")

    # R2: no generic markers in text declarations.
    texts = []
    if residue.get("declared_absence"):
        texts.append(("residue.declaration", residue.get("declaration", "")))
    for i in items:
        if "description" in i:
            texts.append((f"residue.items[{i['id']}].description", i["description"]))
    for where, t in texts:
        if t.strip().lower() in GENERIC_MARKERS:
            error("R2", f"generic marker in {where}: '{t}'")

    # R2 bis: unfilled template markers, in any field.
    # Without this, a minimized-profile template would validate straight from the factory.
    def find_template_marker(value, path: str) -> None:
        if isinstance(value, str) and value.startswith(TEMPLATE_MARKER):
            error("R2", f"unfilled template marker in {path}")
        elif isinstance(value, dict):
            for k, v in value.items():
                find_template_marker(v, f"{path}.{k}")
        elif isinstance(value, list):
            for n, v in enumerate(value):
                find_template_marker(v, f"{path}[{n}]")

    find_template_marker(a, "artifact")

    # R3: the abbreviated path is incompatible with the five protected cases (3.2).
    ap = a["event"]["abbreviated_path"]
    if ap.get("used") and ap.get("protected_cases_touched"):
        error("R3", "abbreviated path used on a change that touches protected cases of 3.2")

    # R4: decorrelation: no model reviewer shares a family with the generator.
    gen_family = a["actors"]["generator"]["family"]
    for r in a["actors"]["reviewers"]:
        if r["family"] == gen_family:
            error("R4", f"reviewer {r['reviewer_id']} shares family ({gen_family}) with the generator: no decorrelation")

    # R5: Level A + execution gap demands written acceptance by a lead (section 7).
    if level == "A":
        for i in items:
            if i["class"] == "execution_gap" and "lead_acceptance" not in i:
                error("R5", f"item {i['id']}: execution gap in Level A without lead acceptance (blocks the merge)")

    # R6: counts coherent with the findings list (when present).
    if findings:
        c = a["metrics"]["counts"]

        def count(state: str) -> int:
            return sum(1 for h in findings if h["final_state"] == state)

        expected = {
            ("valid", "incorporated"): count("incorporated"),
            ("valid", "debt_recorded"): count("debt_recorded"),
            ("valid", "owner_decision"): count("owner_decision"),
            ("false_positives", "refuted_verifiable"): count("refuted_verifiable"),
            ("false_positives", "refuted_interpretive"): count("refuted_interpretive"),
        }
        for (group, field), v in expected.items():
            if c[group][field] != v:
                error("R6", f"count {group}.{field}={c[group][field]} but the list has {v}")
        if c["escalated_open"] != count("escalated_open"):
            error("R6", f"escalated_open={c['escalated_open']} but the list has {count('escalated_open')}")
        if c["total_findings"] != len(findings):
            error("R6", f"total_findings={c['total_findings']} but the list has {len(findings)}")

    # R7: in the diff gate, every incorporated finding closes with its fix verified.
    if gate == "diff":
        for h in findings:
            if h["final_state"] == "incorporated":
                v = h.get("fix_verification")
                if not v:
                    error("R7", f"finding {h['id']} incorporated in the diff gate without fix verification")
                elif v["type"] == "pending_in_diff_gate":
                    error("R7", f"finding {h['id']}: fix verification cannot stay pending in the diff gate itself")

    # R8: an interpretive refutation always asks for human attention (section 6).
    for i in items:
        if i.get("refutation_type") == "interpretive" and not i.get("requires_human_attention"):
            error("R8", f"item {i['id']}: interpretive refutation with requires_human_attention=false")

    # R9: the minimized profile admits no free text.
    if profile == "minimized":
        for h in findings:
            for field in MINIMIZED_FORBIDDEN_TEXT_FIELDS & h.keys():
                error("R9", f"finding {h['id']}: field '{field}' forbidden in the minimized profile")
            ev = h.get("evidence", {})
            if "text" in ev or "link" in ev:
                error("R9", f"finding {h['id']}: evidence with text or link in the minimized profile (hash only)")
        for i in items:
            if "description" in i:
                error("R9", f"item {i['id']}: description forbidden in the minimized profile")
            ev = i.get("evidence", {})
            if "text" in ev or "link" in ev:
                error("R9", f"item {i['id']}: evidence with text or link in the minimized profile (hash only)")
        if a["event"]["repository"].startswith("http"):
            error("R9", "minimized profile with a clear repository URL (use a hash or opaque identifier)")

    return e


def validate_artifact(artifact: dict, schema: dict | None = None) -> list[str]:
    """Validate a complete artifact. Returns the list of errors (empty if valid).

    If the schema fails, structural rules are not evaluated: they would
    operate over a shape that is not guaranteed.
    """
    schema = schema or load_schema()
    if isinstance(artifact, dict) and isinstance(artifact.get("esquema"), str) \
            and artifact["esquema"].startswith("residuo/"):
        return [
            "[schema] artifact declares 'esquema: residuo/v0.1' (Spanish keys). "
            "This disensor validates residue/v0.3, which renamed every key and enum "
            "to English. See the ES-EN glossary in the repository README to migrate."
        ]
    errors = schema_errors(artifact, schema)
    if errors:
        return errors
    return rule_errors(artifact)

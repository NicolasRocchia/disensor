"""Render of the residue declaration as a PR comment (Markdown).

Principle of section 9 of the protocol: the declaration lists residue, not
coverage. The comment directs the human reviewer's scrutiny toward what the
cycle could not close, instead of reading as a seal of quality.
"""
from __future__ import annotations

MARKER = "<!-- disensor-gate -->"

CLASS_NAME = {
    "escalation_without_decision": "Escalation without a decision",
    "principal_refutation": "Refutation by the principal model",
    "execution_gap": "Execution gap",
}

STATE_NAME = {
    "incorporated": "incorporated",
    "debt_recorded": "debt recorded",
    "owner_decision": "owner decision",
    "refuted_verifiable": "refuted with evidence",
    "refuted_interpretive": "refuted by judgment",
    "escalated_open": "escalated open",
}


def _item_line(item: dict, profile: str) -> str:
    klass = CLASS_NAME[item["class"]]
    attention = " **(requires human attention)**" if item.get("requires_human_attention") else ""
    ref = f" (finding {item['finding_ref']})" if item.get("finding_ref") else ""
    detail = ""
    if profile == "full" and item.get("description"):
        detail = f": {item['description']}"
    elif item["class"] == "principal_refutation" and item.get("refutation_type"):
        detail = f" ({item['refutation_type']})"
    elif item["class"] == "execution_gap" and item.get("gap_reason"):
        detail = f" ({item['gap_reason'].replace('_', ' ')})"
    evidence = item.get("evidence", {})
    link = f" [evidence]({evidence['link']})" if evidence.get("link") else ""
    acceptance = ""
    if item.get("lead_acceptance"):
        la = item["lead_acceptance"]
        acceptance = f" Accepted in writing by {la['lead']} ({la['record']})."
    return f"- **{klass}**{ref}{detail}{attention}{link}{acceptance}"


def _counts_summary(a: dict) -> str:
    c = a["metrics"]["counts"]
    v = c["valid"]
    fp = c["false_positives"]
    parts = []
    if v["incorporated"]:
        parts.append(f"{v['incorporated']} incorporated")
    if v["debt_recorded"]:
        parts.append(f"{v['debt_recorded']} to recorded debt")
    if v["owner_decision"]:
        parts.append(f"{v['owner_decision']} with an owner decision")
    if fp["refuted_verifiable"]:
        parts.append(f"{fp['refuted_verifiable']} refuted with evidence")
    if fp["refuted_interpretive"]:
        parts.append(f"{fp['refuted_interpretive']} refuted by judgment")
    if c["escalated_open"]:
        parts.append(f"{c['escalated_open']} escalated open")
    detail = ", ".join(parts) if parts else "no findings"
    return f"{c['total_findings']} findings: {detail}."


def render_artifact(a: dict) -> str:
    ev = a["event"]
    ac = a["actors"]
    lines = []
    reviewers = ", ".join(f"{r['model']} ({r['family']})" for r in ac["reviewers"])
    confinements = ", ".join(
        f"{r['confinement']['mode'].replace('_', ' ')}"
        + (" verified" if r["confinement"]["verified"] else " NOT VERIFIED")
        for r in ac["reviewers"]
    )
    lines.append(
        f"### Event `{a['event']['event_id'][:8]}` "
        f"({ev['gate']} gate, Level {ev['criticality_level']}, commit `{ev['head_commit'][:7]}`)"
    )
    lines.append("")
    lines.append(
        f"Generator {ac['generator']['model']} ({ac['generator']['family']}); "
        f"reviewer {reviewers}; confinement: {confinements}. "
        f"{_counts_summary(a)}"
    )
    if ev["abbreviated_path"].get("used"):
        lines.append(f"Abbreviated path used. Justification: {ev['abbreviated_path'].get('justification', '')}")
    lines.append("")
    residue = a["residue"]
    if residue.get("declared_absence"):
        lines.append(f"**No residue.** Express declaration: {residue['declaration']}")
    else:
        lines.append("**Declared residue** (what the cycle could not close by itself):")
        for item in residue["items"]:
            lines.append(_item_line(item, a["profile"]))
    return "\n".join(lines)


def render_comment(valid: list[dict], errors_by_file: dict[str, list[str]],
                   gate_errors: list[str]) -> str:
    """Complete PR comment, with a marker to update it in place."""
    lines = [MARKER, "## Residue declaration", ""]
    if gate_errors or errors_by_file:
        lines.append("**The gate failed.** The PR does not declare residue in a valid form:")
        for msg in gate_errors:
            lines.append(f"- {msg}")
        for file, errs in errors_by_file.items():
            for msg in errs:
                lines.append(f"- `{file}`: {msg}")
        lines.append("")
    for a in valid:
        lines.append(render_artifact(a))
        lines.append("")
    lines.append("---")
    lines.append(
        "This declaration lists residue, not coverage: it directs the human reviewer's "
        "scrutiny toward what remained open instead of reading as a seal of quality. "
        "The machine validates shape and coherence; that the declared residue is the real "
        "residue is controlled by human sampling, not by this gate."
    )
    return "\n".join(lines)

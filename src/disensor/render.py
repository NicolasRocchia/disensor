"""Render of the residue declaration as a PR comment (Markdown).

Principle of section 9 of the protocol: the declaration lists residue, not
coverage. The comment directs the human reviewer's scrutiny toward what the
cycle could not close, instead of reading as a seal of quality.
"""
from __future__ import annotations

import re

MARKER = "<!-- disensor-gate -->"

# El comentario del PR y el resumen del job son markdown que GitHub renderiza, y
# el texto de la declaracion entraba tal cual: `__pycache__` salia en negrita, lo
# que hubiera entre `<!--` y `-->` no se veia, y `[t](u)` era un enlace que decia
# t (#85). El arbitro lee el comentario y el gate valida la declaracion: si
# difieren, lo que el arbitro aprueba no es lo que se declaro. Todo lo que viene
# de la declaracion pasa por `md_literal` o por `md_code`. Cada caso esta medido
# con la API de markdown de GitHub, en modo gfm.
_ENTITIES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
_PUNCTUATION = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
_EMOJI_AHEAD = re.compile(r"[A-Za-z0-9_+-]+:")
_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_BACKTICKS = re.compile(r"`+")
# GitHub no reconoce un codigo cuya cerca pase de 80 comillas: lo de adentro se
# vuelve a leer como markdown, y un `<!--` ahi escondia texto (medido).
_MAX_FENCE = 80
_BLOCK_START = re.compile(r"^( {0,3})([-+#]|[0-9]{1,9}(?=[.)]))")
# Solo http(s) es enlace, como en el informe HTML; el esquema no distingue
# mayusculas, y GitHub conserva `HTTPS://` como enlace (medido).
_LINKABLE = re.compile(r"^https?://", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _plain(s: str, brackets: bool = False) -> str:
    """One line with no code in it, escaped so that GitHub shows it as written.

    Only what GitHub would read as markup is touched: the same markdown is also
    what the gate prints to the CI log, where every escape is noise. `brackets`
    escapes all of them, for the text of a link, where an unpaired one breaks it.
    """
    out = []
    for i, ch in enumerate(s):
        prev = s[i - 1] if i else ""
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if ch in _ENTITIES:
            out.append(_ENTITIES[ch])
        elif ch == "\\":
            # Antes de un signo lo escaparia, y al final de la linea es un salto;
            # antes de cualquier otra cosa se ve tal cual (`C:\Users`).
            out.append("\\\\" if nxt == "" or nxt in _PUNCTUATION else "\\")
        elif ch in "*~`":
            out.append("\\" + ch)
        elif ch == "_":
            # Entre dos letras o numeros no abre ni cierra enfasis: `gap_reason`
            # queda como esta, y `__pycache__` no.
            out.append("_" if prev.isalnum() and nxt.isalnum() else "\\_")
        elif ch == "]" and (brackets or nxt == "("):
            # Un enlace o una imagen necesitan `](`; `[G6]` solo, no.
            out.append("\\]")
        elif ch == "[" and brackets:
            out.append("\\[")
        elif ch == "$":
            # GitHub arma formulas con `$...$` despues de parsear, y ni la barra
            # ni la entidad lo evitan: con `\phantom{}` adentro, el texto no se
            # ve. Un elemento propio corta el nodo de texto, que es lo que su
            # documentacion recomienda para un `$` literal.
            out.append("<span>$</span>")
        elif ch == ":" and _EMOJI_AHEAD.match(s, i + 1):
            # `:x:` es un emoji aunque los dos puntos vayan escapados.
            out.append("<span>:</span>")
        elif ch == ":" and s.startswith("//", i + 1):
            # Sin autolink: GitHub arma el enlace con el texto crudo, y adentro
            # de una URL las barras de los otros escapes quedaban a la vista.
            out.append("\\:")
        elif ch == "." and s[max(0, i - 3):i].lower() == "www":
            out.append("\\.")
        else:
            out.append(ch)
    return "".join(out)


def _line(s: str) -> str:
    """One line, with the backticks that pair up kept as code.

    The corpus writes paths and commands between backticks, so a pair of them is
    code, which shows its content literally. An unpaired backtick is escaped: left
    alone, it could pair with one that comes later in the comment. Code spans are
    found the way CommonMark finds them, a run of backticks closed by the next run
    of the same length, and that is safe because everything around them is escaped.
    """
    out = []
    i = start = 0
    while True:
        opening = _BACKTICKS.search(s, i)
        if opening is None:
            break
        closing = None
        if len(opening.group()) <= _MAX_FENCE:
            for candidate in _BACKTICKS.finditer(s, opening.end()):
                if len(candidate.group()) == len(opening.group()):
                    closing = candidate
                    break
        if closing is None:
            i = opening.end()
            continue
        out.append(_plain(s[start:opening.start()]))
        out.append(s[opening.start():closing.end()])
        i = start = closing.end()
    out.append(_plain(s[start:]))
    return "".join(out)


def md_literal(value) -> str:
    """Text from a declaration, for a markdown line, shown as it was written.

    A line break becomes `<br>`: a real one would let the text start a heading, a
    list or a block of its own. The only line the text can start is the one it
    is put on, right after a list marker in the error lines, so a first character
    that would open a heading or a list there is escaped too.
    """
    text = "" if value is None else str(value)
    md = "<br>".join(_line(part) for part in _LINE_BREAK.split(text))
    start = _BLOCK_START.match(md)
    if start is None:
        return md
    lead, mark = start.groups()
    rest = md[start.end():]
    # `1.` o `1)` abren una lista por el signo que sigue al numero: se escapa ese.
    return f"{lead}{mark}\\{rest}" if mark.isdigit() else f"{lead}\\{mark}{rest}"


def md_code(value) -> str:
    """A literal as a code span that its own backticks cannot close."""
    text = _LINE_BREAK.sub(" ", "" if value is None else str(value))
    if not text:
        return ""
    fence = "`" * (max((len(m) for m in _BACKTICKS.findall(text)), default=0) + 1)
    if len(fence) > _MAX_FENCE:
        # Una cerca tan larga no la reconoce GitHub: va como texto escapado.
        return _plain(text)
    # CommonMark saca un espacio de cada punta cuando hay en las dos; el relleno
    # es para que se lleve este y no uno del texto.
    pad = " " if (
        text[0] == "`" or text[-1] == "`" or (text[0] == " " and text[-1] == " " and text.strip())
    ) else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def _evidence_link(link: str) -> str:
    """The link with its destination as the visible text, so it cannot say something else."""
    text = "<br>".join(_plain(part, brackets=True) for part in _LINE_BREAK.split(link))
    if not _LINKABLE.match(link) or _CONTROL.search(link):
        return text
    # En el destino se leen escapes y entidades: estos cuatro llegan tal cual.
    destination = (
        link.replace("&", "&amp;").replace("\\", "\\\\").replace("<", "\\<").replace(">", "\\>")
    )
    return f"[{text}](<{destination}>)"


# One entry per class the schema admits, and the suite checks that against the
# enum: v0.4 added the two reviewer classes and this table did not follow, so a
# declaration that validated aborted the gate with KeyError while the comment
# was being built, also with --no-comment (#56).
CLASS_NAME = {
    "escalation_without_decision": "Escalation without a decision",
    "principal_refutation": "Refutation by the principal model",
    "execution_gap": "Execution gap",
    "reviewer_correlation": "Reviewer correlated with the generator",
    "reviewer_hardening_gap": "Reviewer hardening not verified",
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
    # What the item is about: the finding it was born from, the reviewer the two
    # reviewer classes name (R11, R12), or both: the schema allows both on one
    # item, and the reviewer goes on the line in every profile, because without
    # it the item does not say which reviewer was degraded.
    about = []
    if item.get("finding_ref"):
        about.append(f"finding {md_literal(item['finding_ref'])}")
    if item.get("reviewer_ref"):
        about.append(f"reviewer {md_literal(item['reviewer_ref'])}")
    ref = f" ({', '.join(about)})" if about else ""
    detail = ""
    if profile == "full" and item.get("description"):
        detail = f": {md_literal(item['description'])}"
    elif item["class"] == "principal_refutation" and item.get("refutation_type"):
        detail = f" ({md_literal(item['refutation_type'])})"
    elif item["class"] == "execution_gap" and item.get("gap_reason"):
        detail = f" ({md_literal(item['gap_reason'].replace('_', ' '))})"
    evidence = item.get("evidence", {})
    # El destino a la vista: `[evidence](u)` decia "evidence" y llevaba a
    # cualquier lado, y un `)` o un espacio en `u` cortaban el enlace.
    link = f" (evidence: {_evidence_link(evidence['link'])})" if evidence.get("link") else ""
    acceptance = ""
    if item.get("lead_acceptance"):
        la = item["lead_acceptance"]
        acceptance = f" Accepted in writing by {md_literal(la['lead'])} ({md_literal(la['record'])})."
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
    reviewers = ", ".join(
        f"{md_literal(r['model'])} ({md_literal(r['family'])})" for r in ac["reviewers"]
    )
    confinements = ", ".join(
        md_literal(r["confinement"]["mode"].replace("_", " "))
        + (" verified" if r["confinement"]["verified"] else " NOT VERIFIED")
        for r in ac["reviewers"]
    )
    lines.append(
        f"### Event {md_code(a['event']['event_id'][:8])} "
        f"({md_literal(ev['gate'])} gate, Level {md_literal(ev['criticality_level'])}, "
        f"commit {md_code(ev['head_commit'][:7])})"
    )
    lines.append("")
    lines.append(
        f"Generator {md_literal(ac['generator']['model'])} ({md_literal(ac['generator']['family'])}); "
        f"reviewer {reviewers}; confinement: {confinements}. "
        f"{_counts_summary(a)}"
    )
    if ev["abbreviated_path"].get("used"):
        justification = md_literal(ev["abbreviated_path"].get("justification", ""))
        lines.append(f"Abbreviated path used. Justification: {justification}")
    lines.append("")
    residue = a["residue"]
    if residue.get("declared_absence"):
        lines.append(f"**No residue.** Express declaration: {md_literal(residue['declaration'])}")
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
        # Los mensajes citan valores de la declaracion (un id, un marcador
        # generico, lo que el esquema rechazo), y el nombre del archivo lo elige
        # quien lo agrega: pasan por el mismo escape. Las comillas invertidas
        # de los mensajes siguen siendo codigo.
        for msg in gate_errors:
            lines.append(f"- {md_literal(msg)}")
        for file, errs in errors_by_file.items():
            for msg in errs:
                lines.append(f"- {md_code(file)}: {md_literal(msg)}")
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

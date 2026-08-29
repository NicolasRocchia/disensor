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


CURRENT = "residue/v0.4"

# Un recurso por version, inmutable. Un solo archivo con todas las versiones en
# un enum alcanzaba para dos y deja de alcanzar para tres: una declaracion vieja
# terminaba validandose contra la forma combinada, aceptando campos de una
# version que no existia cuando se escribio (issue #13). El discriminador se lee
# primero y elige forma Y reglas juntas; una version ausente o desconocida falla.
SCHEMA_FILES = {
    "residue/v0.2": "residue.schema.v0.2.json",
    "residue/v0.3": "residue.schema.v0.3.json",
    "residue/v0.4": "residue.schema.v0.4.json",
}


ORDER = tuple(SCHEMA_FILES)


def applies_from(declared: str, introduced: str) -> bool:
    """Si una regla introducida en `introduced` alcanza a `declared`.

    El despacho por version elige el esquema; esto es su otra mitad. Sin esto,
    endurecer una regla reescribe el contrato de los identificadores congelados
    y una declaracion emitida bajo el suyo pasa de valida a invalida al
    actualizar el paquete, que es justo lo que el README promete que no ocurre.
    """
    if declared not in ORDER or introduced not in ORDER:
        return False
    return ORDER.index(declared) >= ORDER.index(introduced)


def load_schema(version: str | None = None) -> dict:
    """Load the schema of a version (the current one by default)."""
    name = SCHEMA_FILES[version or CURRENT]
    with resources.files("disensor").joinpath(name).open(encoding="utf-8") as f:
        return json.load(f)


def schema_errors(artifact: dict, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    return [
        f"[schema] {'/'.join(str(p) for p in err.path) or '(root)'}: {err.message}"
        for err in sorted(validator.iter_errors(artifact), key=lambda x: list(x.path))
    ]


def _independence_errors(a: dict, gen_family: str, error) -> None:
    """R4 in v0.4: declared independence has to match the declared families.

    A string nobody checks is worth nothing: `cross_family` would become the
    value everyone writes, degraded rounds included, and the whole point of
    recording the degradation is that it stays visible. The identity of the
    models themselves is still declared and unverifiable; what this closes is
    the cheapest lie, the one where the artifact contradicts itself.

    Every reviewer below cross_family carries a residue item naming it, and an
    unverified hardening carries its own: they are different risks. Correlation
    is about what the reviewer could not see; hardening is about what the
    reviewed material could tell the reviewer.
    """
    items = a["residue"].get("items", [])
    refs = {
        (i.get("class"), i.get("reviewer_ref"))
        for i in items
        if i.get("class") in ("reviewer_correlation", "reviewer_hardening_gap")
    }
    level = a["event"]["criticality_level"]

    for r in a["actors"]["reviewers"]:
        rid = r["reviewer_id"]
        independence = r["independence"]
        distinta = r["family"] != gen_family

        if independence == "cross_family" and not distinta:
            error("R4", f"reviewer {rid} declares cross_family and shares family ({gen_family}) with the generator")
        # El modelo, no solo la familia: declararse distinto del generador
        # siendo exactamente el mismo modelo falsea el registro que v0.4 dice
        # estructurar.
        gen_model = a["actors"]["generator"].get("model")
        if independence == "same_family_distinct_model" and r.get("model") == gen_model:
            error(
                "R4",
                f"reviewer {rid} declares same_family_distinct_model with the same model as the "
                "generator: that is same_model_fresh_context",
            )
        if independence == "same_model_fresh_context" and r.get("model") != gen_model:
            error(
                "R4",
                f"reviewer {rid} declares same_model_fresh_context with model "
                f"{r.get('model')!r} while the generator declares {gen_model!r}",
            )
        if independence != "cross_family" and distinta:
            error(
                "R4",
                f"reviewer {rid} declares {independence} and comes from a different family "
                f"({r['family']} vs {gen_family}): declared independence has to match the families declared",
            )
        if independence != "cross_family":
            if level == "A":
                error(
                    "R4",
                    f"reviewer {rid}: Level A demands cross_family. A degraded mode is declarable, "
                    "not admissible at the level the protocol reserves for what cannot be undone",
                )
            if "fallback_reason" not in r:
                error(
                    "R4",
                    f"reviewer {rid}: independence below cross_family without fallback_reason. "
                    "Why the round settled for less is part of what happened",
                )
            if ("reviewer_correlation", rid) not in refs:
                error(
                    "R11",
                    f"reviewer {rid}: independence {independence} without a reviewer_correlation "
                    "residue item naming it. The errors the reviewer shares with the generator "
                    "were not covered by this round, and that is residue",
                )
        if r.get("hardening") == "unverified" and ("reviewer_hardening_gap", rid) not in refs:
            error(
                "R12",
                f"reviewer {rid}: unverified hardening without a reviewer_hardening_gap residue "
                "item naming it. The reviewed material could have addressed the reviewer before "
                "the brief did",
            )


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
    #
    # Presencia y no truthiness, por lo mismo que R6: desde que la lista vacia
    # es un resultado valido, un item que referencia un hallazgo inexistente
    # quedaba sin que nadie lo mirara. Con la lista vacia no hay estados que
    # unir al residuo, pero cualquier referencia sigue apuntando a la nada.
    if a.get("findings") is not None:
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

    # R4: decorrelation. Hasta v0.3 la regla era absoluta: familia distinta o la
    # declaracion se rechaza. Eso dejaba sin poder declarar nada a quien no tiene
    # un segundo modelo, aunque dijera la verdad sobre lo que hizo, y empujaba la
    # unica salida honesta fuera del registro. Desde v0.4 la independencia se
    # DECLARA siempre y la regla verifica que lo declarado coincida con las
    # familias declaradas; el minimo exigible por nivel lo fija la politica, y
    # cualquier cosa por debajo de cross_family arrastra su propio residuo.
    gen_family = a["actors"]["generator"]["family"]
    if applies_from(a["schema"], "residue/v0.4"):
        _independence_errors(a, gen_family, error)
    else:
        for r in a["actors"]["reviewers"]:
            if r["family"] == gen_family:
                error("R4", f"reviewer {r['reviewer_id']} shares family ({gen_family}) with the generator: no decorrelation")

    # R5: Level A + execution gap demands written acceptance by a lead (section 7).
    if level == "A":
        for i in items:
            if i["class"] == "execution_gap" and "lead_acceptance" not in i:
                error("R5", f"item {i['id']}: execution gap in Level A without lead acceptance (blocks the merge)")

    # R6: counts coherent with the findings list (when present).
    #
    # Presencia y no truthiness: con la lista vacia, la guarda anterior salteaba
    # toda la coherencia, y un artefacto que declaraba cero hallazgos podia
    # contar tres incorporados y un escalado en los subconteos sin que nada lo
    # mirara. Cero hallazgos es un resultado valido; cero hallazgos con conteos
    # que dicen otra cosa no lo es.
    if a.get("findings") is not None:
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

    # R13: local identifiers are unique, and every reference resolves.
    #
    # Desde v0.4, que es la version vigente cuando se introdujo: una declaracion
    # emitida bajo un identificador anterior se sigue juzgando con las reglas de
    # su contrato.
    if applies_from(a["schema"], "residue/v0.4"):
        #
        # El esquema ya declara que `origin` es un reviewer_id y que un item de
        # correlacion cubre UN revisor degradado. Sin esto, un hallazgo podia quedar
        # atribuido a alguien que no esta en la declaracion, que es exactamente lo
        # que un registro de auditoria no puede permitirse.
        ids_revisores = [r["reviewer_id"] for r in a["actors"]["reviewers"]]
        for etiqueta, valores in (
            ("reviewer_id", ids_revisores),
            ("finding id", [h["id"] for h in findings]),
            ("residue item id", [i["id"] for i in items]),
        ):
            repetidos = sorted({v for v in valores if valores.count(v) > 1})
            for v in repetidos:
                error("R13", f"{etiqueta} {v!r} is declared more than once: an identifier that names "
                             "two things cannot anchor a reference")
        conocidos = set(ids_revisores)
        for h in findings:
            if h["origin"] not in conocidos:
                error("R13", f"finding {h['id']} is attributed to reviewer {h['origin']!r}, which is "
                             "not among the declared reviewers")
        for i in items:
            ref = i.get("reviewer_ref")
            if ref is not None and ref not in conocidos:
                error("R13", f"item {i['id']} references reviewer {ref!r}, which is not among the "
                             "declared reviewers")

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

    # R9: the minimized profile strips the free text listed below. It narrows
    # the leak channel; it does not close it: the fields this rule does not
    # reach still admit free prose. The documents say so; this comment used to
    # claim the opposite.
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

    The declared version is read FIRST and selects shape and rules together. A
    single combined shape let a v0.2 declaration borrow fields from v0.3, which
    is the opposite of what versioning is for: a record is validated under the
    rules of the version it was written under, and nothing else.

    An explicit `schema` argument still wins, for callers that need to check an
    artifact against a specific version on purpose.
    """
    if isinstance(artifact, dict) and isinstance(artifact.get("esquema"), str) \
            and artifact["esquema"].startswith("residuo/"):
        return [
            "[schema] artifact declares 'esquema: residuo/v0.1' (Spanish keys). "
            f"This disensor validates {CURRENT}, which renamed every key and enum "
            "to English. See the ES-EN glossary in the repository README to migrate."
        ]
    if schema is None:
        declared = artifact.get("schema") if isinstance(artifact, dict) else None
        if declared not in SCHEMA_FILES:
            conocidas = ", ".join(sorted(SCHEMA_FILES))
            return [
                f"[schema] the artifact declares schema {declared!r}, which this disensor does "
                f"not know how to validate (it reads {conocidas}). A declaration is validated "
                "under the version it declares; guessing one would validate it under rules it "
                "was never written for."
            ]
        schema = load_schema(declared)
    errors = schema_errors(artifact, schema)
    if errors:
        return errors
    return rule_errors(artifact)

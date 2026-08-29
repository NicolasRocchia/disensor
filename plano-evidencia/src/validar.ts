/**
 * TypeScript port of the residue artifact validator (schema v0.2 to v0.4).
 *
 * Mirror of src/disensor/rules.py (the Python reference implementation).
 * Parity is not ensured by reading the code: it is ensured by running the
 * conformance vectors of spec/vectors. Same verdict and same rule labels
 * per vector, or the port is broken.
 *
 * Parity note with the reference: "format" (uuid, date-time) is not
 * validated, same as Python jsonschema without a format checker.
 */
import Ajv2020 from "ajv/dist/2020.js";
import type { ValidateFunction } from "ajv";

export const GENERIC_MARKERS = new Set([
  // English
  "n/a", "na", "none", "all resolved", "applied", "ok", "no residue",
  "-", "not applicable", "done", "resolved",
  // Spanish (teams write in their own language; laziness has no border)
  "ninguno", "ninguna", "todo resuelto", "aplicado", "sin residuo", "no aplica",
]);

const RESIDUE_STATES = new Set([
  "escalated_open", "refuted_verifiable", "refuted_interpretive",
]);

const EXPECTED_CLASS: Record<string, string> = {
  escalated_open: "escalation_without_decision",
  refuted_verifiable: "principal_refutation",
  refuted_interpretive: "principal_refutation",
};

const MINIMIZED_FORBIDDEN_TEXT_FIELDS = ["title", "description", "location"];

const TEMPLATE_MARKER = "FILL_IN";

type Artifact = any;

export function compilarSchema(schema: object): ValidateFunction {
  const ajv = new Ajv2020({ strict: false, validateFormats: false, allErrors: true });
  return ajv.compile(schema);
}

export function erroresSchema(a: Artifact, validar: ValidateFunction): string[] {
  const ok = validar(a);
  if (ok) return [];
  return (validar.errors ?? []).map(
    (e) => `[schema] ${e.instancePath || "(root)"}: ${e.message ?? ""}`,
  );
}

export function erroresReglas(a: Artifact): string[] {
  const e: string[] = [];
  const error = (rule: string, msg: string) => e.push(`[${rule}] ${msg}`);

  const profile: string = a.profile;
  const findings: any[] = a.findings ?? [];
  const residue = a.residue;
  const items: any[] = residue.items ?? [];
  const byId = new Map<string, any>(findings.map((h) => [h.id, h]));
  const gate: string = a.event.gate;
  const level: string = a.event.criticality_level;

  // R0: without a human arbiter the event does not comply with the protocol (section 6).
  if (!a.actors.human_arbiter.present) {
    error("R0", "event without a human arbiter present");
  }

  // R10: in the full profile, the findings list is mandatory. What has to be
  // there is the LIST, not an element in it: a round that found nothing is a
  // valid result and the reference accepts it. Rejecting the empty list made
  // the two implementations disagree on artifacts that already exist.
  if (profile === "full" && !Array.isArray(a.findings)) {
    error("R10", "full profile without a findings list");
  } else if (profile === "full" && findings.length === 0
             && a.metrics?.counts?.total_findings !== 0) {
    // La otra mitad de R10, que la referencia tiene y que se perdio al
    // simplificar: una lista vacia cuyo total dice otra cosa. R6 tambien lo
    // caza, pero el contrato es que coincidan las ETIQUETAS, no solo el
    // veredicto, y el detalle del error de la ingesta sale de ellas.
    const n = a.metrics?.counts?.total_findings;
    error("R10", `full profile lists no findings but metrics declare ${n}: either list `
                 + "them or set the counts to zero. A count without its findings is not a record");
  }

  // R1: coherence between residue-joining states and their items.
  // Presence, not truthiness: same reason as R6. An item referencing a finding
  // that is not there was going unchecked once the empty list became valid.
  if (Array.isArray(a.findings)) {
    const refs = new Set(items.map((i) => i.finding_ref).filter(Boolean));
    for (const h of findings) {
      if (RESIDUE_STATES.has(h.final_state) && !refs.has(h.id)) {
        error("R1", `finding ${h.id} (${h.final_state}) without a residue item`);
      }
    }
    for (const i of items) {
      const ref = i.finding_ref;
      if (ref) {
        if (!byId.has(ref)) {
          error("R1", `item ${i.id} references nonexistent finding ${ref}`);
        } else {
          const st = byId.get(ref).final_state;
          if (st in EXPECTED_CLASS && i.class !== EXPECTED_CLASS[st]) {
            error("R1", `item ${i.id} class ${i.class} does not match state ${st} of ${ref}`);
          }
        }
      }
    }
  }

  // R2: no generic markers in text declarations.
  const texts: Array<[string, string]> = [];
  if (residue.declared_absence) {
    texts.push(["residue.declaration", residue.declaration ?? ""]);
  }
  for (const i of items) {
    if (typeof i.description === "string") {
      texts.push([`residue.items[${i.id}].description`, i.description]);
    }
  }
  for (const [where, t] of texts) {
    if (GENERIC_MARKERS.has(t.trim().toLowerCase())) {
      error("R2", `generic marker in ${where}: '${t}'`);
    }
  }

  // R2 bis: unfilled template markers, in any field.
  const findTemplateMarker = (value: unknown, path: string): void => {
    if (typeof value === "string" && value.startsWith(TEMPLATE_MARKER)) {
      error("R2", `unfilled template marker in ${path}`);
    } else if (Array.isArray(value)) {
      value.forEach((v, n) => findTemplateMarker(v, `${path}[${n}]`));
    } else if (value !== null && typeof value === "object") {
      for (const [k, v] of Object.entries(value)) findTemplateMarker(v, `${path}.${k}`);
    }
  };
  findTemplateMarker(a, "artifact");

  // R3: the abbreviated path is incompatible with the five protected cases (3.2).
  const ap = a.event.abbreviated_path;
  if (ap.used && (ap.protected_cases_touched ?? []).length > 0) {
    error("R3", "abbreviated path used on a change that touches protected cases of 3.2");
  }

  // R4: decorrelation between generator and reviewers.
  //
  // Two shapes, dispatched by the declared version. Up to v0.3 it is absolute:
  // same family is a violation, and a round without a second family cannot be
  // declared at all. From v0.4 independence is always DECLARED, and the rule
  // checks that what was declared matches the families and models the
  // declaration names, with its own minimums per level and its own residue.
  const genFamily: string = a.actors.generator.family;
  if (appliesFrom(a.schema, "residue/v0.4")) {
    const refs = new Set(
      items
        .filter((i: any) => i.class === "reviewer_correlation" || i.class === "reviewer_hardening_gap")
        .map((i: any) => `${i.class}|${i.reviewer_ref}`),
    );
    const genModel = a.actors.generator.model;
    for (const r of a.actors.reviewers) {
      const rid = r.reviewer_id;
      const independence = r.independence;
      const distinta = r.family !== genFamily;

      if (independence === "cross_family" && !distinta) {
        error("R4", `reviewer ${rid} declares cross_family and shares family (${genFamily}) with the generator`);
      }
      if (independence === "same_family_distinct_model" && r.model === genModel) {
        error("R4", `reviewer ${rid} declares same_family_distinct_model with the same model as the generator: that is same_model_fresh_context`);
      }
      if (independence === "same_model_fresh_context" && r.model !== genModel) {
        error("R4", `reviewer ${rid} declares same_model_fresh_context with model '${r.model}' while the generator declares '${genModel}'`);
      }
      if (independence !== "cross_family" && distinta) {
        error("R4", `reviewer ${rid} declares ${independence} and comes from a different family (${r.family} vs ${genFamily}): declared independence has to match the families declared`);
      }
      if (independence !== "cross_family") {
        if (level === "A") {
          error("R4", `reviewer ${rid}: Level A demands cross_family. A degraded mode is declarable, not admissible at the level the protocol reserves for what cannot be undone`);
        }
        if (!("fallback_reason" in r)) {
          error("R4", `reviewer ${rid}: independence below cross_family without fallback_reason. Why the round settled for less is part of what happened`);
        }
        if (!refs.has(`reviewer_correlation|${rid}`)) {
          error("R11", `reviewer ${rid}: independence ${independence} without a reviewer_correlation residue item naming it. The errors the reviewer shares with the generator were not covered by this round, and that is residue`);
        }
      }
      if (r.hardening === "unverified" && !refs.has(`reviewer_hardening_gap|${rid}`)) {
        error("R12", `reviewer ${rid}: unverified hardening without a reviewer_hardening_gap residue item naming it. The reviewed material could have addressed the reviewer before the brief did`);
      }
    }
  } else {
    for (const r of a.actors.reviewers) {
      if (r.family === genFamily) {
        error("R4", `reviewer ${r.reviewer_id} shares family (${genFamily}) with the generator: no decorrelation`);
      }
    }
  }

  // R5: Level A + execution gap demands written acceptance (section 7).
  if (level === "A") {
    for (const i of items) {
      if (i.class === "execution_gap" && !("lead_acceptance" in i)) {
        error("R5", `item ${i.id}: execution gap in Level A without lead acceptance (blocks the merge)`);
      }
    }
  }

  // R6: counts coherent with the findings list.
  //
  // Presence, not truthiness: the empty list used to skip the whole coherence
  // check on both sides, so a declaration of zero findings could carry counts
  // saying otherwise.
  if (Array.isArray(a.findings)) {
    const c = a.metrics.counts;
    const count = (st: string) => findings.filter((h) => h.final_state === st).length;
    const expected: Array<[string, string, number]> = [
      ["valid", "incorporated", count("incorporated")],
      ["valid", "debt_recorded", count("debt_recorded")],
      ["valid", "owner_decision", count("owner_decision")],
      ["false_positives", "refuted_verifiable", count("refuted_verifiable")],
      ["false_positives", "refuted_interpretive", count("refuted_interpretive")],
    ];
    for (const [group, field, v] of expected) {
      if (c[group][field] !== v) {
        error("R6", `count ${group}.${field}=${c[group][field]} but the list has ${v}`);
      }
    }
    if (c.escalated_open !== count("escalated_open")) {
      error("R6", `escalated_open=${c.escalated_open} but the list has ${count("escalated_open")}`);
    }
    if (c.total_findings !== findings.length) {
      error("R6", `total_findings=${c.total_findings} but the list has ${findings.length}`);
    }
  }

  // R13: local identifiers are unique, and every reference resolves.
  //
  // The schema already states that `origin` is a reviewer_id and that a
  // correlation item covers ONE degraded reviewer. Without this, a finding
  // could stay attributed to someone who is not in the declaration, which is
  // exactly what an audit record cannot afford.
  // Desde residue/v0.4, que es la version vigente cuando se introdujo: una
  // declaracion emitida bajo un identificador anterior se sigue juzgando con las
  // reglas de su contrato.
  const idsRevisores = (a.actors?.reviewers ?? []).map((r: any) => r.reviewer_id);
  if (appliesFrom(a.schema, "residue/v0.4")) {
  const grupos: Array<[string, any[]]> = [
    ["reviewer_id", idsRevisores],
    ["finding id", findings.map((h: any) => h.id)],
    ["residue item id", items.map((i: any) => i.id)],
  ];
  for (const [etiqueta, valores] of grupos) {
    const repetidos = [...new Set(valores.filter((v, _i, xs) => xs.filter((y) => y === v).length > 1))].sort();
    for (const v of repetidos) {
      error("R13", `${etiqueta} '${v}' is declared more than once: an identifier that names `
                   + "two things cannot anchor a reference");
    }
  }
  const conocidos = new Set(idsRevisores);
  for (const h of findings) {
    if (!conocidos.has(h.origin)) {
      error("R13", `finding ${h.id} is attributed to reviewer '${h.origin}', which is not among `
                   + "the declared reviewers");
    }
  }
  for (const i of items) {
    if (i.reviewer_ref !== undefined && !conocidos.has(i.reviewer_ref)) {
      error("R13", `item ${i.id} references reviewer '${i.reviewer_ref}', which is not among the `
                   + "declared reviewers");
    }
  }

  }

  // R7: in the diff gate, every incorporated finding closes with its fix verified.
  if (gate === "diff") {
    for (const h of findings) {
      if (h.final_state === "incorporated") {
        const v = h.fix_verification;
        if (!v) {
          error("R7", `finding ${h.id} incorporated in the diff gate without fix verification`);
        } else if (v.type === "pending_in_diff_gate") {
          error("R7", `finding ${h.id}: fix verification cannot stay pending in the diff gate itself`);
        }
      }
    }
  }

  // R8: an interpretive refutation always asks for human attention.
  for (const i of items) {
    if (i.refutation_type === "interpretive" && !i.requires_human_attention) {
      error("R8", `item ${i.id}: interpretive refutation with requires_human_attention=false`);
    }
  }

  // R9: the minimized profile strips the free text listed below. It narrows
  // the leak channel; it does not close it (same wording as the reference).
  if (profile === "minimized") {
    for (const h of findings) {
      for (const field of MINIMIZED_FORBIDDEN_TEXT_FIELDS) {
        if (field in h) error("R9", `finding ${h.id}: field '${field}' forbidden in the minimized profile`);
      }
      const ev = h.evidence ?? {};
      if ("text" in ev || "link" in ev) {
        error("R9", `finding ${h.id}: evidence with text or link in the minimized profile (hash only)`);
      }
    }
    for (const i of items) {
      if ("description" in i) error("R9", `item ${i.id}: description forbidden in the minimized profile`);
      const ev = i.evidence ?? {};
      if ("text" in ev || "link" in ev) {
        error("R9", `item ${i.id}: evidence with text or link in the minimized profile (hash only)`);
      }
    }
    if (String(a.event.repository).startsWith("http")) {
      error("R9", "minimized profile with a clear repository URL (use a hash or opaque identifier)");
    }
  }

  return e;
}

/**
 * Validates a complete artifact. If the schema fails, rules are not evaluated
 * (same semantics as the reference): they would operate over an unguaranteed shape.
 */
export const SCHEMA_FILES: Record<string, string> = {
  "residue/v0.2": "residue.schema.v0.2.json",
  "residue/v0.3": "residue.schema.v0.3.json",
  "residue/v0.4": "residue.schema.v0.4.json",
};

/**
 * The versions whose RULES this port implements.
 *
 * The JSON Schema of a newer version may well load here, but validating with it
 * while running v0.3 rules would return "valid" without ever having checked the
 * rules that version added. A stated limit beats a verdict that does not hold.
 */
export const SUPPORTED = new Set(Object.keys(SCHEMA_FILES));

/**
 * Whether a rule introduced in `introduced` reaches an artifact declaring
 * `declared`. A rule is introduced in one version and holds from there on: an
 * equality against the current version would silently drop the rule's newer
 * shape the day the next version opens, with nothing failing to say so.
 */
/**
 * The form of a schema identifier: `residue/v<major>.<minor>`, two numeric
 * components and nothing else. Without it this port read `residue/v0.` as
 * (0, 0) and `residue/v0.1e1` as (0, 10), both of which the reference rejects,
 * and two parsers that disagree disagree about which rules apply. No leading
 * zeros: `v0.04` and `v0.4` would be two spellings of one version, and a
 * frozen identifier has one.
 */
const VERSION_FORM = /^residue\/v(0|[1-9]\d*)\.(0|[1-9]\d*)$/;

export function versionKeyOf(id: string): [number, number] {
  const m = VERSION_FORM.exec(id);
  if (m === null) {
    throw new Error(`'${id}' is not a schema identifier: the form is residue/v<major>.<minor>`);
  }
  return [Number(m[1]), Number(m[2])];
}

/**
 * The known versions in order, for messages and for whoever needs it. Ordinality
 * is NOT resolved by looking up positions here: a derived order is a place to be
 * wrong, and a test over it passes just the same with the derivation broken as
 * long as the map happens to be written in order. The keys get compared.
 */
export const ORDER: string[] = Object.keys(SCHEMA_FILES).sort((a, b) => {
  const [ma, na] = versionKeyOf(a);
  const [mb, nb] = versionKeyOf(b);
  return ma !== mb ? ma - mb : na - nb;
});

/**
 * Whether a rule introduced in `introduced` reaches an artifact declaring
 * `declared`. A rule is introduced in one version and holds from there on: an
 * equality against the current version would silently drop the rule's newer
 * shape the day the next version opens, with nothing failing to say so.
 *
 * `declared` comes from the artifact, from outside: unknown is false, and the
 * dispatch rejects it on its own. `introduced` is written by whoever programs
 * the rule: a typo there would silently disable the rule for every version, so
 * it throws.
 */
export function appliesFrom(declared: string, introduced: string): boolean {
  if (!(introduced in SCHEMA_FILES)) {
    throw new Error(
      `rule introduced in '${introduced}', which is not a known schema version `
      + `(${ORDER.join(", ")}). A typo here would silently disable the rule for every version.`,
    );
  }
  if (!(declared in SCHEMA_FILES)) return false;
  const [md, nd] = versionKeyOf(declared);
  const [mi, ni] = versionKeyOf(introduced);
  return md !== mi ? md > mi : nd >= ni;
}

export function versionOf(a: Artifact): string | null {
  if (a === null || typeof a !== "object" || Array.isArray(a)) return null;
  return typeof a.schema === "string" ? a.schema : null;
}

export function validarArtefacto(a: Artifact, validar: ValidateFunction): string[] {
  const version = versionOf(a);
  if (version !== null && !SUPPORTED.has(version)) {
    return [
      `[schema] artifact declares '${version}'. This TypeScript port implements the rules of `
      + `${[...SUPPORTED].join(", ")}. Validating it here would report a verdict without having `
      + "run the rules that version added: use the reference implementation.",
    ];
  }
  if (a !== null && typeof a === "object" && !Array.isArray(a)
      && typeof a.esquema === "string" && a.esquema.startsWith("residuo/")) {
    return [
      "[schema] artifact declares 'esquema: residuo/v0.1' (Spanish keys). "
      + `This validator checks ${[...SUPPORTED].join(", ")}, which renamed every `
      + "key and enum to English. See the ES-EN glossary in the repository README "
      + "to migrate.",
    ];
  }
  const es = erroresSchema(a, validar);
  if (es.length > 0) return es;
  return erroresReglas(a);
}

export function etiquetas(errores: string[]): string[] {
  const tags = new Set<string>();
  for (const e of errores) {
    if (e.startsWith("[") && e.includes("]")) tags.add(e.slice(1, e.indexOf("]")));
  }
  return [...tags].sort();
}

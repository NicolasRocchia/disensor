/**
 * TypeScript port of the residue artifact validator (schema v0.2 and v0.3).
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
  const genFamily: string = a.actors.generator.family;
  for (const r of a.actors.reviewers) {
    if (r.family === genFamily) {
      error("R4", `reviewer ${r.reviewer_id} shares family (${genFamily}) with the generator: no decorrelation`);
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
};

/**
 * The versions whose RULES this port implements.
 *
 * The JSON Schema of a newer version may well load here, but validating with it
 * while running v0.3 rules would return "valid" without ever having checked the
 * rules that version added. A stated limit beats a verdict that does not hold.
 */
export const SUPPORTED = new Set(Object.keys(SCHEMA_FILES));

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
      + "This validator checks residue/v0.3, which renamed every key and enum "
      + "to English. See the ES-EN glossary in the repository README to migrate.",
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

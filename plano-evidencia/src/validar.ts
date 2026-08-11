/**
 * Port TypeScript del validador del artefacto de residuo (esquema v0.1).
 *
 * Espejo de src/residuo/reglas.py (implementacion de referencia en Python).
 * La paridad no se asegura leyendo el codigo: se asegura corriendo los
 * vectores de conformidad de spec/vectores. Mismo veredicto y mismas
 * etiquetas de regla por vector, o el port esta roto.
 *
 * Nota de paridad con la referencia: los "format" (uuid, date-time) no se
 * validan, igual que jsonschema en Python sin format checker.
 */
import Ajv2020 from "ajv/dist/2020.js";
import type { ValidateFunction } from "ajv";

export const MARCADORES_GENERICOS = new Set([
  "n/a", "na", "ninguno", "ninguna", "todo resuelto", "aplicado",
  "ok", "sin residuo", "-", "no aplica",
]);

const ESTADOS_A_RESIDUO = new Set([
  "escalado_abierto", "refutado_verificable", "refutado_interpretativo",
]);

const CLASE_ESPERADA: Record<string, string> = {
  escalado_abierto: "escalado_sin_decision",
  refutado_verificable: "refutacion_del_principal",
  refutado_interpretativo: "refutacion_del_principal",
};

const CAMPOS_TEXTO_PROHIBIDOS_MINIMIZADO = ["titulo", "descripcion", "ubicacion"];

type Artefacto = any;

export function compilarSchema(schema: object): ValidateFunction {
  const ajv = new Ajv2020({ strict: false, validateFormats: false, allErrors: true });
  return ajv.compile(schema);
}

export function erroresSchema(a: Artefacto, validar: ValidateFunction): string[] {
  const ok = validar(a);
  if (ok) return [];
  return (validar.errors ?? []).map(
    (e) => `[schema] ${e.instancePath || "(raiz)"}: ${e.message ?? ""}`,
  );
}

export function erroresReglas(a: Artefacto): string[] {
  const e: string[] = [];
  const error = (regla: string, msg: string) => e.push(`[${regla}] ${msg}`);

  const perfil: string = a.perfil;
  const hallazgos: any[] = a.hallazgos ?? [];
  const residuo = a.residuo;
  const items: any[] = residuo.items ?? [];
  const porId = new Map<string, any>(hallazgos.map((h) => [h.id, h]));
  const compuerta: string = a.evento.compuerta;
  const nivel: string = a.evento.nivel_criticidad;

  // R0: sin arbitro humano el evento no cumple el protocolo (seccion 6).
  if (!a.actores.arbitro_humano.presente) {
    error("R0", "evento sin arbitro humano presente");
  }

  // R10: en perfil completo, la lista de hallazgos es obligatoria.
  if (perfil === "completo" && hallazgos.length === 0) {
    error("R10", "perfil completo sin lista de hallazgos");
  }

  // R1: coherencia entre estados que integran el residuo y sus items.
  if (hallazgos.length > 0) {
    const refs = new Set(items.map((i) => i.ref_hallazgo).filter(Boolean));
    for (const h of hallazgos) {
      if (ESTADOS_A_RESIDUO.has(h.estado_final) && !refs.has(h.id)) {
        error("R1", `hallazgo ${h.id} (${h.estado_final}) sin item de residuo`);
      }
    }
    for (const i of items) {
      const ref = i.ref_hallazgo;
      if (ref) {
        if (!porId.has(ref)) {
          error("R1", `item ${i.id} referencia hallazgo inexistente ${ref}`);
        } else {
          const est = porId.get(ref).estado_final;
          if (est in CLASE_ESPERADA && i.clase !== CLASE_ESPERADA[est]) {
            error("R1", `item ${i.id} clase ${i.clase} no corresponde al estado ${est} de ${ref}`);
          }
        }
      }
    }
  }

  // R2: sin marcadores genericos en las declaraciones de texto.
  const textos: Array<[string, string]> = [];
  if (residuo.ausencia_declarada) {
    textos.push(["residuo.declaracion", residuo.declaracion ?? ""]);
  }
  for (const i of items) {
    if (typeof i.descripcion === "string") {
      textos.push([`residuo.items[${i.id}].descripcion`, i.descripcion]);
    }
  }
  for (const [donde, t] of textos) {
    if (MARCADORES_GENERICOS.has(t.trim().toLowerCase())) {
      error("R2", `marcador generico en ${donde}: '${t}'`);
    }
  }

  // R2 bis: marcadores de plantilla sin completar, en cualquier campo.
  const buscarPlantilla = (valor: unknown, ruta: string): void => {
    if (typeof valor === "string" && valor.startsWith("COMPLETAR")) {
      error("R2", `marcador de plantilla sin completar en ${ruta}`);
    } else if (Array.isArray(valor)) {
      valor.forEach((v, n) => buscarPlantilla(v, `${ruta}[${n}]`));
    } else if (valor !== null && typeof valor === "object") {
      for (const [k, v] of Object.entries(valor)) buscarPlantilla(v, `${ruta}.${k}`);
    }
  };
  buscarPlantilla(a, "artefacto");

  // R3: ruta abreviada incompatible con los cinco casos protegidos (3.2).
  const ra = a.evento.ruta_abreviada;
  if (ra.usada && (ra.casos_protegidos_tocados ?? []).length > 0) {
    error("R3", "ruta abreviada usada sobre un cambio que toca casos protegidos de 3.2");
  }

  // R4: decorrelacion entre generador y revisores.
  const famGen: string = a.actores.generador.familia;
  for (const r of a.actores.revisores) {
    if (r.familia === famGen) {
      error("R4", `revisor ${r.id_revisor} comparte familia (${famGen}) con el generador: sin decorrelacion`);
    }
  }

  // R5: Nivel A + gap de ejecucion exige aceptacion escrita (seccion 7).
  if (nivel === "A") {
    for (const i of items) {
      if (i.clase === "gap_de_ejecucion" && !("aceptacion_referente" in i)) {
        error("R5", `item ${i.id}: gap de ejecucion en Nivel A sin aceptacion de referente (bloquea el merge)`);
      }
    }
  }

  // R6: conteos coherentes con la lista de hallazgos.
  if (hallazgos.length > 0) {
    const c = a.metricas.conteos;
    const conteo = (est: string) => hallazgos.filter((h) => h.estado_final === est).length;
    const esperado: Array<[string, string, number]> = [
      ["validos", "incorporado", conteo("incorporado")],
      ["validos", "deuda_registrada", conteo("deuda_registrada")],
      ["validos", "decision_del_dueno", conteo("decision_del_dueno")],
      ["falsos_positivos", "refutado_verificable", conteo("refutado_verificable")],
      ["falsos_positivos", "refutado_interpretativo", conteo("refutado_interpretativo")],
    ];
    for (const [grupo, campo, v] of esperado) {
      if (c[grupo][campo] !== v) {
        error("R6", `conteo ${grupo}.${campo}=${c[grupo][campo]} pero la lista tiene ${v}`);
      }
    }
    if (c.escalados_abiertos !== conteo("escalado_abierto")) {
      error("R6", `escalados_abiertos=${c.escalados_abiertos} pero la lista tiene ${conteo("escalado_abierto")}`);
    }
    if (c.total_hallazgos !== hallazgos.length) {
      error("R6", `total_hallazgos=${c.total_hallazgos} pero la lista tiene ${hallazgos.length}`);
    }
  }

  // R7: en compuerta diff, todo incorporado cierra con la correccion verificada.
  if (compuerta === "diff") {
    for (const h of hallazgos) {
      if (h.estado_final === "incorporado") {
        const v = h.verificacion_de_la_correccion;
        if (!v) {
          error("R7", `hallazgo ${h.id} incorporado en compuerta diff sin verificacion de la correccion`);
        } else if (v.tipo === "pendiente_en_compuerta_diff") {
          error("R7", `hallazgo ${h.id}: la verificacion de la correccion no puede quedar pendiente en la propia compuerta diff`);
        }
      }
    }
  }

  // R8: refutacion interpretativa siempre pide atencion humana.
  for (const i of items) {
    if (i.tipo_refutacion === "interpretativa" && !i.requiere_atencion_humana) {
      error("R8", `item ${i.id}: refutacion interpretativa con requiere_atencion_humana=false`);
    }
  }

  // R9: perfil minimizado no admite texto libre.
  if (perfil === "minimizado") {
    for (const h of hallazgos) {
      for (const campo of CAMPOS_TEXTO_PROHIBIDOS_MINIMIZADO) {
        if (campo in h) error("R9", `hallazgo ${h.id}: campo '${campo}' prohibido en perfil minimizado`);
      }
      const ev = h.evidencia ?? {};
      if ("texto" in ev || "enlace" in ev) {
        error("R9", `hallazgo ${h.id}: evidencia con texto o enlace en perfil minimizado (solo hash)`);
      }
    }
    for (const i of items) {
      if ("descripcion" in i) error("R9", `item ${i.id}: descripcion prohibida en perfil minimizado`);
      const ev = i.evidencia ?? {};
      if ("texto" in ev || "enlace" in ev) {
        error("R9", `item ${i.id}: evidencia con texto o enlace en perfil minimizado (solo hash)`);
      }
    }
    if (String(a.evento.repositorio).startsWith("http")) {
      error("R9", "perfil minimizado con URL de repositorio en claro (usar hash o identificador opaco)");
    }
  }

  return e;
}

/**
 * Valida un artefacto completo. Si el schema falla, las reglas no se evaluan
 * (misma semantica que la referencia): operarian sobre una forma no garantizada.
 */
export function validarArtefacto(a: Artefacto, validar: ValidateFunction): string[] {
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

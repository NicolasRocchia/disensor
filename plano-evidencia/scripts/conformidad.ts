/**
 * Conformance runner: the TypeScript port against the vectors of spec/vectors.
 * Same verdict and same labels per vector, or the port is broken. Exit 1 on divergence.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  compilarSchema, validarArtefacto, etiquetas, versionOf, SCHEMA_FILES,
  appliesFrom, versionKeyOf, erroresSchema, erroresReglas,
} from "../src/validar.js";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const vectorsDir = join(root, "spec", "vectors");

// Uno por version, elegido por lo que el artefacto declara. `residue.schema.json`
// es la version corriente y cambia en cada release: aplicarselo a un vector de
// otra version lo juzga con reglas que no son las suyas.
const validadores = new Map(
  Object.entries(SCHEMA_FILES).map(([version, archivo]) => [
    version,
    compilarSchema(JSON.parse(readFileSync(join(root, "spec", archivo), "utf-8"))),
  ]),
);
const desconocida = compilarSchema(
  JSON.parse(readFileSync(join(root, "spec", "residue.schema.json"), "utf-8")),
);
let run = 0;
let divergences = 0;
const noImplementadas = new Map<string, number>();
const porVersion = new Map<string, number>();
// Cuantos vectores MUST-FAIL nombran cada etiqueta, y los MUST-PASS de cada
// suite, que son las bases sobre las que se prueban las exenciones mas abajo.
const porRegla = new Map<string, number>();
const mustPassPorSuite = new Map<string, { name: string; artifact: any }[]>();

// Una suite por version: se recorren todas. Las de versiones que este port no
// implementa se cuentan aparte y se declaran al final, porque saltearlas en
// silencio dejaria el mensaje diciendo conformidad sobre un contrato que ni
// siquiera miro.
const suites = readdirSync(vectorsDir, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .map((d) => d.name)
  .sort();

for (const suite of suites) {
  const dir = join(vectorsDir, suite);
  for (const name of readdirSync(dir).sort()) {
    if (!name.endsWith(".json") || name === "index.json") continue;
    const vector = JSON.parse(readFileSync(join(dir, name), "utf-8"));
    // El censo por regla y las bases se toman del corpus entero, antes del
    // despacho por version: son propiedades de spec/vectors, no de lo que este
    // port sepa juzgar.
    if (vector.expected.valid) {
      const lista = mustPassPorSuite.get(suite) ?? [];
      lista.push({ name: vector.name, artifact: vector.artifact });
      mustPassPorSuite.set(suite, lista);
    } else {
      for (const etiqueta of new Set<string>(vector.expected.rules)) {
        porRegla.set(etiqueta, (porRegla.get(etiqueta) ?? 0) + 1);
      }
    }
    const version = versionOf(vector.artifact);
    if (version !== null && !validadores.has(version)) {
      noImplementadas.set(version, (noImplementadas.get(version) ?? 0) + 1);
      continue;
    }
    const validar = (version !== null && validadores.get(version)) || desconocida;
    if (version !== null) porVersion.set(version, (porVersion.get(version) ?? 0) + 1);
    const errores = validarArtefacto(vector.artifact, validar);
    const valid = errores.length === 0;
    const tags = etiquetas(errores);
    const expected = vector.expected;
    const ok = valid === expected.valid && JSON.stringify(tags) === JSON.stringify(expected.rules);
    run += 1;
    if (!ok) {
      divergences += 1;
      console.log(`DIVERGES ${vector.name}`);
      console.log(`  expected: valid=${expected.valid} rules=${JSON.stringify(expected.rules)}`);
      console.log(`  obtained: valid=${valid} rules=${JSON.stringify(tags)}`);
      for (const e of errores.slice(0, 6)) console.log(`    ${e}`);
    } else {
      console.log(`OK ${vector.name}`);
    }
  }
}

// Cobertura, no solo ausencia de divergencia: cada version conocida tiene que
// tener su suite, y esa suite tiene que contener vectores que declaren esa
// version. Contar lo no implementado solo caza el caso en que la suite existe;
// abrir una version y no crear sus vectores dejaba el contador vacio y el
// runner en verde, declarando conformidad sobre un contrato que nadie ejercito.
const faltantes: string[] = [];
for (const version of Object.keys(SCHEMA_FILES)) {
  const juzgados = porVersion.get(version) ?? 0;
  if (juzgados === 0) faltantes.push(version);
}

// Y el vector compartido de la forma del identificador y de la ordinalidad, que
// es donde las dos implementaciones se habian separado sin que nada lo dijera.
// Dos contadores, porque son dos clases de caso: llamar "ordinality" al total
// le mostraba a un lector externo una clasificacion distinta de la del archivo,
// que separa la forma del identificador de la ordinalidad de las reglas.
let casosForma = 0;
let casosOrdinalidad = 0;
const casos = JSON.parse(readFileSync(join(root, "spec", "version_ordinality.json"), "utf-8"));
for (const c of casos.form) {
  let acepta = true;
  try { versionKeyOf(c.id); } catch { acepta = false; }
  if (acepta !== c.valid) {
    console.log(`DIVERGE form ${JSON.stringify(c.id)}: obtained valid=${acepta}, expected ${c.valid}`);
    divergences++;
  }
  casosForma++;
}
for (const c of casos.ordinality) {
  let obtenido: boolean | "raises";
  try { obtenido = appliesFrom(c.declared, c.introduced); } catch { obtenido = "raises"; }
  const esperado = c.raises ? "raises" : c.applies;
  if (obtenido !== esperado) {
    console.log(`DIVERGE ordinality ${c.declared} from ${c.introduced}: obtained ${obtenido}, expected ${esperado}`);
    divergences++;
  }
  casosOrdinalidad++;
}

// Cobertura por regla, no solo por version: para cada regla que este port puede
// emitir, cuantos vectores MUST-FAIL la nombran. Una regla en cero es una regla
// que un verificador puede no implementar sin que ningun vector lo note, porque
// la comparacion exacta de etiquetas no tiene nada que comparar. Las que no
// pueden tener vector figuran en spec/rule_coverage.json, y la exencion no se
// toma por declarada: se prueba abajo, con codigo de este port y no del de la
// implementacion de referencia. El registro sale de la fuente de este port a
// proposito; leerlo de un archivo compartido dejaria que el port se saltee una
// regla y pase igual.
const cobertura = JSON.parse(readFileSync(join(root, "spec", "rule_coverage.json"), "utf-8"));
const exentas: any[] = cobertura.exempt;
const fuente = readFileSync(join(here, "..", "src", "validar.ts"), "utf-8");
const registro = [...new Set([...fuente.matchAll(/"(R\d+)"/g)].map((m) => m[1]))]
  .sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));

const sinCobertura = registro.filter(
  (r) => (porRegla.get(r) ?? 0) === 0 && !exentas.some((e) => e.rule === r));
const exencionesVencidas = exentas
  .filter((e) => (porRegla.get(e.rule) ?? 0) > 0).map((e) => e.rule);
const exencionesFantasma = exentas
  .filter((e) => !registro.includes(e.rule)).map((e) => e.rule);

// La ruta de la instancia, sin la barra inicial: este port informa un JSON
// Pointer y la referencia una ruta unida por barras, y el dato compartido dice
// una sola cosa.
const rutaDe = (error: string): string => {
  const resto = error.slice(error.indexOf("]") + 1);
  return resto.slice(0, resto.indexOf(":")).trim().replace(/^\//, "");
};
// Una misma violacion puede salir como mas de un error cuando el validador
// tambien informa el condicional que la envuelve. Eso es la misma violacion
// subiendo, no ruido: el ruido cae en otra rama del artefacto.
const dentro = (ruta: string, objetivo: string): boolean =>
  objetivo === ruta || objetivo.startsWith(ruta + "/");
const cumple = (a: any, necesita: any): boolean => {
  for (const clave of Object.keys(necesita ?? {})) {
    if (clave !== "residue_item_class") {
      throw new Error(`spec/rule_coverage.json pide ${clave} y este runner no sabe que es`);
    }
  }
  const clase = (necesita ?? {}).residue_item_class;
  if (clase === undefined) return true;
  return ((a.residue ?? {}).items ?? []).some((i: any) => i.class === clase);
};

const escenarios: Record<string, (a: any) => any> = {
  R3(a: any) {
    a.event.abbreviated_path = {
      used: true,
      justification: "cambio trivial de una linea en un helper",
      protected_cases_touched: ["data_migration"],
    };
    return a;
  },
  R8(a: any) {
    for (const item of a.residue.items) {
      if (item.class === "principal_refutation") {
        item.refutation_type = "interpretive";
        item.requires_human_attention = false;
        return a;
      }
    }
    throw new Error("la base no tiene el item que el escenario necesita");
  },
};

// La exencion se prueba en las dos direcciones y en cada version: sobre una
// base MUST-PASS de la propia suite, que valida limpia contra su propio
// esquema, el escenario tiene que ser rechazado en el campo que la exencion
// nombra y en ningun otro lado, y la regla tiene que disparar igual cuando se
// saltea la capa de esquema.
const exencionesSinProbar: string[] = [];
for (const exenta of exentas) {
  const escenario = escenarios[exenta.rule];
  if (escenario === undefined) {
    exencionesSinProbar.push(`${exenta.rule}: este port no tiene escenario para probarla`);
    continue;
  }
  for (const version of Object.keys(SCHEMA_FILES)) {
    const suite = version.split("/")[1];
    const validar = validadores.get(version);
    if (validar === undefined) continue;
    const candidatos = (mustPassPorSuite.get(suite) ?? [])
      .filter((v) => cumple(v.artifact, exenta.base_needs));
    if (candidatos.length === 0) {
      exencionesSinProbar.push(`${exenta.rule} in ${version}: no MUST-PASS vector of the suite `
        + `satisfies ${JSON.stringify(exenta.base_needs)}`);
      continue;
    }
    const base = candidatos[0];
    if (erroresSchema(base.artifact, validar).length > 0) {
      exencionesSinProbar.push(`${exenta.rule} in ${version}: base ${base.name} does not `
        + "validate clean against its own schema");
      continue;
    }
    const mutado = escenario(JSON.parse(JSON.stringify(base.artifact)));
    const rutas = erroresSchema(mutado, validar).map(rutaDe);
    const patron = new RegExp(exenta.schema_path);
    const objetivo = rutas.filter((r) => patron.test(r));
    if (objetivo.length === 0) {
      exencionesSinProbar.push(`${exenta.rule} in ${version}: the scenario on ${base.name} is `
        + `not rejected at ${exenta.schema_path}; paths ${JSON.stringify(rutas)}`);
      continue;
    }
    const ajenas = rutas.filter((r) => !objetivo.some((o) => dentro(r, o)));
    if (ajenas.length > 0) {
      exencionesSinProbar.push(`${exenta.rule} in ${version}: the scenario on ${base.name} is `
        + `also rejected at ${JSON.stringify(ajenas)}, outside ${exenta.schema_path}`);
      continue;
    }
    if (!erroresReglas(mutado).some((e) => e.startsWith(`[${exenta.rule}]`))) {
      exencionesSinProbar.push(`${exenta.rule} in ${version}: with the schema layer skipped the `
        + "rule does not fire on its own scenario");
    }
  }
}

console.log(`---`);
for (const [version, cuantos] of [...noImplementadas].sort()) {
  console.log(`NOT IMPLEMENTED: ${cuantos} vectors of ${version} were not judged by this port`);
}
for (const version of faltantes) {
  console.log(`NO COVERAGE: ${version} is a known version with no vectors declaring it`);
}
for (const regla of sinCobertura) {
  console.log(`NO COVERAGE: rule ${regla} is named by no MUST-FAIL vector and is not exempt `
    + "in spec/rule_coverage.json");
}
for (const regla of exencionesVencidas) {
  console.log(`STALE EXEMPTION: rule ${regla} is exempt in spec/rule_coverage.json and already `
    + "has a MUST-FAIL vector naming it");
}
for (const regla of exencionesFantasma) {
  console.log(`UNKNOWN EXEMPTION: spec/rule_coverage.json exempts ${regla}, which this port `
    + "does not emit");
}
for (const linea of exencionesSinProbar) {
  console.log(`EXEMPTION NOT PROVED: ${linea}`);
}
const censoRoto = sinCobertura.length + exencionesVencidas.length
  + exencionesFantasma.length + exencionesSinProbar.length;
const casosCompartidos = casosForma + casosOrdinalidad;
console.log(divergences === 0 && censoRoto === 0
  ? `CONFORMANT: ${run} vectors and ${casosCompartidos} shared cases `
    + `(${casosForma} identifier-form, ${casosOrdinalidad} ordinality), `
    + `${registro.length} rules covered (${exentas.length} by proved exemption), zero divergences`
  : `NOT CONFORMANT: ${divergences} divergences over ${run} vectors and ${casosCompartidos} shared cases`);
// Una suite que este port no sabe juzgar, o una version conocida sin vectores,
// son fallas y no notas al pie: sin esto CI queda en verde mientras el claim de
// dos implementaciones vuelve a cubrir una version que ya no es la vigente, que
// es exactamente el agujero que este trabajo vino a cerrar.
process.exit(divergences === 0 && noImplementadas.size === 0 && faltantes.length === 0
  && censoRoto === 0 ? 0 : 1);

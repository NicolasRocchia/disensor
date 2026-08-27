/**
 * Conformance runner: the TypeScript port against the vectors of spec/vectors.
 * Same verdict and same labels per vector, or the port is broken. Exit 1 on divergence.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { compilarSchema, validarArtefacto, etiquetas, versionOf, SCHEMA_FILES } from "../src/validar.js";

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

for (const name of readdirSync(vectorsDir).sort()) {
  if (!name.endsWith(".json") || name === "index.json") continue;
  const vector = JSON.parse(readFileSync(join(vectorsDir, name), "utf-8"));
  const version = versionOf(vector.artifact);
  const validar = (version !== null && validadores.get(version)) || desconocida;
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

console.log(`---`);
console.log(divergences === 0
  ? `CONFORMANT: ${run} vectors, zero divergences`
  : `NOT CONFORMANT: ${divergences} of ${run} vectors diverge`);
process.exit(divergences === 0 ? 0 : 1);

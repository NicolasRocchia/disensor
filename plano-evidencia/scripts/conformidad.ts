/**
 * Corredor de conformidad: el port TypeScript contra los vectores de spec/vectores.
 * Mismo veredicto y mismas etiquetas por vector, o el port esta roto. Exit 1 si diverge.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { compilarSchema, validarArtefacto, etiquetas } from "../src/validar.js";

const aqui = dirname(fileURLToPath(import.meta.url));
const raiz = join(aqui, "..", "..");
const schema = JSON.parse(readFileSync(join(raiz, "spec", "residuo.schema.json"), "utf-8"));
const dirVectores = join(raiz, "spec", "vectores");

const validar = compilarSchema(schema);
let corridos = 0;
let divergencias = 0;

for (const nombre of readdirSync(dirVectores).sort()) {
  if (!nombre.endsWith(".json") || nombre === "INDICE.json") continue;
  const vector = JSON.parse(readFileSync(join(dirVectores, nombre), "utf-8"));
  const errores = validarArtefacto(vector.artefacto, validar);
  const valido = errores.length === 0;
  const tags = etiquetas(errores);
  const esperado = vector.esperado;
  const ok = valido === esperado.valido && JSON.stringify(tags) === JSON.stringify(esperado.reglas);
  corridos += 1;
  if (!ok) {
    divergencias += 1;
    console.log(`DIVERGE ${vector.nombre}`);
    console.log(`  esperado: valido=${esperado.valido} reglas=${JSON.stringify(esperado.reglas)}`);
    console.log(`  obtenido: valido=${valido} reglas=${JSON.stringify(tags)}`);
    for (const e of errores.slice(0, 6)) console.log(`    ${e}`);
  } else {
    console.log(`OK ${vector.nombre}`);
  }
}

console.log(`---`);
console.log(divergencias === 0
  ? `CONFORME: ${corridos} vectores, cero divergencias`
  : `NO CONFORME: ${divergencias} de ${corridos} vectores divergen`);
process.exit(divergencias === 0 ? 0 : 1);

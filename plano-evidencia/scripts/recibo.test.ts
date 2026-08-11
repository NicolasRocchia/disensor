/**
 * Verificacion cruzada del recibo: la firma HMAC del Worker contra un valor
 * esperado calculado con una implementacion independiente (Python hmac).
 * Dos implementaciones, un resultado, o algo esta mal.
 */
import { sha256Hex, firmarRecibo } from "../src/index.js";

const cuerpo = new TextEncoder().encode('{"prueba":"recibo"}');
const hash = await sha256Hex(cuerpo);
const firma = await firmarRecibo("secreto-de-prueba", hash, "2026-08-11T00:00:00.000Z");

// Valores esperados calculados con Python (hashlib y hmac), ver comando en el README.
const HASH_ESPERADO = "676bebec0f8912b1e397e64df1afe8d24e38d1c98ae9255fc4b4c06f722229ae";
const FIRMA_ESPERADA = "9fde3563921a87da8fb7ec2d40d7b8438d84f26b593671eb3542b43115c46f5e";

if (hash !== HASH_ESPERADO) {
  console.log(`DIVERGE hash: ${hash} vs ${HASH_ESPERADO}`);
  process.exit(1);
}
if (firma !== FIRMA_ESPERADA) {
  console.log(`DIVERGE firma: ${firma} vs ${FIRMA_ESPERADA}`);
  process.exit(1);
}
console.log("recibo CONFORME: hash y firma coinciden con la implementacion independiente");

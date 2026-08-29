/**
 * Plano de evidencia: Worker de ingesta (v0, Fase 2).
 *
 * POST /v1/artefactos: recibe un artefacto de residuo, lo valida con el mismo
 * nucleo que el gate (conformidad garantizada por spec/vectores), lo guarda en
 * D1 y devuelve un recibo de integridad: hash del cuerpo recibido, timestamp
 * del servidor y firma HMAC. El recibo es lo que un digestor casero no puede
 * tener: un tercero independiente atestiguando que el artefacto existio con
 * ese contenido en ese momento.
 *
 * Lo que este archivo NO hace, a proposito: no corre modelos, no ve codigo,
 * no acepta texto fuera del artefacto. Perfil minimizado bienvenido.
 */
import schemaV02 from "../../spec/residue.schema.v0.2.json";
import schemaV03 from "../../spec/residue.schema.v0.3.json";
import schemaV04 from "../../spec/residue.schema.v0.4.json";
import { compilarSchema, validarArtefacto, versionOf } from "./validar.js";

export interface Env {
  DB: D1Database;
  HMAC_SECRET: string;
}

// Un validador por version conocida: un artefacto se juzga con el schema de la
// version que declara. Compilando solo la vigente, una declaracion de una
// version superada fallaba por forma, con los errores de un contrato que no es
// el suyo, y nunca llegaba a la unica explicacion util. El Worker no tiene
// filesystem, asi que los recursos se importan uno por uno; que este mapa
// coincida con el del validador lo verifica una prueba, no la buena memoria.
export const VALIDADORES = new Map<string, ReturnType<typeof compilarSchema>>(Object.entries({
  "residue/v0.2": compilarSchema(schemaV02 as object),
  "residue/v0.3": compilarSchema(schemaV03 as object),
  "residue/v0.4": compilarSchema(schemaV04 as object),
}));

// Espejo de CURRENT_SCHEMA en src/disensor/gate.py (G9). El esquema compartido
// sigue leyendo versiones superadas para que la historia no se reescriba, pero
// cada POST es una emision presente: el recibo atesta que el artefacto existe
// ahora, asi que lo que entra declara la version vigente.
const ESQUEMA_VIGENTE = "residue/v0.4";

const enc = new TextEncoder();

export function aHex(buf: ArrayBuffer): string {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(datos: Uint8Array): Promise<string> {
  return aHex(await crypto.subtle.digest("SHA-256", datos as unknown as ArrayBuffer));
}

export async function firmarRecibo(secreto: string, hash: string, recibidoEn: string): Promise<string> {
  const clave = await crypto.subtle.importKey(
    "raw", enc.encode(secreto), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const firma = await crypto.subtle.sign("HMAC", clave, enc.encode(`${hash}.${recibidoEn}`));
  return aHex(firma);
}

function json(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function organizacionDelToken(env: Env, req: Request): Promise<string | null> {
  const auth = req.headers.get("authorization") ?? "";
  if (!auth.toLowerCase().startsWith("bearer ")) return null;
  const token = auth.slice(7).trim();
  if (!token) return null;
  const hashToken = await sha256Hex(enc.encode(token));
  const fila = await env.DB
    .prepare("SELECT org_id FROM tokens WHERE hash_token = ? AND revocado_en IS NULL")
    .bind(hashToken)
    .first<{ org_id: string }>();
  return fila?.org_id ?? null;
}

type Recibo = { hash: string; recibido_en: string; firma: string };

async function reciboDe(env: Env, orgId: string, idEvento: string): Promise<Recibo | null> {
  return await env.DB
    .prepare("SELECT hash, recibido_en, firma FROM recibos WHERE org_id = ? AND id_evento = ?")
    .bind(orgId, idEvento)
    .first<Recibo>();
}

/** Lo que un evento ya declarado responde: su recibo, o el conflicto. */
function respuestaDelRecibo(existente: Recibo, hash: string): Response {
  if (existente.hash === hash) return json({ recibo: existente, repetido: true }, 200);
  return json({
    error: "el evento ya fue declarado con otro contenido; los recibos no se reemplazan",
    recibo_original: existente,
  }, 409);
}

async function ingestar(env: Env, req: Request): Promise<Response> {
  const orgId = await organizacionDelToken(env, req);
  if (!orgId) return json({ error: "token invalido o revocado" }, 401);

  const crudo = new Uint8Array(await req.arrayBuffer());
  if (crudo.length === 0) return json({ error: "cuerpo vacio" }, 400);
  if (crudo.length > 1_000_000) return json({ error: "artefacto demasiado grande" }, 413);

  let artefacto: any;
  try {
    artefacto = JSON.parse(new TextDecoder().decode(crudo));
  } catch {
    return json({ error: "JSON invalido" }, 400);
  }

  const declarada = versionOf(artefacto);
  // Un Map y no un objeto: en JavaScript `VALIDADORES["toString"]` devuelve
  // una funcion heredada del prototipo, y el discriminador viene de afuera.
  const validar = VALIDADORES.get(declarada ?? ESQUEMA_VIGENTE)
    ?? VALIDADORES.get(ESQUEMA_VIGENTE)!;
  const errores = validarArtefacto(artefacto, validar);
  if (errores.length > 0) return json({ error: "artefacto invalido", errores }, 422);

  const hash = await sha256Hex(crudo);
  const idEvento: string = artefacto.event.event_id;

  // Idempotencia: el mismo evento con el mismo contenido devuelve el recibo
  // original; el mismo evento con otro contenido es un conflicto, nunca un
  // reemplazo silencioso. Los recibos son de solo agregado.
  const yaDeclarado = await reciboDe(env, orgId, idEvento);
  if (yaDeclarado) return respuestaDelRecibo(yaDeclarado, hash);

  // Recien aca la politica de emision. Va despues de la busqueda del recibo a
  // proposito: un evento ya declarado devuelve lo que ya se le atesto, aunque
  // su version haya sido superada desde entonces. Rechazar un reenvio no
  // protege nada y rompe el reintento de cualquier cliente al que se le corto
  // la red, en cada bump de version.
  if (artefacto.schema !== ESQUEMA_VIGENTE) {
    return json({
      error: `el artefacto declara '${artefacto.schema}' y la version vigente es `
        + `${ESQUEMA_VIGENTE}; las versiones superadas se leen, no se emiten`,
    }, 422);
  }

  const recibidoEn = new Date().toISOString();
  const firma = await firmarRecibo(env.HMAC_SECRET, hash, recibidoEn);
  const ev = artefacto.event;

  try {
    await env.DB.batch([
      env.DB.prepare(
        `INSERT INTO artefactos (org_id, id_evento, hash, esquema, perfil, nivel, compuerta, recibido_en, cuerpo)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).bind(orgId, idEvento, hash, artefacto.schema, artefacto.profile,
             ev.criticality_level, ev.gate, recibidoEn, new TextDecoder().decode(crudo)),
      env.DB.prepare(
        `INSERT INTO recibos (org_id, id_evento, hash, recibido_en, firma) VALUES (?, ?, ?, ?, ?)`,
      ).bind(orgId, idEvento, hash, recibidoEn, firma),
    ]);
  } catch (e) {
    // Dos POST simultaneos del mismo evento pueden ver los dos que no hay
    // recibo: uno inserta y el otro choca con la clave primaria. Eso no es un
    // error interno, es la respuesta que la busqueda habria dado un instante
    // despues, y devolver 500 hace que la idempotencia dependa de que nadie
    // reintente rapido. Si el recibo aparecio, gana el que lo escribio.
    const carrera = await reciboDe(env, orgId, idEvento);
    if (carrera) return respuestaDelRecibo(carrera, hash);
    throw e;
  }

  return json({ recibo: { hash, recibido_en: recibidoEn, firma } }, 201);
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/v1/salud") {
      return json({ ok: true, schema: ESQUEMA_VIGENTE });
    }
    if (req.method === "POST" && url.pathname === "/v1/artefactos") {
      try {
        return await ingestar(env, req);
      } catch (e) {
        return json({ error: "error interno" }, 500);
      }
    }
    return json({ error: "ruta desconocida" }, 404);
  },
};

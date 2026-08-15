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
import schema from "../../spec/residue.schema.json";
import { compilarSchema, validarArtefacto } from "./validar.js";

export interface Env {
  DB: D1Database;
  HMAC_SECRET: string;
}

const validar = compilarSchema(schema as object);

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

  const errores = validarArtefacto(artefacto, validar);
  if (errores.length > 0) return json({ error: "artefacto invalido", errores }, 422);

  const hash = await sha256Hex(crudo);
  const idEvento: string = artefacto.event.event_id;

  // Idempotencia: el mismo evento con el mismo contenido devuelve el recibo
  // original; el mismo evento con otro contenido es un conflicto, nunca un
  // reemplazo silencioso. Los recibos son de solo agregado.
  const existente = await env.DB
    .prepare("SELECT hash, recibido_en, firma FROM recibos WHERE org_id = ? AND id_evento = ?")
    .bind(orgId, idEvento)
    .first<{ hash: string; recibido_en: string; firma: string }>();
  if (existente) {
    if (existente.hash === hash) {
      return json({ recibo: existente, repetido: true }, 200);
    }
    return json({
      error: "el evento ya fue declarado con otro contenido; los recibos no se reemplazan",
      recibo_original: existente,
    }, 409);
  }

  const recibidoEn = new Date().toISOString();
  const firma = await firmarRecibo(env.HMAC_SECRET, hash, recibidoEn);
  const ev = artefacto.event;

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

  return json({ recibo: { hash, recibido_en: recibidoEn, firma } }, 201);
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (req.method === "GET" && url.pathname === "/v1/salud") {
      return json({ ok: true, schema: "residue/v0.3" });
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

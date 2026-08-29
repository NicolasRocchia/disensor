/**
 * La ingesta contra un D1 de mentira: lo que decide, y en que orden.
 *
 * El recibo de un artefacto ya aceptado tiene que sobrevivir al cambio de
 * version vigente. La ingesta rechazaba por version antes de buscar el recibo,
 * asi que un reenvio de algo ya atestado devolvia un rechazo, y una declaracion
 * de una version superada fallaba por forma contra el schema de otro contrato
 * en vez de recibir la unica explicacion util. Las dos cosas se repiten en cada
 * bump de version, asi que se prueban.
 *
 * El entorno de Workers trae fetch, Request y Response; el Node de este repo es
 * viejo y no. Se les pone el minimo que el Worker toca, sin sumar una
 * dependencia por un test, y sin pisar nada si el runtime ya los tiene.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { webcrypto } from "node:crypto";

const g = globalThis as any;
if (!g.crypto?.subtle) g.crypto = webcrypto;
if (!g.Headers) {
  g.Headers = class {
    private m = new Map<string, string>();
    constructor(init: Record<string, string> = {}) {
      for (const [k, v] of Object.entries(init)) this.m.set(k.toLowerCase(), v);
    }
    get(k: string) { return this.m.get(k.toLowerCase()) ?? null; }
  };
}
if (!g.Request) {
  g.Request = class {
    url: string; method: string; headers: any; private cuerpo: string;
    constructor(url: string, init: any = {}) {
      this.url = url;
      this.method = init.method ?? "GET";
      this.headers = new g.Headers(init.headers ?? {});
      this.cuerpo = init.body ?? "";
    }
    async arrayBuffer() { return new TextEncoder().encode(this.cuerpo).buffer; }
  };
}
if (!g.Response) {
  g.Response = class {
    status: number; private cuerpo: string;
    constructor(cuerpo: string, init: any = {}) {
      this.cuerpo = cuerpo;
      this.status = init.status ?? 200;
    }
    async json() { return JSON.parse(this.cuerpo); }
  };
}

const { default: worker, sha256Hex, firmarRecibo } = await import("../src/index.js");

const raiz = join(process.cwd(), "..");
const ORG = "org-de-prueba";
const SECRETO = "secreto-de-prueba";

type Recibo = { hash: string; recibido_en: string; firma: string };

/** Un D1 que responde lo justo: la tabla de tokens y la de recibos. */
function entorno(recibo: Recibo | null = null, idEvento: string | null = null) {
  const escrituras: string[] = [];
  const stmt = (sql: string, args: unknown[] = []): any => ({
    bind: (...a: unknown[]) => stmt(sql, a),
    first: async () => {
      if (sql.includes("FROM tokens")) return { org_id: ORG };
      if (sql.includes("FROM recibos")) return recibo && args[1] === idEvento ? recibo : null;
      return null;
    },
    run: async () => ({ success: true }),
  });
  return {
    escrituras,
    DB: {
      prepare: (sql: string) => stmt(sql),
      batch: async (s: unknown[]) => { escrituras.push(`batch:${s.length}`); return []; },
    } as any,
    HMAC_SECRET: SECRETO,
  };
}

async function post(env: any, cuerpo: string): Promise<{ status: number; body: any }> {
  const req = new g.Request("https://x/v1/artefactos", {
    method: "POST",
    headers: { authorization: "Bearer token-de-prueba", "content-type": "application/json" },
    body: cuerpo,
  });
  const res = await worker.fetch(req, env);
  return { status: res.status, body: await res.json() };
}

function vector(suite: string, nombre: string): string {
  const v = JSON.parse(readFileSync(join(raiz, "spec/vectors", suite, nombre), "utf-8"));
  return JSON.stringify(v.artifact);
}

let fallas = 0;
function ok(cond: boolean, que: string, detalle: unknown = "") {
  if (cond) console.log(`OK ${que}`);
  else { console.log(`FALLA ${que}: ${JSON.stringify(detalle)}`); fallas++; }
}

const superada = vector("v0.3", "valid_diff_gate.json");
const vigente = vector("v0.4", "valid_diff_gate.json");
const idSuperada = JSON.parse(superada).event.event_id;

// 1. Una version superada, nunca vista, se rechaza por lo que es: la emision de
//    un contrato que ya no se emite. No por errores de forma contra el schema
//    de otra version, que era lo unico que el emisor llegaba a ver.
{
  const { status, body } = await post(entorno(), superada);
  ok(status === 422, "una version superada se rechaza", status);
  ok(typeof body.error === "string" && body.error.includes("no se emiten"),
     "y el motivo es la vigencia, no la forma", body);
}

// 2. Reenviar algo ya aceptado devuelve su recibo, aunque su version haya sido
//    superada desde entonces. Es lo que la idempotencia promete, y era lo que
//    se rompia en cada bump.
{
  const hash = await sha256Hex(new TextEncoder().encode(superada));
  const recibidoEn = "2026-08-11T00:00:00.000Z";
  const recibo = { hash, recibido_en: recibidoEn, firma: await firmarRecibo(SECRETO, hash, recibidoEn) };
  const env = entorno(recibo, idSuperada);
  const { status, body } = await post(env, superada);
  ok(status === 200, "un reenvio de lo ya aceptado devuelve su recibo", status);
  ok(body.repetido === true && body.recibo?.hash === hash, "y es el recibo original", body);
  ok(env.escrituras.length === 0, "sin escribir nada nuevo", env.escrituras);
}

// 3. El mismo evento con otro contenido sigue siendo conflicto, no reemplazo.
{
  const env = entorno({ hash: "otro", recibido_en: "2026-08-11T00:00:00.000Z", firma: "x" }, idSuperada);
  const { status } = await post(env, superada);
  ok(status === 409, "el mismo evento con otro contenido es conflicto", status);
}

// 4. La version vigente entra y se escribe una sola vez.
{
  const env = entorno();
  const { status } = await post(env, vigente);
  ok(status === 201, "la version vigente se acepta", status);
  ok(env.escrituras.length === 1, "y se escribe una vez", env.escrituras);
}

console.log("---");
console.log(fallas === 0 ? "INGESTA CONFORME" : `INGESTA: ${fallas} fallas`);
process.exit(fallas === 0 ? 0 : 1);

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
type Sentencia = { sql: string; args: unknown[] };

/**
 * Un D1 que responde lo justo y GUARDA lo que le mandan a escribir.
 *
 * Contar las llamadas a `batch` no prueba nada: reemplazar la escritura entera
 * por `batch([])` pasaba igual. Lo que se guarda es el SQL y sus bindings, para
 * poder afirmar que lo escrito es lo que el recibo dice.
 *
 * `recibosNuevos` sirve para el caso de la carrera: la busqueda no encuentra
 * nada, la escritura choca con la clave primaria, y la segunda busqueda si
 * encuentra, que es lo que pasa cuando dos POST del mismo evento llegan juntos.
 */
function entorno(opciones: {
  recibo?: Recibo | null;
  idEvento?: string | null;
  batchFalla?: boolean;
  reciboTrasLaCarrera?: Recibo | null;
} = {}) {
  const { recibo = null, idEvento = null, batchFalla = false, reciboTrasLaCarrera = null } = opciones;
  const escrito: Sentencia[] = [];
  let busquedas = 0;
  const stmt = (sql: string, args: unknown[] = []): any => ({
    sql,
    args,
    bind: (...a: unknown[]) => stmt(sql, a),
    first: async () => {
      if (sql.includes("FROM tokens")) return { org_id: ORG };
      if (sql.includes("FROM recibos")) {
        busquedas++;
        if (busquedas > 1 && reciboTrasLaCarrera) return reciboTrasLaCarrera;
        return recibo && args[1] === idEvento ? recibo : null;
      }
      return null;
    },
    run: async () => ({ success: true }),
  });
  return {
    escrito,
    DB: {
      prepare: (sql: string) => stmt(sql),
      batch: async (s: Sentencia[]) => {
        if (batchFalla) throw new Error("UNIQUE constraint failed: recibos.id_evento");
        escrito.push(...s);
        return [];
      },
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
  const env = entorno({ recibo, idEvento: idSuperada });
  const { status, body } = await post(env, superada);
  ok(status === 200, "un reenvio de lo ya aceptado devuelve su recibo", status);
  ok(body.repetido === true && body.recibo?.hash === hash, "y es el recibo original", body);
  ok(env.escrito.length === 0, "sin escribir nada nuevo", env.escrito);
}

// 3. El mismo evento con otro contenido sigue siendo conflicto, no reemplazo.
{
  const env = entorno({
    recibo: { hash: "otro", recibido_en: "2026-08-11T00:00:00.000Z", firma: "x" },
    idEvento: idSuperada,
  });
  const { status, body } = await post(env, superada);
  ok(status === 409, "el mismo evento con otro contenido es conflicto", status);
  ok(body.recibo_original?.hash === "otro", "y devuelve el recibo original", body);
  ok(env.escrito.length === 0, "sin escribir nada", env.escrito);
}

// 4. La version vigente entra, y lo que se escribe es lo que el recibo dice.
//    Contar las llamadas no alcanza: `batch([])` pasaba igual.
{
  const env = entorno();
  const { status, body } = await post(env, vigente);
  ok(status === 201, "la version vigente se acepta", status);

  const hash = await sha256Hex(new TextEncoder().encode(vigente));
  const art = JSON.parse(vigente);
  const enArtefactos = env.escrito.find((s) => s.sql.includes("INSERT INTO artefactos"));
  const enRecibos = env.escrito.find((s) => s.sql.includes("INSERT INTO recibos"));
  ok(env.escrito.length === 2 && !!enArtefactos && !!enRecibos,
     "y se escriben el artefacto y su recibo, una vez cada uno", env.escrito.map((s) => s.sql.slice(0, 30)));
  ok(body.recibo?.hash === hash, "el recibo lleva el hash del cuerpo recibido", body);
  ok(await firmarRecibo(SECRETO, hash, body.recibo?.recibido_en) === body.recibo?.firma,
     "y una firma que verifica contra ese hash y esa fecha", body);
  ok(JSON.stringify(enRecibos?.args) === JSON.stringify(
       [ORG, art.event.event_id, hash, body.recibo?.recibido_en, body.recibo?.firma]),
     "la fila del recibo es la que se devolvio, en ese orden", enRecibos?.args);
  ok(JSON.stringify(enArtefactos?.args?.slice(0, 7)) === JSON.stringify(
       [ORG, art.event.event_id, hash, art.schema, art.profile,
        art.event.criticality_level, art.event.gate]),
     "y la del artefacto lleva su version, perfil, nivel y compuerta", enArtefactos?.args?.slice(0, 7));
  ok(enArtefactos?.args?.[8] === vigente, "con el cuerpo tal como llego", typeof enArtefactos?.args?.[8]);
}

// 5. Dos POST simultaneos del mismo evento: los dos ven que no hay recibo, uno
//    inserta y el otro choca con la clave primaria. El que pierde la carrera
//    devuelve el recibo que gano, no un error interno.
{
  const hash = await sha256Hex(new TextEncoder().encode(vigente));
  const recibidoEn = "2026-08-11T00:00:00.000Z";
  const ganador = { hash, recibido_en: recibidoEn, firma: await firmarRecibo(SECRETO, hash, recibidoEn) };
  const env = entorno({ batchFalla: true, reciboTrasLaCarrera: ganador });
  const { status, body } = await post(env, vigente);
  ok(status === 200, "el que pierde la carrera devuelve el recibo del que gano", status);
  ok(body.repetido === true && body.recibo?.hash === hash, "y es el recibo ganador", body);
}

// 6. Si la escritura falla por cualquier otra cosa, sigue siendo un error.
{
  const env = entorno({ batchFalla: true });
  const { status } = await post(env, vigente);
  ok(status === 500, "una escritura que falla sin recibo detras sigue siendo un error", status);
}

console.log("---");
console.log(fallas === 0 ? "INGESTA CONFORME" : `INGESTA: ${fallas} fallas`);
process.exit(fallas === 0 ? 0 : 1);

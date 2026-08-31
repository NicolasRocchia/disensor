# Plano de evidencia (v0, Fase 2)

Worker de ingesta en Cloudflare (Workers mas D1) que recibe artefactos de residuo, los valida con el mismo nucleo de reglas que el gate, y devuelve un recibo de integridad: hash del cuerpo, timestamp del servidor y firma HMAC. Los recibos son de solo agregado, con triggers que lo hacen cumplir en la base: la independencia del custodio es arquitectura, no marketing.

## Estado de verificacion

Verificado en este repo:
- Conformidad del port TypeScript contra las suites de `spec/vectors`, una por versión del esquema: los 89 vectores de v0.2, v0.3 y v0.4, cada uno bajo las reglas de la versión que declara (`npm run conformidad`): mismo veredicto y mismas etiquetas de regla que la implementacion de referencia en Python, por vector. Más los 28 casos de `spec/version_ordinality.json` (19 de forma del identificador y 9 de ordinalidad), que fijan la forma del identificador de versión y qué reglas alcanzan a qué declaración: es donde las dos implementaciones se habían separado sin que nada lo dijera. El runner falla si una versión conocida no tiene vectores que la declaren, porque si no el claim de dos implementaciones se vacía en silencio.
- Verificacion cruzada del recibo (`npx tsx scripts/recibo.test.ts`): hash y firma HMAC coinciden con valores calculados por una implementacion independiente en Python.
- Typecheck estricto (`npm run typecheck`).

No verificado todavia (se estrena con `wrangler dev`): el handler HTTP contra D1 real, el flujo de tokens y el conflicto 409. Es deliberado: el nucleo con riesgo de divergencia esta blindado por vectores; el pegamento HTTP se prueba contra la plataforma real, no contra un mock que mentiria.

## Contrato de la API

- `POST /v1/artefactos` con `Authorization: Bearer <token>` y el artefacto JSON como cuerpo.
  - `201`: `{ "recibo": { "hash", "recibido_en", "firma" } }`
  - `200` con `repetido: true`: mismo evento, mismo contenido (idempotente).
  - `409`: mismo evento, otro contenido. Los recibos no se reemplazan; se devuelve el original.
  - `422`: artefacto invalido, con la lista de errores del validador, que son los del schema de la version que el artefacto declara. Tambien si el artefacto declara una version superada del esquema (espejo del G9 del gate): las versiones viejas se leen, no se emiten. Esa negativa es sobre la EMISION, asi que va despues de la busqueda del recibo: un evento ya declarado devuelve su `200` o su `409` aunque su version haya sido superada desde entonces, porque rechazar un reenvio no protege nada y rompe el reintento de un cliente al que se le corto la red.
  - `401`: token invalido o revocado.
- `GET /v1/salud`.

## Despliegue

```bash
wrangler d1 create disensor-evidencia          # pegar el database_id en wrangler.toml
wrangler d1 execute disensor-evidencia --file=schema.sql
wrangler secret put HMAC_SECRET
wrangler dev                                   # estreno local
wrangler deploy
```

Alta manual de una organizacion (v0, hasta que exista panel):

```sql
INSERT INTO organizaciones (id, nombre, creado_en) VALUES ('org-demo', 'Demo', datetime('now'));
-- token: generar 32 bytes aleatorios; guardar SOLO su sha256
INSERT INTO tokens (hash_token, org_id, creado_en) VALUES ('<sha256_del_token>', 'org-demo', datetime('now'));
```

## Que no hace, a proposito

No corre modelos, no ve codigo, no acepta texto fuera del artefacto. El perfil minimizado del esquema existe para angostar lo que sale del entorno de un regulado: R9 remueve el texto libre que cubre, pero no alcanza a todo string del artefacto (ver "Que no hace" en el README de la herramienta). Es una reduccion de superficie, no la garantia de que no sale nada. Las metricas viajan igual.

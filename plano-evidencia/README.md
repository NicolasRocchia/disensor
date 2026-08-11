# Plano de evidencia (v0, Fase 2)

Worker de ingesta en Cloudflare (Workers mas D1) que recibe artefactos de residuo, los valida con el mismo nucleo de reglas que el gate, y devuelve un recibo de integridad: hash del cuerpo, timestamp del servidor y firma HMAC. Los recibos son de solo agregado, con triggers que lo hacen cumplir en la base: la independencia del custodio es arquitectura, no marketing.

## Estado de verificacion

Verificado en este repo:
- Conformidad del port TypeScript contra los 22 vectores de `spec/vectores` (`npm run conformidad`): mismo veredicto y mismas etiquetas de regla que la implementacion de referencia en Python, por vector.
- Verificacion cruzada del recibo (`npx tsx scripts/recibo.test.ts`): hash y firma HMAC coinciden con valores calculados por una implementacion independiente en Python.
- Typecheck estricto (`npm run typecheck`).

No verificado todavia (se estrena con `wrangler dev`): el handler HTTP contra D1 real, el flujo de tokens y el conflicto 409. Es deliberado: el nucleo con riesgo de divergencia esta blindado por vectores; el pegamento HTTP se prueba contra la plataforma real, no contra un mock que mentiria.

## Contrato de la API

- `POST /v1/artefactos` con `Authorization: Bearer <token>` y el artefacto JSON como cuerpo.
  - `201`: `{ "recibo": { "hash", "recibido_en", "firma" } }`
  - `200` con `repetido: true`: mismo evento, mismo contenido (idempotente).
  - `409`: mismo evento, otro contenido. Los recibos no se reemplazan; se devuelve el original.
  - `422`: artefacto invalido, con la lista de errores del validador.
  - `401`: token invalido o revocado.
- `GET /v1/salud`.

## Despliegue

```bash
wrangler d1 create residuo-evidencia          # pegar el database_id en wrangler.toml
wrangler d1 execute residuo-evidencia --file=schema.sql
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

No corre modelos, no ve codigo, no acepta texto fuera del artefacto. El perfil minimizado del esquema existe para que un regulado use esto sin que un solo texto libre salga de su entorno, y las metricas viajan igual.

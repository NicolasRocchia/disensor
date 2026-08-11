-- Plano de evidencia: esquema D1 (v0, Fase 2).
-- Datos de clientes con token. La red anonima (telemetria opt-in de la capa
-- dev, Fase 5) va en tablas separadas desde el dia uno, por diseno.

CREATE TABLE IF NOT EXISTS organizaciones (
  id TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  creado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tokens (
  hash_token TEXT PRIMARY KEY,          -- sha256 del token; el token en claro no se guarda
  org_id TEXT NOT NULL REFERENCES organizaciones(id),
  creado_en TEXT NOT NULL,
  revocado_en TEXT
);

CREATE TABLE IF NOT EXISTS artefactos (
  org_id TEXT NOT NULL REFERENCES organizaciones(id),
  id_evento TEXT NOT NULL,
  hash TEXT NOT NULL,                   -- sha256 del cuerpo recibido, tal como llego
  esquema TEXT NOT NULL,
  perfil TEXT NOT NULL,
  nivel TEXT NOT NULL,
  compuerta TEXT NOT NULL,
  recibido_en TEXT NOT NULL,
  cuerpo TEXT NOT NULL,
  PRIMARY KEY (org_id, id_evento)
);

CREATE INDEX IF NOT EXISTS idx_artefactos_org_fecha ON artefactos(org_id, recibido_en);

-- El registro que se vende: recibos de solo agregado. La independencia del
-- custodio tiene que ser real en la arquitectura, no en el marketing.
CREATE TABLE IF NOT EXISTS recibos (
  org_id TEXT NOT NULL,
  id_evento TEXT NOT NULL,
  hash TEXT NOT NULL,
  recibido_en TEXT NOT NULL,
  firma TEXT NOT NULL,                  -- HMAC-SHA256(secreto, hash || '.' || recibido_en)
  PRIMARY KEY (org_id, id_evento)
);

CREATE TRIGGER IF NOT EXISTS recibos_sin_update
BEFORE UPDATE ON recibos
BEGIN
  SELECT RAISE(ABORT, 'los recibos son de solo agregado');
END;

CREATE TRIGGER IF NOT EXISTS recibos_sin_delete
BEFORE DELETE ON recibos
BEGIN
  SELECT RAISE(ABORT, 'los recibos son de solo agregado');
END;

-- Fase 5 (telemetria opt-in de la red, perfil minimizado): tablas separadas.
CREATE TABLE IF NOT EXISTS red_anonima (
  install_id TEXT NOT NULL,
  recibido_en TEXT NOT NULL,
  cuerpo TEXT NOT NULL
);

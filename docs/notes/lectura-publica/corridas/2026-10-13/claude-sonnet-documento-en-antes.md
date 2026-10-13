# claude-sonnet, documento, en, antes

```yaml
modelo: claude-sonnet
modelo_pedido: sonnet
cli: claude 2.1.285 (Claude Code)
modo: documento
idioma: en
estado: antes
repeticion: 1
pregunta: What is disensor and what does the file it generates look like? Show an example of the artifact.
documento: README.md
commit: de14e5c
sha256: 1a5723141ea0f2f6db16ee496f8fe4086e801077e737bc4df1ead52d68d0093c
bytes: 44409
prompt_sha256: b7fb9d47368aa45b332bc481c5fcdf2676a209f6e4106df47bf95c31a4fda8af
comando: claude -p --safe-mode --no-session-persistence --model sonnet --output-format json --tools ""
inicio: 2026-10-13T10:01:19-03:00
fin: 2026-10-13T10:01:35-03:00
duracion_s: 16
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 15074
cli_duration_api_ms: 12815
cli_num_turns: 1
cli_total_cost_usd: 0.0799494
cli_subtype: success
cli_usage: {"input_tokens": 2, "cache_creation_input_tokens": 15913, "cache_read_input_tokens": 1467, "output_tokens": 1600, "output_tokens_details": {"thinking_tokens": 329}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 15913, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 1600, "cache_read_input_tokens": 1467, "cache_creation_input_tokens": 15913, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 15913}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

## Qué es disensor

Es la implementación de referencia de un artefacto llamado **residue** (residuo). Surge del método de **desacuerdo controlado**: un modelo genera el código, un modelo de otra familia lo ataca, el generador verifica cada hallazgo, y el ciclo termina cuando cada hallazgo está resuelto, refutado con evidencia o escalado a un humano.

El artefacto es un archivo JSON versionado en el repo (en `.residue/`), junto al código que juzga. No es un sello de calidad ni una métrica de cobertura. Registra lo que la revisión **no pudo establecer**: qué hallazgos se verificaron y contra qué, cuáles se refutaron, qué no se pudo ejecutar y qué queda a criterio de alguien.

Además del formato, disensor incluye:
- Un CLI que valida el archivo (reglas R0 a R13).
- Un gate de CI (checks G1 a G9) que frena el PR si el cambio exige un registro y falta, es genérico o no corresponde al cambio.
- Un informe HTML del residuo y un orquestador opcional de la ronda de revisión (`disensor round`).

## Cómo es el archivo

**El documento no incluye un ejemplo completo del artefacto.** Solo indica que hay tres ejemplos en `spec/examples/` (uno real anonimizado y uno con perfil minimizado) y que el esquema está en `spec/residue.schema.json` (versión `residue/v0.4`). Por eso no voy a inventar un JSON completo que podría no coincidir con el esquema real.

Lo que el texto sí permite decir es qué contiene, por los campos que menciona:

- **`schema`**: la versión, por ejemplo `residue/v0.4`.
- **Identidad**: el nombre del archivo es `<event_id>.json`, con `event_id` como UUID canónico. Hay un `event.pr`.
- **Gate y nivel**: `plan`, `diff` o `architecture`, y el `criticality_level`. En `diff`, también `base_commit` y el commit revisado.
- **Actores**: `generator`, `reviewers` y `human_arbiter`. Cada revisor lleva familia, modelo, `independence`, `fallback_reason` (si está por debajo de `cross_family`), `hardening` y confinamiento.
- **`prompt_hash`**: el `sha256:` de la consigna adversarial usada.
- **Hallazgos (findings)**: cada uno con un estado final (`incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive`, `escalated_open`), su `verification` (incluido `against`) y su evidencia (`text`, `link` o `hash`).
- **Residuo**: ítems con clases como `escalation_without_decision`, `principal_refutation`, `execution_gap`, `reviewer_correlation` y `reviewer_hardening_gap`.
- **Otros**: métricas (`counts`, `valid`, `false_positives`), `lead_acceptance`, `declaration` y `extensions`.
- **Perfil**: `full` o `minimized`. El segundo elimina texto libre como `text` y `link` de la evidencia.

## Lo único literal que muestra el documento

Es el archivo de configuración `disensor.config.json`, que no es el artefacto sino la política del repo:

```json
{
  "criticality_level": "B",
  "level_A_enabled": false
}
```

Para ver un artefacto real, abre los archivos de `spec/examples/` en el repositorio, o genera una plantilla con `disensor new --gate diff --level B`, que la deja prellenada en `.residue/`.

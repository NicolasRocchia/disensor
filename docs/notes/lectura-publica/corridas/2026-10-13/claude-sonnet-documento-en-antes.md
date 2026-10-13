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
inicio: 2026-10-13T09:47:42-03:00
fin: 2026-10-13T09:48:00-03:00
duracion_s: 17
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 16346
cli_duration_api_ms: 13734
cli_num_turns: 1
cli_total_cost_usd: 0.0812634
cli_subtype: success
cli_usage: {"input_tokens": 2, "cache_creation_input_tokens": 16454, "cache_read_input_tokens": 1467, "output_tokens": 1515, "output_tokens_details": {"thinking_tokens": 297}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 16454, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 1515, "cache_read_input_tokens": 1467, "cache_creation_input_tokens": 16454, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 16454}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 0
```

## Respuesta

## Qué es disensor

disensor es la implementación de referencia de un artefacto llamado **residuo** (*residue*), que sale del método de **desacuerdo controlado**. Un modelo genera el código, un modelo de otra familia lo ataca, el generador verifica cada hallazgo, y el ciclo termina cuando cada uno quedó resuelto, refutado con evidencia o escalado a un humano.

El artefacto es un archivo JSON versionado en el repositorio (en `.residue/<event_id>.json`), junto al código que juzga. No es una insignia verde ni un puntaje de cobertura. Registra lo que la revisión **no pudo establecer**:

- qué hallazgos se verificaron y contra qué
- cuáles se refutaron
- qué no se pudo ejecutar
- qué sigue dependiendo del criterio de alguien

También registra quién generó el cambio, quién lo revisó (y de qué familia de modelos), sobre qué commits, con qué consigna y quién aceptó el riesgo residual.

Además del esquema, el paquete incluye un validador por CLI (reglas R0 a R13), una compuerta de CI (G1 a G9) que frena el PR si falta la declaración, es genérica o no corresponde al cambio, y un informe HTML del residuo.

## Cómo se ve el archivo

**El documento no incluye ningún ejemplo completo del artefacto.** Solo indica que hay tres ejemplos en `spec/examples/` (uno real anonimizado y otro con el perfil `minimized`, sin texto libre) y que el esquema está en `spec/residue.schema.json` (versión `residue/v0.4`). No voy a inventar un JSON completo, porque la estructura exacta y el anidamiento no están en el texto.

Lo que el documento sí nombra como campos o conceptos del artefacto:

- `schema`: la versión, por ejemplo `residue/v0.4`
- `event_id` (un UUID canónico, que además da nombre al archivo) y `event.pr`
- gate: `plan`, `diff` o `architecture`; en `diff` también `base_commit`
- `criticality_level`
- perfil: `full` o `minimized`
- actores: `generator`, `reviewers` y `human_arbiter`
- en cada revisor: `family`, `independence`, `fallback_reason`, `hardening` y confinamiento
- `prompt_hash` (el `sha256:` de la consigna adversarial)
- hallazgos (*findings*) con `final_state`: `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive` o `escalated_open`
- `evidence` (`text`, `link` o `hash`) y `verification.against` (`repository`, `execution` o `external_source`)
- ítems de residuo, con clases como `escalation_without_decision`, `principal_refutation`, `execution_gap`, `reviewer_correlation` y `reviewer_hardening_gap`
- `metrics` (`counts`, `valid`, `false_positives`), `lead_acceptance` y `extensions`

Los únicos JSON concretos que muestra el documento son la configuración y el workflow, que **no son el artefacto**. La configuración generada por `disensor init` es:

```json
{
  "criticality_level": "B",
  "level_A_enabled": false
}
```

Para ver un artefacto real, abrí `spec/examples/` o generá una plantilla con `disensor new --gate diff --level B`, que la deja prellenada en `.residue/`.

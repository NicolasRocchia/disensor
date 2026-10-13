# claude-haiku, documento, en, antes

```yaml
modelo: claude-haiku
modelo_pedido: haiku
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
comando: claude -p --safe-mode --no-session-persistence --model haiku --output-format json --tools ""
inicio: 2026-10-13T09:49:00-03:00
fin: 2026-10-13T09:49:16-03:00
duracion_s: 16
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 14839
cli_duration_api_ms: 12765
cli_num_turns: 1
cli_total_cost_usd: 0.037681
cli_subtype: success
cli_usage: {"input_tokens": 9, "cache_creation_input_tokens": 15566, "cache_read_input_tokens": 0, "output_tokens": 1308, "output_tokens_details": {"thinking_tokens": 665}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 15566, "ephemeral_5m_input_tokens": 0}, "inference_geo": "not_available", "iterations": [{"input_tokens": 9, "output_tokens": 1308, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 15566, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 15566}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001"]
cli_llamadas_a_herramientas: 0
```

## Respuesta

# Disensor

**Disensor** es una herramienta que registra y valida lo que sucede en una revisión de código adversarial automatizada. Su propósito es documentar qué pasó cuando una IA generó código y otra IA de una familia diferente lo revisó.

## ¿Qué es?

Según el documento:

> "Your AI wrote the code. Another AI reviewed it. What happened in that review ends up as a JSON file in your repo, next to the code it judges."

Es la implementación de referencia de un artefacto llamado **residue** (residuo) que utiliza **controlled disagreement** (desacuerdo controlado):

1. Un modelo genera código
2. Un modelo de otra familia lo ataca adversarialmente
3. El generador verifica cada hallazgo
4. El ciclo termina cuando cada hallazgo ha sido resuelto, refutado con evidencia o escalado a una persona

## El archivo que genera

El artefacto es un **archivo JSON** que se coloca en el repositorio bajo `.residue/<event_id>.json` y declara:

- **Qué hallazgos fueron verificados** y contra qué
- **Qué fue refutado** con evidencia
- **Qué no pudo ejecutarse** y por qué
- **Qué sigue siendo un juicio humano**
- **Quién** generó el cambio, quién lo revisó (y de qué familia de modelo)
- **Sobre qué commits** se revisó
- **Con qué consigna** (brief adversarial)
- **Quién aceptó** el riesgo residual

## Esquema

El documento especifica que el esquema se encuentra en `spec/residue.schema.json` (JSON Schema 2020-12) en versión **residue/v0.4**.

## Ejemplos

El documento menciona que hay ejemplos en `spec/examples/`:
- Tres artefactos de ejemplo
- Incluyendo un evento real anonimizado
- Y el perfil minimizado sin texto libre

Sin embargo, el documento no muestra ejemplos detallados de la estructura JSON completa, solo describe que contiene campos como:
- `event`: información del evento
- `findings`: hallazgos encontrados
- `residue`: lo declarado como residuo
- `reviewers`: quiénes revisaron
- `generator`: quién generó
- `human_arbiter`: árbitro humano
- `final_state`: estado final de cada hallazgo (incorporado, deuda registrada, refutado, etc.)
- `verification`: detalles de verificación

# claude-haiku, documento, es, antes

```yaml
modelo: claude-haiku
modelo_pedido: haiku
cli: claude 2.1.285 (Claude Code)
modo: documento
idioma: es
estado: antes
repeticion: 1
pregunta: ¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.
documento: README.es.md
commit: de14e5c
sha256: 85d80fe0097ffcd4ca6e658306581787979dc26cbc7e79de7a4ceb31a2f24fc1
bytes: 45859
prompt_sha256: 45d77acac78c6e9718b020f5ca5d90aa305ae3a1384efb0ef90fa06eb7c83243
comando: claude -p --safe-mode --no-session-persistence --model haiku --output-format json --tools ""
inicio: 2026-10-13T09:48:23-03:00
fin: 2026-10-13T09:48:41-03:00
duracion_s: 18
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 16765
cli_duration_api_ms: 15005
cli_num_turns: 1
cli_total_cost_usd: 0.043122
cli_subtype: success
cli_usage: {"input_tokens": 9, "cache_creation_input_tokens": 18049, "cache_read_input_tokens": 0, "output_tokens": 1403, "output_tokens_details": {"thinking_tokens": 849}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 18049, "ephemeral_5m_input_tokens": 0}, "inference_geo": "not_available", "iterations": [{"input_tokens": 9, "output_tokens": 1403, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 18049, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 18049}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001"]
cli_llamadas_a_herramientas: 0
```

## Respuesta

# ¿Qué es disensor?

Disensor es un **registro versionado de revisión de código entre dos familias de modelos de IA**. Funciona así:

1. Tu IA escribió el código
2. Otra IA de una familia distinta lo revisó y atacó
3. Lo que pasó en esa revisión termina como un archivo JSON en tu repositorio

El núcleo es el método de **desacuerdo controlado**: un modelo genera, un modelo de otra familia ataca, el generador verifica cada hallazgo, y el ciclo termina cuando todo quedó resuelto, refutado con evidencia o escalado a un humano. El resultado se llama **residuo**: lo que la ronda deja para que lo mire una persona.

No es un puntaje de cobertura ni un badge verde. Es un **registro de lo que NO se pudo establecer**: qué hallazgos se verificaron y contra qué, cuáles se refutaron, qué no se pudo ejecutar y qué sigue descansando sobre el juicio de alguien.

# El archivo que genera

Es un archivo **JSON versionado** que vive en el repositorio:

- **Ubicación**: directorio `.residue/`
- **Nombre**: `<event_id>.json` (el event_id es un UUID canónico)
- **Esquema**: JSON Schema 2020-12, versión `residue/v0.4`
- **Contenido**: declara quién generó el cambio, quién lo revisó, de qué familia de modelos, sobre qué commits, con qué consigna, y quién aceptó el riesgo residual

El gate de CI valida estos artefactos (reglas R0 a R13), lo que evita que lleguen duplicados, genéricos o que no cubran el cambio real.

# Ejemplo del artefacto

El documento menciona que existen ejemplos en `spec/examples/`, pero **no incluye un ejemplo completo en este texto**. Solo especifica que hay:
- Tres artefactos de ejemplo
- Un evento real anonimizado
- El perfil minimizado sin texto libre

Para ver un ejemplo real, habría que consultar el repositorio de disensor directamente.

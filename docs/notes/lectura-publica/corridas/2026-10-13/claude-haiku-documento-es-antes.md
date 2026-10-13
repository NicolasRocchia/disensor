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
inicio: 2026-10-13T10:01:59-03:00
fin: 2026-10-13T10:02:17-03:00
duracion_s: 18
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 17177
cli_duration_api_ms: 15353
cli_num_turns: 1
cli_total_cost_usd: 0.042075
cli_subtype: success
cli_usage: {"input_tokens": 9, "cache_creation_input_tokens": 17623, "cache_read_input_tokens": 0, "output_tokens": 1364, "output_tokens_details": {"thinking_tokens": 853}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 17623, "ephemeral_5m_input_tokens": 0}, "inference_geo": "not_available", "iterations": [{"input_tokens": 9, "output_tokens": 1364, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 17623, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 17623}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001"]
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

# Qué es disensor

**Disensor** es un paquete Python que implementa un método llamado **desacuerdo controlado**. En resumen:

- Una IA genera código
- Otra IA de una familia de modelos distinta lo revisa de forma adversarial
- El generador verifica cada hallazgo encontrado
- El ciclo termina cuando cada hallazgo se resuelve, se refuta con evidencia o se escala a una persona

Disensor es la implementación de referencia que define y valida el artefacto que resulta de este proceso: la **declaración de residuo** (lo que la revisión dejó para que lo mire un humano).

# El archivo que genera

El archivo es un **JSON versionado** que registra:

- Qué hallazgos se verificaron y contra qué
- Cuáles se refutaron
- Qué no se pudo ejecutar
- Qué sigue descansando sobre el juicio de alguien
- Quién generó el cambio, quién lo revisó (y de qué familia de modelos)
- Sobre qué commits, con qué consigna
- Quién aceptó el riesgo residual

Es **residuo, no cobertura**: dirige el escrutinio del revisor humano en lugar de ser un sello de calidad. El archivo se coloca en el repositorio junto al código que juzga, al lado del código versionado.

# Ejemplo del artefacto

El documento menciona que existen ejemplos en `spec/examples/`, incluido un evento real anonimizado, pero **no proporciona un JSON de ejemplo completo**. 

Sin embargo, describe la estructura del artefacto: versión del esquema (`residue/v0.4`), identificador único (`event_id`), datos del evento (PR, commits), actores (generador, revisores, árbitro humano), hallazgos (con texto, evidencia, estado final), ítems de residuo (escalado sin decisión, refutación, gaps de ejecución) y métricas.

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
inicio: 2026-10-13T10:02:37-03:00
fin: 2026-10-13T10:02:55-03:00
duracion_s: 17
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 16549
cli_duration_api_ms: 14541
cli_num_turns: 1
cli_total_cost_usd: 0.036844
cli_subtype: success
cli_usage: {"input_tokens": 9, "cache_creation_input_tokens": 15140, "cache_read_input_tokens": 0, "output_tokens": 1311, "output_tokens_details": {"thinking_tokens": 826}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 15140, "ephemeral_5m_input_tokens": 0}, "inference_geo": "not_available", "iterations": [{"input_tokens": 9, "output_tokens": 1311, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 15140, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 15140}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001"]
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

# Qué es disensor

**disensor** es una herramienta que crea un registro verificable de lo que sucedió en una revisión de código realizada por múltiples asistentes de IA. Genera un archivo JSON en tu repositorio que documenta:

- Qué IA generó el código
- Qué IA de otra familia lo revisó (desacuerdo controlado)
- Cada hallazgo encontrado en la revisión
- El estado final de cada hallazgo: incorporado, refutado con evidencia, o escalado a un humano
- Quién es el árbitro humano responsable de los riesgos residuales

El método que implementa se llama **"desacuerdo controlado"**: un modelo genera, otro modelo de familia diferente ataca, el generador verifica cada hallazgo, y el ciclo termina cuando cada hallazgo se resuelve, se refuta con evidencia, o se escala a una persona.

## El archivo que genera

El artefacto es un archivo JSON llamado `<event_id>.json` que se guarda en el directorio `.residue/` del repositorio. Contiene la **"declaración de residuo"** —lo que la revisión dejó para que una persona examine— con campos como:

- Información del evento (`event`), incluyendo PR y commits revisados
- Actores: generador, revisores, árbitro humano
- Hallazgos (`findings`) con su estado final
- Residuo: lo que quedó sin resolver, las deudas técnicas, las brechas de ejecución
- Datos de independencia y verificación

## Ejemplo del artefacto

Lamentablemente, **el documento no incluye un ejemplo concreto del JSON completo**. Solo menciona que hay tres ejemplos de artefactos en `spec/examples/`, incluyendo un evento anonimizado real y un perfil minimizado sin texto libre, pero no los muestra en el contenido proporcionado.

# claude-sonnet, documento, es, antes

```yaml
modelo: claude-sonnet
modelo_pedido: sonnet
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
comando: claude -p --safe-mode --no-session-persistence --model sonnet --output-format json --tools ""
inicio: 2026-10-13T09:47:06-03:00
fin: 2026-10-13T09:47:23-03:00
duracion_s: 16
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 15503
cli_duration_api_ms: 13069
cli_num_turns: 1
cli_total_cost_usd: 0.0955274
cli_subtype: success
cli_usage: {"input_tokens": 2, "cache_creation_input_tokens": 19450, "cache_read_input_tokens": 1467, "output_tokens": 1743, "output_tokens_details": {"thinking_tokens": 400}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 19450, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 1743, "cache_read_input_tokens": 1467, "cache_creation_input_tokens": 19450, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 19450}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 0
```

## Respuesta

## Qué es disensor

Es la implementación de referencia de un artefacto: la **declaración de residuo**. Es un archivo JSON versionado en el repo, junto al código que juzga, que registra qué pasó cuando una IA revisó el código escrito por otra IA. Pertenece al método de **desacuerdo controlado**: un modelo genera, un modelo de otra familia ataca, el generador verifica cada hallazgo, y el ciclo termina cuando cada hallazgo quedó resuelto, refutado con evidencia o escalado a un humano.

Lo que lo distingue es que no es un sello de calidad ni un puntaje de cobertura. Lista **residuo**: lo que la revisión no pudo establecer y sigue dependiendo de un juicio humano.

Alrededor del archivo hay tres piezas:
- Un **CLI** (`disensor validate`, con reglas R0 a R13) que valida el archivo.
- Un **gate de CI** (chequeos G1 a G9) que frena el PR si el cambio exige un registro y falta, es genérico o no coincide con el cambio.
- Un **informe HTML** (`disensor report`) que muestra primero lo que quedó abierto.

## Cómo es el archivo

- Vive en `.residue/<event_id>.json`, y el `event_id` es un UUID canónico.
- Su esquema es JSON Schema 2020-12, hoy `residue/v0.4`.
- Registra:
  - quién generó y quién revisó, con la familia de modelo y la independencia real de la ronda;
  - sobre qué commits (`base_commit` es obligatorio en la compuerta `diff`);
  - el hash de la consigna (`prompt_hash`);
  - los hallazgos con su `final_state`: `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive` o `escalated_open`;
  - la evidencia (`text`, `link` o `hash`) y `verification.against`;
  - el residuo, con clases como `escalation_without_decision`, `principal_refutation`, `execution_gap` y `reviewer_correlation`;
  - el árbitro humano y quién aceptó el riesgo (`lead_acceptance`).
- Tiene un perfil `minimized` que quita el texto libre del hallazgo y la evidencia.

## Ejemplo

El documento **no incluye el contenido de un artefacto completo**. Solo dice que hay tres ejemplos en `spec/examples/`, uno de ellos un evento real anonimizado. Lo que sigue es un **esbozo ilustrativo** armado con los nombres de campo que menciona el texto. La anidación y los valores son supuestos míos, no el esquema real:

```json
{
  "schema": "residue/v0.4",
  "event_id": "<uuid-canónico>",
  "gate": "diff",
  "profile": "full",
  "event": { "pr": "...", "base_commit": "<sha>" },
  "actors": {
    "generator": { "family": "anthropic" },
    "reviewers": [
      {
        "family": "<otra-familia>",
        "independence": "cross_family",
        "prompt_hash": "sha256:..."
      }
    ],
    "human_arbiter": { "id": "..." }
  },
  "findings": [
    {
      "final_state": "refuted_verifiable",
      "evidence": { "text": "..." },
      "verification": { "against": "execution" }
    }
  ],
  "residue": {
    "declaration": "...",
    "items": [
      { "class": "execution_gap", "description": "..." }
    ]
  },
  "lead_acceptance": "..."
}
```

Para ver uno real, el documento remite a `spec/examples/`. Con `disensor new --gate diff --level B` se genera una plantilla prellenada en `.residue/`, y `disensor guide` imprime la guía de llenado.

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
inicio: 2026-10-13T10:00:40-03:00
fin: 2026-10-13T10:00:57-03:00
duracion_s: 17
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 15850
cli_duration_api_ms: 12530
cli_num_turns: 1
cli_total_cost_usd: 0.0925614
cli_subtype: success
cli_usage: {"input_tokens": 2, "cache_creation_input_tokens": 18931, "cache_read_input_tokens": 1467, "output_tokens": 1654, "output_tokens_details": {"thinking_tokens": 397}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 18931, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 1654, "cache_read_input_tokens": 1467, "cache_creation_input_tokens": 18931, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 18931}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

# Qué es disensor

Es una herramienta (paquete Python, CLI y GitHub Action) que implementa el método del **desacuerdo controlado**: un modelo genera el código, un modelo de **otra familia** lo ataca, el generador verifica cada hallazgo y el ciclo termina cuando todo hallazgo quedó resuelto, refutado con evidencia o escalado a un humano.

Lo que produce es una **declaración de residuo**: un registro versionado de lo que la revisión no pudo establecer, no un sello de calidad ni un puntaje de cobertura. Un validador (reglas R0 a R13) la revisa, y un gate de CI (G1 a G9) frena el PR si el cambio exige una declaración y esta falta, es genérica o no coincide con el cambio.

# Cómo es el archivo

- Es un JSON en `.residue/<event_id>.json`, donde `event_id` es un UUID canónico, versionado en git junto al código.
- Se valida contra `spec/residue.schema.json` (JSON Schema 2020-12), hoy `residue/v0.4`.
- Registra quién generó el cambio, quién lo revisó y de qué familia de modelos, sobre qué commits, con qué consigna (`prompt_hash`) y quién aceptó el riesgo residual.
- Lista los hallazgos con su estado final (`incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive`, `escalated_open`) y los ítems de residuo (`escalation_without_decision`, `principal_refutation`, `execution_gap`, y desde v0.4 `reviewer_correlation` y `reviewer_hardening_gap`).
- Tiene un perfil `full` y uno `minimized`, que remueve el texto libre de los hallazgos.
- Es de solo agregar: el gate (G8) no deja modificar ni borrar declaraciones ya existentes.

# Ejemplo del artefacto

El documento **no incluye un artefacto completo**. Solo dice que hay tres ejemplos en `spec/examples/`, uno de ellos un evento real anonimizado. Lo que sigue es un **boceto ilustrativo** armado con los nombres de campo que el texto menciona; la anidación exacta y los valores son supuestos míos, así que no lo tomes como el formato real:

```json
{
  "schema": "residue/v0.4",
  "event_id": "3f2b8c1e-9a47-4d6b-b1e2-5c7a90d4e812",
  "profile": "full",
  "gate": "diff",
  "criticality_level": "B",
  "base_commit": "<sha del commit base revisado>",
  "prompt_hash": "sha256:<hash de la consigna adversarial>",
  "actors": {
    "generator": { "family": "anthropic" },
    "reviewers": [
      {
        "family": "<otra familia>",
        "independence": "cross_family",
        "hardening": "verified"
      }
    ],
    "human_arbiter": { "id": "<quién arbitró>" }
  },
  "findings": [
    {
      "final_state": "refuted_verifiable",
      "evidence": { "text": "<qué se comprobó>" },
      "verification": { "against": "repository", "detail": "<cómo>" }
    }
  ],
  "residue": [
    { "class": "execution_gap", "description": "<qué no se pudo ejecutar>" }
  ]
}
```

Para ver uno real, mirá `spec/examples/`, o generá una plantilla con `disensor new --gate diff --level B` y validala con `disensor validate .residue/<id>.json`.

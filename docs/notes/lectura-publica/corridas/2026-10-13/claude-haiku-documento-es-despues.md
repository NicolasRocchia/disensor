# claude-haiku, documento, es, despues

```yaml
modelo: claude-haiku
modelo_pedido: haiku
cli: claude 2.1.285 (Claude Code)
modo: documento
idioma: es
estado: despues
repeticion: 1
pregunta: ¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.
documento: README.es.md
commit: 96e12ae
sha256: 745785e7f888beb206a7d6e84967d7d3be56c52ea6d99dd273488a5c9d283bc8
bytes: 52212
prompt_sha256: f3248622878cee70fab342d2d0f0243d896a86bd0633e7be187ab9abe934a9ec
comando: claude -p --safe-mode --no-session-persistence --model haiku --output-format json --tools ""
inicio: 2026-10-13T10:02:17-03:00
fin: 2026-10-13T10:02:37-03:00
duracion_s: 19
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 18537
cli_duration_api_ms: 16636
cli_num_turns: 1
cli_total_cost_usd: 0.046844
cli_subtype: success
cli_usage: {"input_tokens": 9, "cache_creation_input_tokens": 19710, "cache_read_input_tokens": 0, "output_tokens": 1483, "output_tokens_details": {"thinking_tokens": 444}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 19710, "ephemeral_5m_input_tokens": 0}, "inference_geo": "not_available", "iterations": [{"input_tokens": 9, "output_tokens": 1483, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 19710, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 19710}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001"]
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

# disensor

## ¿Qué es?

**disensor** es una herramienta que registra y valida el resultado de una revisión de código entre modelos de IA. Según el documento:

> Tu IA escribió el código. Otra IA lo revisó. Lo que pasó en esa revisión termina como un archivo JSON en tu repo, al lado del código que juzga.

Es la implementación de referencia de un artefacto llamado **"residuo"**: el registro versionado de lo que la revisión no pudo establecer, es decir, qué hallazgos se verificaron y contra qué, cuáles se refutaron, qué no se pudo ejecutar y qué sigue descansando sobre el juicio de alguien.

El método detrás se llama **desacuerdo controlado**: un modelo genera código, un modelo de otra familia lo ataca (revisa críticamente), el generador verifica cada hallazgo, y el ciclo termina cuando todo hallazgo quedó resuelto, refutado con evidencia o escalado a un humano.

## ¿Cómo es el archivo que genera?

El archivo es un **JSON estructurado** (declaración de residuo) que contiene:

- `schema`: versión del esquema (ej: `residue/v0.4`)
- `event`: metadatos del evento (ID, timestamps, commits revisados, nivel de criticidad)
- `actors`: quién generó, quién revisó (familia de modelo, modelo específico, independencia) y si hay árbitro humano
- `findings`: lista de hallazgos encontrados en la revisión, con su estado final (incorporado, refutado, escalado, etc.)
- `residue`: items que quedan pendientes o cerrados (lo que pide atención humana)
- `metrics`: conteos de hallazgos válidos y falsos positivos

## Ejemplo del artefacto

Un extracto real del repositorio de disensor (PR #101):

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "27089d19-ee91-4c6c-b517-63b9627969e0",
    "created_at": "2026-09-29T10:21:11-03:00",
    "repository": "github.com/NicolasRocchia/disensor",
    "gate": "diff",
    "criticality_level": "B",
    "base_commit": "b340cfc30fc418957f2dfafc82c1e14bf8e87884",
    "head_commit": "c2970915df2501b5eb214e3272174bb03638f610"
  },
  "actors": {
    "generator": {
      "family": "anthropic",
      "model": "claude-fable-5-1"
    },
    "reviewers": [
      {
        "reviewer_id": "r8",
        "family": "openai",
        "model": "gpt-5.6-sol",
        "independence": "cross_family"
      }
    ],
    "human_arbiter": {
      "present": true
    }
  },
  "findings": [
    {
      "id": "h15",
      "origin": "r8",
      "severity": "major",
      "title": "Una declaración que el gate rechaza...",
      "final_state": "incorporated",
      "verification": {
        "against": "repository"
      }
    }
  ],
  "residue": {
    "items": [
      {
        "id": "r4",
        "class": "principal_refutation",
        "finding_ref": "h16",
        "refutation_type": "verifiable"
      }
    ]
  },
  "metrics": {
    "counts": {
      "total_findings": 19,
      "valid": {
        "incorporated": 18
      }
    }
  }
}
```

El archivo se guarda en `.residue/<event_id>.json` al lado del código, es versionado en git y validado automáticamente por un gate en CI.

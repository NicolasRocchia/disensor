# claude-haiku, documento, en, despues

```yaml
modelo: claude-haiku
modelo_pedido: haiku
cli: claude 2.1.285 (Claude Code)
modo: documento
idioma: en
estado: despues
repeticion: 1
pregunta: What is disensor and what does the file it generates look like? Show an example of the artifact.
documento: README.md
commit: 96e12ae
sha256: 2ded6b061429bd9605ab139e78b6ce8040fd44d8c8c70b5508ec88d40596458d
bytes: 50741
prompt_sha256: 1480ae919bd016d6d0c86cd791000056bb8da56603faed091e3caaf491669962
comando: claude -p --safe-mode --no-session-persistence --model haiku --output-format json --tools ""
inicio: 2026-10-13T09:49:16-03:00
fin: 2026-10-13T09:49:35-03:00
duracion_s: 18
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 17439
cli_duration_api_ms: 15426
cli_num_turns: 1
cli_total_cost_usd: 0.04230299999999999
cli_subtype: success
cli_usage: {"input_tokens": 9, "cache_creation_input_tokens": 17587, "cache_read_input_tokens": 0, "output_tokens": 1424, "output_tokens_details": {"thinking_tokens": 502}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 17587, "ephemeral_5m_input_tokens": 0}, "inference_geo": "not_available", "iterations": [{"input_tokens": 9, "output_tokens": 1424, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 17587, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 17587}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001"]
cli_llamadas_a_herramientas: 0
```

## Respuesta

# ¿Qué es disensor?

Disensor es una herramienta que registra y valida lo que sucede cuando una IA revisa el código escrito por otra IA. Genera un archivo JSON versionado en tu repositorio que documenta el resultado de una revisión adversarial automatizada.

El método detrás de disensor se llama **desacuerdo controlado**: un modelo genera código, otro modelo de una familia diferente lo ataca (revisa adversarialmente), el generador verifica cada hallazgo, y el ciclo termina cuando cada hallazgo ha sido resuelto, refutado con evidencia o escalado a un humano.

Lo que disensor crea es un **residuo** (residue): no un sello de calidad ni una puntuación de cobertura, sino un registro versionado de lo que la revisión **no pudo cerrar** — qué hallazgos fueron verificados, contra qué, cuáles fueron refutados con evidencia, cuáles no pudieron ejecutarse, y cuáles descansan en el juicio de alguien.

## Aspecto del archivo

Es un archivo JSON declarativo con estructura definida por el esquema `residue/v0.4`, ubicado en `.residue/<event_id>.json`.

## Ejemplo de artefacto

El documento incluye un fragmento real de una declaración de revisión (PR #101 del repositorio de disensor):

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
      "title": "Una declaracion que el gate rechaza...",
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

Contiene: qué se revisó (commits), quién lo generó y revisó (modelos y familias), diecinueve hallazgos identificados (dieciocho incorporados, uno refutado con evidencia), y el residuo que quedó para examen humano.

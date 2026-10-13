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
inicio: 2026-10-13T09:48:41-03:00
fin: 2026-10-13T09:49:00-03:00
duracion_s: 19
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 17867
cli_duration_api_ms: 16004
cli_num_turns: 1
cli_total_cost_usd: 0.047805
cli_subtype: success
cli_usage: {"input_tokens": 9, "cache_creation_input_tokens": 20133, "cache_read_input_tokens": 0, "output_tokens": 1506, "output_tokens_details": {"thinking_tokens": 516}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 20133, "ephemeral_5m_input_tokens": 0}, "inference_geo": "not_available", "iterations": [{"input_tokens": 9, "output_tokens": 1506, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 20133, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 20133}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001"]
cli_llamadas_a_herramientas: 0
```

## Respuesta

# ¿Qué es disensor?

**disensor** es una herramienta que registra lo que sucede cuando una IA revisa código generado por otra IA. Según el documento:

> "Tu IA escribió el código. Otra IA lo revisó. Lo que pasó en esa revisión termina como un archivo JSON en tu repo, al lado del código que juzga."

El método que implementa se llama **desacuerdo controlado**: un modelo genera el código, un modelo de otra familia lo ataca identificando hallazgos, el generador verifica cada hallazgo, y el ciclo termina cuando todo quedó resuelto, refutado con evidencia o escalado a un humano.

El resultado es una **declaración de residuo**: lo que la ronda deja para que lo mire una persona. No es un sello de aprobación, sino un registro versionado que dice:
- Quién generó el cambio y quién lo revisó
- De qué familia de modelos
- Sobre qué commits
- Con qué consigna
- Quién aceptó el riesgo residual

## El archivo que genera

Es un **archivo JSON** con esquema `residue/v0.4`. El documento lo describe como un "artefacto" que lista residuo, no cobertura: dirige el escrutinio del revisor humano en lugar de leerse como sello de calidad.

## Ejemplo del artefacto

Este es un extracto real del repositorio disensor, de `.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json`:

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
      "title": "Una declaracion que el gate rechaza por sus propias comprobaciones daba por cubierto el merge",
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
        "finding_ref": "h15",
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

El archivo documenta: quién generó, quién revisó (de otra familia de modelo), qué hallazgos se encontraron, en qué estado final terminaron (incorporado, rechazado, escalado a humano), y qué residuo quedó pendiente para revisión humana.

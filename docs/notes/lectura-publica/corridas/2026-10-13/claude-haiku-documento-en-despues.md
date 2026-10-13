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
inicio: 2026-10-13T10:02:55-03:00
fin: 2026-10-13T10:03:16-03:00
duracion_s: 20
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 19218
cli_duration_api_ms: 15421
cli_num_turns: 1
cli_total_cost_usd: 0.041762
cli_subtype: success
cli_usage: {"input_tokens": 9, "cache_creation_input_tokens": 17394, "cache_read_input_tokens": 0, "output_tokens": 1393, "output_tokens_details": {"thinking_tokens": 388}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 17394, "ephemeral_5m_input_tokens": 0}, "inference_geo": "not_available", "iterations": [{"input_tokens": 9, "output_tokens": 1393, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 17394, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 17394}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001"]
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

# Disensor

**Disensor** es un sistema que registra y valida las revisiones de código realizadas por IA. Su propósito es que cuando una IA genera código y otra IA lo revisa, el resultado de esa revisión quede documentado en un archivo JSON versionado en el repositorio, junto al código que se juzga.

No es una puntuación de cobertura ni un sello de calidad, sino un **registro versioned de lo que la revisión no pudo establecer**: qué hallazgos se verificaron y contra qué, cuáles se refutaron, qué no se pudo ejecutar, y qué sigue descansando en el juicio humano.

## Cómo se ve el archivo

El archivo generado es un **archivo JSON** almacenado en el directorio `.residue/` del repositorio. Tiene una estructura que incluye:

- **Esquema**: Versión del formato (ej: `residue/v0.4`)
- **Evento**: Información sobre cuándo ocurrió, qué commits se revisaron, nivel de criticidad
- **Actores**: Quién generó el código, quién lo revisó y de qué familia de modelos, quién fue el árbitro humano
- **Hallazgos** (*findings*): Problemas o observaciones que el revisor encontró
- **Residuo** (*residue*): Qué quedó sin resolver después de todo, qué necesita atención humana

## Ejemplo del artefacto

Este es un fragmento real del archivo `.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json` de la PR #101:

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
        "independence": "cross_family",
        "confinement": {
          "mode": "read_only_by_instruction",
          "verified": true
        }
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
        "against": "repository",
        "detail": "Comparadas las comprobaciones inline de _run_gate..."
      }
    }
  ],
  "metrics": {
    "counts": {
      "total_findings": 19,
      "valid": {
        "incorporated": 18,
        "refuted_verifiable": 1
      }
    }
  }
}
```

El archivo documenta que un modelo Anthropic (Claude) generó el código, un modelo OpenAI (GPT) lo revisó, encontraron 19 hallazgos, 18 fueron incorporados y 1 fue refutado con evidencia. Todo queda registrado de forma auditoria.

# claude-sonnet, busqueda, es, despues

```yaml
modelo: claude-sonnet
modelo_pedido: sonnet
cli: claude 2.1.285 (Claude Code)
modo: busqueda
idioma: es
estado: despues
repeticion: 1
pregunta: ¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.
documento: web
prompt_sha256: 4ec215dace14d8514928f29562b271ca82cf55a519516b789e4750ed9c01f39d
comando: claude -p --safe-mode --no-session-persistence --model sonnet --output-format json --tools WebSearch,WebFetch
inicio: 2026-10-13T10:03:16-03:00
fin: 2026-10-13T10:03:59-03:00
duracion_s: 43
confinamiento: con búsqueda web, a propósito
cli_duration_ms: 42112
cli_duration_api_ms: 49441
cli_num_turns: 6
cli_total_cost_usd: 0.13749719999999999
cli_subtype: success
cli_usage: {"input_tokens": 8, "cache_creation_input_tokens": 5730, "cache_read_input_tokens": 17841, "output_tokens": 2047, "output_tokens_details": {"thinking_tokens": 18}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 5730, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 1508, "cache_read_input_tokens": 6402, "cache_creation_input_tokens": 1917, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 1917}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001", "claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 5
cli_eventos_ilegibles: 0
```

## Respuesta

**Qué es disensor**

Disensor es una CLI en Python y una GitHub Action que implementa lo que llaman "controlled disagreement" en el código escrito con IA. Una IA genera el código y otra, de una familia de modelos distinta, lo ataca como revisora. Después, el generador resuelve los hallazgos. En vez de dar un visto bueno, la herramienta deja un registro estructurado de qué hallazgos se verificaron, cuáles se refutaron, cuáles se escalaron y cuáles quedaron sin decidir. El gate de CI valida ese registro contra el schema, contra sus reglas y contra el cambio real del pull request ([repo en GitHub](https://github.com/NicolasRocchia/disensor), [disensor.dev](https://disensor.dev/)). Según el repo, el gate no usa modelos ni API keys. Se instala con `pip install disensor` ([PyPI](https://pypi.org/project/disensor/0.11.0/)).

**El archivo que genera (la "residue declaration")**

Según el [repo](https://github.com/NicolasRocchia/disensor) y [disensor.dev](https://disensor.dev/):

- **Ubicación y nombre:** `.residue/<event_id>.json` en la raíz del repo. El `event_id` es un UUID. Por ejemplo: `.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json`.
- **Schema:** `residue/v0.4`, un JSON Schema 2020-12 congelado, en `spec/residue.schema.json`.
- **Campos principales:**
  - `event`: id, fecha, repositorio, tipo de gate, nivel de criticidad y commits base y head.
  - `actors`: el generador, los revisores (con su independencia, por ejemplo `cross_family`) y el árbitro humano.
  - `findings`: cada hallazgo tiene id, severidad, título, descripción, ubicación y un `final_state`. Los estados posibles son `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive` y `escalated_open`.
  - `residue.items`: lo que queda para atención humana.
  - `metrics`: conteos por estado de los hallazgos y falsos positivos.
- **Qué registra:** lo que la ronda de revisión no pudo cerrar, no si el código fue aprobado.

**Ejemplo**

Es un extracto del artefacto real del PR #101 del propio repo, según lo muestra la documentación. Esta parte cubre solo `schema`, `event` y `actors`. No pude ver `findings`, `residue` ni `metrics` con su contenido completo.

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
    "generator": { "family": "anthropic", "model": "claude-fable-5-1" },
    "reviewers": [
      {
        "reviewer_id": "r8",
        "family": "openai",
        "model": "gpt-5.6-sol",
        "independence": "cross_family"
      }
    ],
    "human_arbiter": { "present": true }
  }
}
```

Según [disensor.dev](https://disensor.dev/), el artefacto completo de ese PR tiene 19 hallazgos: 18 incorporados y 1 refutado con evidencia. También tiene 4 ítems de residuo para revisión humana, aunque todos los hallazgos llegaron a un estado terminal.

Si quiere el JSON completo, el archivo está en la carpeta `.residue/` del repo.

Sources:
- [GitHub – NicolasRocchia/disensor](https://github.com/NicolasRocchia/disensor)
- [Disensor (sitio oficial)](https://disensor.dev/)
- [disensor en PyPI](https://pypi.org/project/disensor/0.11.0/)

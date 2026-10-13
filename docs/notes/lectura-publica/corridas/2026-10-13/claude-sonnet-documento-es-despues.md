# claude-sonnet, documento, es, despues

```yaml
modelo: claude-sonnet
modelo_pedido: sonnet
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
comando: claude -p --safe-mode --no-session-persistence --model sonnet --output-format json --tools ""
inicio: 2026-10-13T10:00:57-03:00
fin: 2026-10-13T10:01:19-03:00
duracion_s: 21
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 20037
cli_duration_api_ms: 17782
cli_num_turns: 1
cli_total_cost_usd: 0.1146114
cli_subtype: success
cli_usage: {"input_tokens": 2, "cache_creation_input_tokens": 21546, "cache_read_input_tokens": 1467, "output_tokens": 2813, "output_tokens_details": {"thinking_tokens": 262}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 21546, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 2813, "cache_read_input_tokens": 1467, "cache_creation_input_tokens": 21546, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 21546}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

# Qué es disensor

Es la implementación de referencia de un artefacto: un **archivo JSON versionado en el repo** (en `.residue/`), al lado del código que juzga. Registra lo que pasó en la revisión de un cambio generado por una IA y revisado por otra IA, y sobre todo **lo que la revisión no pudo establecer** (el "residuo"). No es un badge verde ni un puntaje de cobertura: dirige el escrutinio del revisor humano en lugar de funcionar como sello de calidad.

El método detrás es el **desacuerdo controlado**:
- Un modelo genera el cambio.
- Un modelo de **otra familia** lo ataca.
- El generador verifica cada hallazgo.
- El ciclo termina cuando cada hallazgo quedó incorporado, refutado con evidencia o escalado a un humano.

Además del esquema (`residue/v0.4`), incluye:
- **CLI** (`disensor validate`, `new`, `round`, `report`, etc.): valida el archivo con las reglas R0 a R13.
- **Gate de CI** (GitHub Action): frena el PR si el cambio exige un registro y falta, es genérico o no coincide con el cambio.
- **Informe HTML** autocontenido con el residuo primero.

# Cómo es el archivo

El registro dice:
- quién generó el cambio y quién lo revisó (familia y modelo);
- sobre qué commits;
- con qué consigna (`prompt_hash`);
- qué hallazgos hubo y su estado final;
- qué verificó el generador y contra qué;
- qué queda como residuo;
- quién es el árbitro humano.

Este es el extracto real del documento (el evento de la declaración del PR #101 del propio repo), con algunas descripciones largas abreviadas con `…`:

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
        "independence": "cross_family",
        "confinement": {
          "mode": "read_only_by_instruction",
          "verified": true,
          "verification_method": "clean_git_status"
        },
        "hardening": "verified",
        "prompt_hash": "sha256:3494df5ebd20cc793ff9c5a214a2e715758e69c41bbc9e09b70f7d3064ee6a1c"
      }
    ],
    "human_arbiter": { "present": true }
  },
  "findings": [
    {
      "id": "h15",
      "origin": "r8",
      "severity": "major",
      "title": "Una declaracion que el gate rechaza por sus propias comprobaciones daba por cubierto el merge",
      "description": "El recorrido validaba el esquema y aplicaba G5, G6 y G7, pero no las comprobaciones por artefacto del gate … ",
      "location": "src/disensor/gate.py (judge_artifact); src/disensor/branch.py (_judge_merge, _historical_ids)",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Comparadas las comprobaciones inline de _run_gate … con lo que aplicaba _judge_merge; …"
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_branch.py::test_a_declaration_the_gate_rejects_on_its_own_checks_covers_nothing, …"
      }
    },
    {
      "id": "h16",
      "origin": "r8",
      "severity": "info",
      "title": "La resolucion de un merge con conflictos no entra en la cobertura",
      "description": "Hipotesis del revisor: el recorrido evalua el rango desde el merge base hasta el segundo padre … ",
      "location": "src/disensor/branch.py (_judge_merge); src/disensor/gate.py (resolve_context, evaluate_coverage)",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "repository",
        "detail": "Es el contrato del gate, no del panel: resolve_context toma head_oid como head del PR … "
      },
      "evidence": {
        "text": "gate.py, resolve_context: head_oid = gitctx.resolve_commit(head, repo_dir); status = gitctx.changed_status(mb, head_oid, repo_dir). El rango juzgado es merge base a head del PR."
      }
    }
  ],
  "residue": {
    "items": [
      {
        "id": "r4",
        "class": "principal_refutation",
        "finding_ref": "h16",
        "refutation_type": "verifiable",
        "requires_human_attention": false,
        "description": "El revisor sugirio que la cobertura mirara el arbol del commit de merge y no el head del PR; se refuto con el codigo del gate … "
      }
    ]
  },
  "metrics": {
    "counts": {
      "total_findings": 19,
      "valid": { "incorporated": 18, "debt_recorded": 0, "owner_decision": 0 },
      "false_positives": { "refuted_verifiable": 1, "refuted_interpretive": 0 },
      "escalated_open": 0
    }
  }
}
```

# Cómo leerlo

- **Contexto del ejemplo**: un cambio generado por un modelo de Anthropic pasó por doce corridas de un revisor de OpenAI, que devolvieron 19 hallazgos: 18 incorporados y 1 refutado con evidencia. El extracto muestra una de esas corridas.
- **`final_state`**: estado terminal del hallazgo, uno de seis: `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive`, `escalated_open`.
- **`verification.against`**: contra qué verificó el generador (`repository`, `execution` o `external_source`).
- **`fix_verification`**: cómo se verificó la corrección de un hallazgo incorporado.
- **`residue.items`**: cada ítem apunta a su hallazgo con `finding_ref`. Un hallazgo refutado con evidencia cierra igual y entra al residuo, para que una persona pueda no dar la refutación por buena.
- **`independence: cross_family`**: generador y revisor son de familias distintas, lo que exige la regla R4.

Las claves y los valores enumerados son el contrato (en inglés); la prosa interna puede estar en cualquier idioma. La guía campo por campo sale de `disensor guide`.

**Límite que declara el propio documento:** la máquina detecta el campo vacío y el marcador genérico, no la declaración falsa. Por eso el muestreo humano de PR cerrados sigue siendo parte del diseño.

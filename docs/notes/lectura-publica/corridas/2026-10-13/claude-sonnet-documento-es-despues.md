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
inicio: 2026-10-13T09:47:23-03:00
fin: 2026-10-13T09:47:42-03:00
duracion_s: 19
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 17966
cli_duration_api_ms: 15587
cli_num_turns: 1
cli_total_cost_usd: 0.1139254
cli_subtype: success
cli_usage: {"input_tokens": 2, "cache_creation_input_tokens": 22087, "cache_read_input_tokens": 1467, "output_tokens": 2528, "output_tokens_details": {"thinking_tokens": 155}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 22087, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 2528, "cache_read_input_tokens": 1467, "cache_creation_input_tokens": 22087, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 22087}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 0
```

## Respuesta

# Qué es disensor

Es una herramienta (paquete Python con CLI, más un gate de CI y una GitHub Action) que implementa el método del **desacuerdo controlado**: un modelo genera el código, un modelo de otra familia lo ataca, el generador verifica cada hallazgo, y el ciclo termina cuando cada hallazgo quedó resuelto, refutado con evidencia o escalado a un humano.

Lo que produce es un **registro versionado de la revisión**, la *declaración de residuo*. No es un sello de calidad ni un puntaje de cobertura. Lista lo que la revisión **no** pudo establecer y lo que queda para que lo mire una persona.

- **Un CLI** valida el registro.
- **Un gate de CI** frena el pull request si el cambio exige un registro y este falta, es genérico o no corresponde al cambio.

# Cómo es el archivo

Es un JSON en `.residue/<event_id>.json`, versionado en el repo junto al código. El esquema actual es `residue/v0.4`. Registra:

- **`event`**: repositorio, compuerta (`gate`), nivel de criticidad, y los commits base y head revisados.
- **`actors`**: el generador, los revisores (familia, modelo, independencia, confinamiento, hash de la consigna) y el árbitro humano.
- **`findings`**: cada hallazgo, con su `final_state` terminal (uno de seis: `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive`, `escalated_open`), contra qué se verificó (`repository`, `execution` o `external_source`) y cómo se verificó la corrección.
- **`residue.items`**: lo que queda para una persona. Cada ítem apunta a su hallazgo con `finding_ref`. Incluso una refutación con evidencia entra, para que alguien pueda no darla por buena.
- **`metrics`**: conteos que tienen que cerrar con los hallazgos.

# Ejemplo

Es un extracto del documento (evento real del PR #101 del propio repo). Un cambio generado por un modelo de Anthropic pasó por doce corridas de un revisor de OpenAI, que devolvieron 19 hallazgos: 18 se incorporaron y 1 se refutó con evidencia. Abrevié algunos textos largos con `…`.

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
        "prompt_hash": "sha256:3494df5e…6ee64a1c"
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
      "description": "Hipotesis del revisor: el recorrido evalua el rango desde el merge base hasta el segundo padre …",
      "location": "src/disensor/branch.py (_judge_merge); src/disensor/gate.py (resolve_context, evaluate_coverage)",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "repository",
        "detail": "Es el contrato del gate, no del panel: resolve_context toma head_oid como head del PR … "
      },
      "evidence": {
        "text": "gate.py, resolve_context: head_oid = gitctx.resolve_commit(head, repo_dir); status = gitctx.changed_status(mb, head_oid, repo_dir). …"
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
        "description": "El revisor sugirio que la cobertura mirara el arbol del commit de merge y no el head del PR; se refuto con el codigo del gate … El limite que senala … es del gate, no de este panel, y queda anotado."
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

En el ejemplo, `h15` es un hallazgo válido que se incorporó y se verificó con un test específico. `h16` fue una hipótesis del revisor que el generador refutó con evidencia del código. Aun así, esa refutación queda como ítem de residuo (`r4`) para que una persona pueda cuestionarla.

El documento aclara que las claves y los valores enumerados son el contrato (están en inglés), mientras que la prosa interna está en castellano. La guía campo por campo se obtiene con `disensor guide`.

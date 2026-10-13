# claude-sonnet, documento, en, despues

```yaml
modelo: claude-sonnet
modelo_pedido: sonnet
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
comando: claude -p --safe-mode --no-session-persistence --model sonnet --output-format json --tools ""
inicio: 2026-10-13T09:48:00-03:00
fin: 2026-10-13T09:48:22-03:00
duracion_s: 22
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 21208
cli_duration_api_ms: 18645
cli_num_turns: 1
cli_total_cost_usd: 0.1037374
cli_subtype: success
cli_usage: {"input_tokens": 2, "cache_creation_input_tokens": 18975, "cache_read_input_tokens": 1467, "output_tokens": 2754, "output_tokens_details": {"thinking_tokens": 208}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 18975, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 2754, "cache_read_input_tokens": 1467, "cache_creation_input_tokens": 18975, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 18975}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 0
```

## Respuesta

# Qué es disensor

disensor es la implementación de referencia de un artefacto llamado **residuo** (*residue*). Es un registro en JSON, versionado en el repositorio junto al código que juzga, de lo que pasó cuando un asistente de IA revisó el código escrito por otro. Viene de un método llamado **desacuerdo controlado**: un modelo genera, un modelo de otra familia ataca, el generador verifica cada hallazgo, y el ciclo termina cuando cada hallazgo fue resuelto, refutado con evidencia o escalado a un humano.

Lo importante es que el registro **lista residuo, no cobertura**. No es una insignia verde ni un puntaje. Dice qué hallazgos se verificaron y contra qué, cuáles se refutaron, qué no se pudo ejecutar y qué sigue descansando en el juicio de alguien. También dice quién generó el cambio, quién lo revisó y de qué familia de modelo, sobre qué commits, con qué consigna y quién aceptó el riesgo residual.

Alrededor del artefacto hay:
- Una **CLI** que lo valida (reglas R0 a R13).
- Un **gate de CI** (G1 a G9) que frena el pull request si el cambio exige un registro y este falta, es genérico o no corresponde al cambio.
- Un **informe HTML** del residuo.
- Un comando `disensor round` que orquesta la ronda con un revisor instalado en la máquina.

# Cómo se ve el archivo

Es un JSON en `.residue/<event_id>.json`, con el esquema `residue/v0.4`. Este es un extracto de un evento real del propio repositorio (PR #101). Un cambio generado por un modelo de Anthropic pasó por doce corridas de un revisor de OpenAI, que devolvió 19 hallazgos: 18 incorporados y 1 refutado con evidencia. Abrevié con `…` algunos textos largos; el resto son los valores del documento.

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
        "detail": "Comparadas las comprobaciones inline de _run_gate … con lo que aplicaba _judge_merge …"
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
        "detail": "Es el contrato del gate, no del panel: resolve_context toma head_oid como head del PR …"
      },
      "evidence": {
        "text": "gate.py, resolve_context: head_oid = gitctx.resolve_commit(head, repo_dir); … El rango juzgado es merge base a head del PR."
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
        "description": "El revisor sugirio que la cobertura mirara el arbol del commit de merge y no el head del PR; se refuto con el codigo del gate … y queda anotado."
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

## Cómo leerlo

- **`event`**: identifica el evento, el gate (`diff`), el nivel de criticidad y el par de commits revisados (base y head).
- **`actors`**: quién generó, quién revisó (familia, modelo, independencia, confinamiento, hash de la consigna) y si hubo árbitro humano.
- **`findings`**: cada hallazgo termina en uno de seis estados finales: `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive`, `escalated_open`.
  - `verification.against` indica contra qué se verificó: `repository`, `execution` o `external_source`.
  - `fix_verification` dice cómo se verificó la corrección de un hallazgo incorporado.
  - Una refutación verificable exige `evidence` con `text`, `link` o `hash`.
- **`residue.items`**: lo que queda para que una persona mire. Cada ítem apunta a su hallazgo con `finding_ref`. Un hallazgo refutado con evidencia se cierra y aun así entra al residuo, para que alguien pueda no aceptar la refutación sin más.
- **`metrics.counts`**: conteos que tienen que sumar.

Las claves y los valores enumerados son el contrato y se leen igual en cualquier idioma. La prosa interna está en español porque quienes mantienen el repositorio escriben en español.

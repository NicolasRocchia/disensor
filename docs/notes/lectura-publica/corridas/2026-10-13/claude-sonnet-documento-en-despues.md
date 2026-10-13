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
inicio: 2026-10-13T10:01:35-03:00
fin: 2026-10-13T10:01:59-03:00
duracion_s: 23
confinamiento: herramientas apagadas por construcción (--tools "")
cli_duration_ms: 22256
cli_duration_api_ms: 20349
cli_num_turns: 1
cli_total_cost_usd: 0.10812739999999998
cli_subtype: success
cli_usage: {"input_tokens": 2, "cache_creation_input_tokens": 18430, "cache_read_input_tokens": 1467, "output_tokens": 3411, "output_tokens_details": {"thinking_tokens": 179}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 18430, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 3411, "cache_read_input_tokens": 1467, "cache_creation_input_tokens": 18430, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 18430}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

# Qué es disensor

disensor es la implementación de referencia de un artefacto llamado **residue** (residuo). Es una declaración JSON versionada en el repositorio, junto al código que juzga, que registra lo que ocurrió en una revisión adversarial de código generado por IA.

Se basa en el método del **desacuerdo controlado**:
- Un modelo genera el cambio.
- Un modelo de otra familia lo ataca.
- El generador verifica cada hallazgo.
- El ciclo termina cuando cada hallazgo fue resuelto, refutado con evidencia o escalado a una persona.

El registro no es un sello de calidad ni una métrica de cobertura. Lista el **residuo**: qué hallazgos se verificaron y contra qué, cuáles se refutaron, qué no se pudo ejecutar y qué queda librado al criterio de alguien. También dice quién generó el cambio, quién lo revisó y de qué familia de modelos, sobre qué commits, con qué consigna y quién aceptó el riesgo residual.

Además del artefacto, el paquete incluye:
- Una CLI que lo valida (reglas R0 a R13).
- Un gate de CI (G1 a G9) que frena el pull request si el cambio exige un registro y este falta, es genérico o no corresponde al cambio.
- Un informe HTML del residuo.
- Una orquestación opcional de la ronda (`disensor round`).

# Cómo se ve el artefacto

Este es un extracto de un evento real del propio repositorio (`.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json`, la declaración del PR #101). Un cambio generado por un modelo de Anthropic pasó por doce corridas de un revisor de OpenAI, que devolvió 19 hallazgos: 18 se incorporaron y 1 se refutó con evidencia. El extracto muestra la entrada del revisor de una de esas corridas, dos de los hallazgos y el ítem de residuo que dejó uno de ellos. Las claves y los valores enumerados son el contrato; la prosa está en español porque quienes mantienen el repositorio escriben en ese idioma.

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
          "verified": true,
          "verification_method": "clean_git_status"
        },
        "hardening": "verified",
        "prompt_hash": "sha256:3494df5ebd20cc793ff9c5a214a2e715758e69c41bbc9e09b70f7d3064ee6a1c"
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
      "description": "El recorrido validaba el esquema y aplicaba G5, G6 y G7, pero no las comprobaciones por artefacto del gate: una declaracion de nivel C en un repositorio de nivel B (G2), un id no canonico o un archivo con otro nombre (G8), o un nivel A sin confinamiento admitido (G4) cubrian igual. Las comprobaciones del gate se extrajeron a gate.judge_artifact, que _run_gate y el recorrido comparten; el recorrido no aplica G9 porque una version anterior del esquema era la vigente cuando un merge viejo ocurrio, y lo dice. Las declaraciones que el PR agrego se juzgan como en el gate, y una mutacion de evidencia o un historico ilegible tambien lo dejan sin cobertura, como al PR.",
      "location": "src/disensor/gate.py (judge_artifact); src/disensor/branch.py (_judge_merge, _historical_ids)",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Comparadas las comprobaciones inline de _run_gate (G9, G8, G2, G3, G4, G5) con lo que aplicaba _judge_merge; la extraccion conserva el orden y los textos, y la suite del gate sigue en verde."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_branch.py::test_a_declaration_the_gate_rejects_on_its_own_checks_covers_nothing, que corre run_gate sobre el mismo PR y afirma que devuelve 1"
      }
    },
    {
      "id": "h16",
      "origin": "r8",
      "severity": "info",
      "title": "La resolucion de un merge con conflictos no entra en la cobertura",
      "description": "Hipotesis del revisor: el recorrido evalua el rango desde el merge base hasta el segundo padre y no el arbol del commit de merge, asi que codigo introducido al resolver un conflicto puede diferir del head revisado y el merge figurar cubierto.",
      "location": "src/disensor/branch.py (_judge_merge); src/disensor/gate.py (resolve_context, evaluate_coverage)",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "repository",
        "detail": "Es el contrato del gate, no del panel: resolve_context toma head_oid como head del PR y evaluate_coverage y check_range_membership juzgan ese head; el gate nunca ve el arbol del merge que la plataforma crea al integrar. El panel replica exactamente lo que el gate juzgo. Lo que el revisor senala es un limite del gate que existe desde G6, y no cambia con este PR."
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
        "description": "El revisor sugirio que la cobertura mirara el arbol del commit de merge y no el head del PR; se refuto con el codigo del gate, que juzga el head. El limite que senala (lo que se escribe al resolver un conflicto no pasa por ninguna revision) es del gate, no de este panel, y queda anotado."
      }
    ]
  },
  "metrics": {
    "counts": {
      "total_findings": 19,
      "valid": {
        "incorporated": 18,
        "debt_recorded": 0,
        "owner_decision": 0
      },
      "false_positives": {
        "refuted_verifiable": 1,
        "refuted_interpretive": 0
      },
      "escalated_open": 0
    }
  }
}
```

## Cómo leerlo

- **`event`**: identifica la revisión (gate `diff`, nivel de criticidad `B`) y el par de commits revisados (`base_commit` y `head_commit`).
- **`actors`**: quién generó el cambio (`anthropic`), quién lo revisó (`openai`, con `independence: cross_family`), cómo se confinó al revisor, el hash de la consigna adversarial (`prompt_hash`) y si hubo un árbitro humano (obligatorio, regla R0).
- **`findings`**: cada hallazgo termina en uno de seis estados finales (`final_state`): `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive` o `escalated_open`.
  - `verification.against` indica contra qué se verificó el hallazgo: `repository`, `execution` o `external_source`.
  - `fix_verification` indica cómo se verificó la corrección de un hallazgo incorporado.
  - Una refutación verificable exige evidencia material (`text`, `link` o `hash`), como en `h16`.
- **`residue.items`**: lo que queda para que una persona mire. Cada ítem apunta a su hallazgo mediante `finding_ref`. Un hallazgo refutado con evidencia se cierra pero igual entra al residuo, para que alguien pueda no aceptar la refutación sin más.
- **`metrics.counts`**: conteos que deben sumar (19 en total: 18 incorporados y 1 refutado verificable).

La guía campo por campo está en `disensor guide`.

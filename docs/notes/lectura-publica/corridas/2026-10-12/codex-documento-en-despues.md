# codex, documento, en, despues

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
modo: documento
idioma: en
estado: despues
pregunta: What is disensor and what does the file it generates look like? Show an example of the artifact.
documento: README.md
commit: 96e12ae
sha256: 2ded6b061429bd9605ab139e78b6ce8040fd44d8c8c70b5508ec88d40596458d
bytes: 50741
prompt_sha256: 1480ae919bd016d6d0c86cd791000056bb8da56603faed091e3caaf491669962
comando: codex exec -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o C:\Users\Usuario\AppData\Local\Temp\lectura-publica-3_i18g_h\respuesta.md
inicio: 2026-10-12T14:34:21-03:00
fin: 2026-10-12T14:34:56-03:00
duracion_s: 34
cli_exit_code: 0
cli_log_lineas: 136
```

## Respuesta

Disensor is a CLI and CI control for recording the outcome of adversarial AI code review.

Instead of producing an “approved” badge, it creates a versioned JSON artifact—called a **residue declaration**—next to the code. The declaration records:

- Who generated and reviewed the change, including model families.
- Which commits and adversarial prompt were reviewed.
- Every finding and its terminal state.
- What each finding was verified against.
- How incorporated fixes were tested.
- Refutations and their evidence.
- Risks, execution gaps, debts, or escalations left for human attention.
- Aggregate finding counts.

The method is “controlled disagreement”: one model generates, another model family attacks the work, the generator verifies every finding, and unresolved or disputed points remain explicitly recorded for a human. A validator checks the artifact, while the CI gate can reject a pull request if its required declaration is absent, generic, stale, invalid, or does not cover the final change.

Artifacts use the `residue/v0.4` schema and normally live at:

```text
.residue/<event_id>.json
```

Here is a shortened representative artifact:

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
      "title": "Una declaración rechazada por el gate daba por cubierto el merge",
      "description": "El revisor detectó que el recorrido no aplicaba todas las comprobaciones del gate.",
      "location": "src/disensor/gate.py; src/disensor/branch.py",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Se compararon las comprobaciones del gate con las del recorrido."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_branch.py::test_a_declaration_the_gate_rejects_on_its_own_checks_covers_nothing"
      }
    },
    {
      "id": "h16",
      "origin": "r8",
      "severity": "info",
      "title": "La resolución de conflictos no entra en la cobertura",
      "description": "El revisor cuestionó qué árbol juzga el gate.",
      "location": "src/disensor/branch.py; src/disensor/gate.py",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "repository",
        "detail": "El código confirma que el contrato juzga el head del PR."
      },
      "evidence": {
        "text": "resolve_context toma head_oid como head del PR."
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
        "description": "La hipótesis fue refutada con el código, pero el límite señalado queda registrado."
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

Each finding must end in one of six states:

```text
incorporated
debt_recorded
owner_decision
refuted_verifiable
refuted_interpretive
escalated_open
```

Crucially, even an evidence-backed refutation can remain in `residue.items`, allowing a human to inspect the disagreement instead of treating the generator’s rebuttal as automatically correct.

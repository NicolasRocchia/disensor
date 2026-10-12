# codex, documento, en, antes

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
modo: documento
idioma: en
estado: antes
pregunta: What is disensor and what does the file it generates look like? Show an example of the artifact.
documento: README.md
commit: de14e5c
sha256: 1a5723141ea0f2f6db16ee496f8fe4086e801077e737bc4df1ead52d68d0093c
bytes: 44409
prompt_sha256: b7fb9d47368aa45b332bc481c5fcdf2676a209f6e4106df47bf95c31a4fda8af
comando: codex exec -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o C:\Users\Usuario\AppData\Local\Temp\lectura-publica-as3q55bq\respuesta.md
inicio: 2026-10-12T14:34:04-03:00
fin: 2026-10-12T14:34:21-03:00
duracion_s: 17
cli_exit_code: 0
cli_log_lineas: 131
```

## Respuesta

`disensor` is a CLI and CI control for recording the outcome of an adversarial AI code review.

Its method is “controlled disagreement”:

1. One model generates a change.
2. A model from another family attacks it.
3. The generator verifies every finding.
4. Each finding is incorporated, refuted with evidence, recorded as debt, accepted by an owner, or escalated.
5. The remaining uncertainty is saved as a versioned JSON “residue declaration” in `.residue/`, alongside the code it evaluates.

The artifact is deliberately not an approval badge or coverage score. It records:

- Who generated and reviewed the change, including model families and independence.
- The exact commits and adversarial prompt involved.
- Every finding and its terminal state.
- How each finding was verified.
- Whether incorporated fixes were tested.
- Unresolved risks, execution gaps, debts, and human decisions.
- The human arbiter who accepts the residual risk.
- Whether reviewer confinement was verified.

The filename is `<event_id>.json`, where `event_id` is a canonical UUID. New declarations use schema `residue/v0.4`. The exact authoritative structure lives in `spec/residue.schema.json`; `disensor new` generates a prefilled template and `disensor validate` checks it.

The supplied document does not include a complete example from `spec/examples/`, so the following is an illustrative, abbreviated representation—not a guaranteed schema-valid artifact:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "7a94d2bc-31c0-4d80-944e-bab3c4f30650",
    "gate": "diff",
    "criticality_level": "B",
    "repository": "example/project",
    "pr": "PR-42",
    "base_commit": "4b3c2d1",
    "reviewed_commit": "9f8e7d6",
    "prompt_hash": "sha256:0123456789abcdef..."
  },
  "actors": {
    "generator": {
      "family": "anthropic",
      "model": "generator-model"
    },
    "reviewers": [
      {
        "id": "reviewer-1",
        "family": "openai",
        "model": "reviewer-model",
        "independence": "cross_family",
        "hardening": "verified"
      }
    ],
    "human_arbiter": {
      "id": "maintainer"
    }
  },
  "findings": [
    {
      "id": "F-1",
      "reviewer": "reviewer-1",
      "description": "A concurrent update could overwrite a newer value.",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Verified against the transaction implementation."
      },
      "fix_verification": {
        "method": "specific_test",
        "detail": "The concurrent-update regression test passed."
      }
    },
    {
      "id": "F-2",
      "reviewer": "reviewer-1",
      "description": "The authorization check might permit cross-owner access.",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "execution",
        "detail": "Ownership tests reject access by a different user."
      },
      "evidence": {
        "text": "The authorization test suite passed, including the cross-owner case."
      }
    },
    {
      "id": "F-3",
      "reviewer": "reviewer-1",
      "description": "Production behavior under provider timeout was not exercised.",
      "final_state": "escalated_open",
      "verification": {
        "against": "none",
        "detail": "The external provider was unavailable in the test environment."
      }
    }
  ],
  "residue": {
    "items": [
      {
        "id": "R-1",
        "class": "execution_gap",
        "finding": "F-3",
        "description": "Provider-timeout behavior still requires human attention."
      }
    ],
    "declaration": "One execution gap remains; no other unresolved residue was identified."
  },
  "metrics": {
    "counts": {
      "total": 3,
      "incorporated": 1,
      "refuted_verifiable": 1,
      "escalated_open": 1
    }
  },
  "confinement": {
    "mode": "read_only_by_instruction",
    "verified": true
  },
  "lead_acceptance": "The maintainer accepts the declared residual risk."
}
```

In practice, the normal workflow is:

```bash
disensor new --gate diff --level B
disensor validate .residue/<event-id>.json
disensor gate --no-comment --base main --head HEAD
```

The resulting JSON is committed as append-only review evidence. CI can reject a pull request when the declaration is missing, generic, stale, inconsistent with the changed code, or insufficient for the repository’s criticality policy.

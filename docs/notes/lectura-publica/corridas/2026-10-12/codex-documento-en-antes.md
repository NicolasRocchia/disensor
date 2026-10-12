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
comando: codex exec --json -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o C:\Users\Usuario\AppData\Local\Temp\lectura-publica-vhhfd3x9\respuesta.md
inicio: 2026-10-12T14:57:39-03:00
fin: 2026-10-12T14:57:58-03:00
duracion_s: 19
confinamiento: por instrucción; ver llamadas_a_herramientas
cli_eventos: {"item.completed/agent_message": 1, "thread.started": 1, "turn.completed": 1, "turn.started": 1}
cli_llamadas_a_herramientas: 0
```

## Respuesta

`disensor` is a CLI and CI control for recording the outcome of an adversarial AI code review.

Instead of producing an “approved” badge, it creates a versioned JSON declaration in `.residue/`, beside the code being judged. The declaration records:

- Who generated and reviewed the change, including model families and reviewer independence.
- Which commits and adversarial prompt were reviewed.
- Every finding and its terminal state: incorporated, refuted, recorded as debt, accepted by the owner, or escalated.
- How each finding was verified and what evidence supports a refutation.
- What remains for human attention: unresolved escalation, principal disagreement, execution gaps, reviewer correlation, or reviewer-hardening gaps.
- The human arbiter and acceptance of residual risk.

The current schema is `residue/v0.4`. Files are named `<event_id>.json`, where `event_id` is a canonical UUID. The following is a simplified illustrative artifact based on the documented fields:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "8cdb99d1-bc55-4fd5-9aea-a3e213242fa7",
    "gate": "diff",
    "criticality_level": "B",
    "repository": "example/project",
    "base_commit": "58cf849e0ed1cbb2e39db15ba62fe7325feac387",
    "reviewed_commit": "ac142fd431a2b44137506dbf41325228b2ff9bf1",
    "prompt_hash": "sha256:71e5d92eac9b84a606ff56b19d1c656415bcf3a48cb57e86521e70f77962c390"
  },
  "profile": "full",
  "actors": {
    "generator": {
      "id": "implementation-agent",
      "family": "anthropic"
    },
    "reviewers": [
      {
        "id": "adversarial-reviewer",
        "family": "openai",
        "model": "reviewer-model",
        "independence": "cross_family",
        "hardening": "verified"
      }
    ],
    "human_arbiter": {
      "id": "project-owner"
    }
  },
  "findings": [
    {
      "id": "F-001",
      "reviewer": "adversarial-reviewer",
      "description": "A concurrent update could overwrite a newer value.",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "The affected update path and transaction boundary were inspected."
      },
      "fix_verification": {
        "method": "specific_test",
        "detail": "The concurrency regression test passes."
      }
    },
    {
      "id": "F-002",
      "reviewer": "adversarial-reviewer",
      "description": "The reviewer suspected that an unauthenticated caller could reach the endpoint.",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "execution",
        "detail": "The endpoint was exercised without credentials."
      },
      "evidence": {
        "text": "The request returned the expected authentication failure.",
        "hash": "sha256:fd17d41b084985055cc37d2a51d85a297d6d6413ec8791735b625d92b4e75237"
      }
    },
    {
      "id": "F-003",
      "reviewer": "adversarial-reviewer",
      "description": "The acceptable timeout behavior is a product decision.",
      "final_state": "owner_decision",
      "verification": {
        "against": "repository",
        "detail": "The configured timeout and calling path were inspected."
      },
      "lead_acceptance": "The owner accepts the documented timeout behavior."
    }
  ],
  "residue": {
    "items": [
      {
        "id": "R-001",
        "class": "principal_refutation",
        "finding_id": "F-003",
        "description": "The timeout behavior ultimately rests on the owner's judgement."
      }
    ],
    "declared_absence": false,
    "declaration": "One product-level judgement remains for human scrutiny."
  },
  "metrics": {
    "counts": {
      "total": 3,
      "incorporated": 1,
      "refuted_verifiable": 1,
      "owner_decision": 1
    }
  },
  "confinement": {
    "mode": "read_only_by_instruction",
    "verified": true
  }
}
```

This example demonstrates the artifact’s intent and general shape; the authoritative field requirements are defined by `spec/residue.schema.json`. `disensor validate` checks the schema and rules R0–R13, while `disensor gate` determines whether the declaration properly covers the pull request.

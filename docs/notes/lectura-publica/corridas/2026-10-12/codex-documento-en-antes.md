# codex, documento, en, antes

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
modo: documento
idioma: en
estado: antes
repeticion: 1
pregunta: What is disensor and what does the file it generates look like? Show an example of the artifact.
documento: README.md
commit: de14e5c
sha256: 1a5723141ea0f2f6db16ee496f8fe4086e801077e737bc4df1ead52d68d0093c
bytes: 44409
prompt_sha256: b7fb9d47368aa45b332bc481c5fcdf2676a209f6e4106df47bf95c31a4fda8af
comando: codex exec --json -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o <archivo>
inicio: 2026-10-12T23:43:10-03:00
fin: 2026-10-12T23:43:31-03:00
duracion_s: 20
confinamiento: por instrucción; ver llamadas_a_herramientas
cli_eventos: {"item.completed/agent_message": 1, "thread.started": 1, "turn.completed": 1, "turn.started": 1}
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

`disensor` is a CLI and artifact format for recording the outcome of an adversarial AI code review.

The workflow is:

1. One model generates a change.
2. A model from another family attacks it, looking for false assumptions, risks, and edge cases.
3. The generator verifies each finding against the repository, an execution, or an external source.
4. Every finding ends in a terminal state: incorporated, recorded as debt, accepted by the owner, refuted with evidence, refuted interpretively, or escalated.
5. The remaining uncertainty is committed beside the code as a versioned JSON declaration in `.residue/`.

It is deliberately not an approval badge or coverage score. The artifact records what the review could and could not establish, including:

- Who generated and reviewed the change, and their model families.
- The commits and review gate involved.
- The hash of the adversarial brief.
- Each finding and its disposition.
- Evidence and verification performed.
- Fix verification for incorporated findings.
- Execution gaps, unresolved escalations, and other residue.
- The human responsible for accepting residual risk.
- Whether reviewer confinement was verified.

The generated filename is `<event_id>.json`, where `event_id` is a canonical UUID. New declarations use the `residue/v0.4` schema.

A simplified illustrative artifact looks like this:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "6d68c839-75d5-4a77-b3fe-a6713e7a90e2",
    "gate": "diff",
    "criticality_level": "B",
    "repository": "acme/payments-api",
    "base_commit": "0b11c5fb723a20f62c45de42a12482cce898b537",
    "reviewed_commit": "f6241a451390f6a90cd7d90fa612808890ffa215",
    "pr": "PR-184"
  },
  "actors": {
    "generator": {
      "id": "primary-agent",
      "family": "anthropic",
      "model": "generator-model"
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
      "id": "nicolas"
    }
  },
  "prompt_hash": "sha256:8e941b7fb5d13ac2b9b18795432e3ac73816e6f5ae9a7130637183cba3f02dad",
  "confinement": {
    "mode": "read_only_by_instruction",
    "verified": true
  },
  "findings": [
    {
      "id": "F-001",
      "reviewer": "adversarial-reviewer",
      "text": "The ownership check occurs after the record is loaded.",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Verified against the request handler and authorization service."
      },
      "fix_verification": {
        "method": "specific_test",
        "detail": "The cross-user access test now returns 403."
      }
    },
    {
      "id": "F-002",
      "reviewer": "adversarial-reviewer",
      "text": "Concurrent updates might overwrite one another.",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "execution",
        "detail": "The concurrency test confirmed optimistic-lock rejection."
      },
      "evidence": {
        "text": "The second update failed with the expected version conflict."
      }
    },
    {
      "id": "F-003",
      "reviewer": "adversarial-reviewer",
      "text": "Retry behavior may need operational monitoring.",
      "final_state": "debt_recorded",
      "verification": {
        "against": "repository",
        "detail": "No retry-specific alert exists."
      },
      "debt_id": "OPS-219"
    }
  ],
  "residue": {
    "items": [
      {
        "id": "R-001",
        "class": "execution_gap",
        "finding": "F-003",
        "description": "Retry behavior was not tested under a production-equivalent load."
      }
    ],
    "declared_absence": false,
    "declaration": "One execution gap remains and is tracked as OPS-219."
  },
  "metrics": {
    "counts": {
      "total": 3,
      "incorporated": 1,
      "debt_recorded": 1,
      "refuted_verifiable": 1
    }
  },
  "lead_acceptance": "The remaining execution gap is accepted for this change."
}
```

That example demonstrates the artifact’s intent and approximate structure; an actual declaration must follow the complete `residue/v0.4` JSON Schema and pass `disensor validate`. A review that leaves nothing unresolved still produces an artifact, with an explicit, concrete declaration of absence rather than a generic phrase such as “no residue.”

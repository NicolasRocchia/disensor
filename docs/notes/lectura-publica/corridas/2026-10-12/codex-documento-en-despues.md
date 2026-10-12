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
comando: codex exec --json -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o <archivo>
inicio: 2026-10-12T14:57:58-03:00
fin: 2026-10-12T14:58:31-03:00
duracion_s: 32
confinamiento: por instrucción; ver llamadas_a_herramientas
cli_eventos: {"item.completed/agent_message": 1, "thread.started": 1, "turn.completed": 1, "turn.started": 1}
cli_llamadas_a_herramientas: 0
```

## Respuesta

Disensor is a CLI and CI control for recording the outcome of adversarial AI code review.

Instead of producing an “approved” badge, it generates a versioned JSON artifact—called a residue declaration—stored in `.residue/` alongside the code. It records:

- Who generated and reviewed the change, including model families.
- Which commits and adversarial prompt were reviewed.
- Every finding and its terminal state.
- What each finding was verified against.
- How incorporated fixes were tested.
- Refutations and their evidence.
- Remaining risks, debts, execution gaps, or decisions requiring human attention.
- Aggregate finding counts.

The CLI validates the artifact against its schema and coherence rules. Its CI gate can reject a pull request when a required declaration is missing, generic, stale, inconsistent, or does not cover the final change.

A simplified artifact looks like this:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "27089d19-ee91-4c6c-b517-63b9627969e0",
    "created_at": "2026-09-29T10:21:11-03:00",
    "repository": "github.com/example/project",
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
        "reviewer_id": "r1",
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
      "id": "h1",
      "origin": "r1",
      "severity": "major",
      "title": "The reviewed path could be accepted without all gate checks",
      "description": "The reviewer found that one code path did not apply the same checks as the CI gate.",
      "location": "src/example/gate.py",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Compared both implementations and confirmed the missing checks."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_gate.py::test_rejected_artifact_provides_no_coverage"
      }
    },
    {
      "id": "h2",
      "origin": "r1",
      "severity": "info",
      "title": "Merge-conflict resolutions may not enter coverage",
      "description": "The reviewer suggested evaluating the merge commit rather than the reviewed PR head.",
      "location": "src/example/gate.py",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "repository",
        "detail": "The gate contract explicitly evaluates the PR head."
      },
      "evidence": {
        "text": "The range is calculated from the merge base to the PR head."
      }
    }
  ],
  "residue": {
    "items": [
      {
        "id": "r1",
        "class": "principal_refutation",
        "finding_ref": "h2",
        "refutation_type": "verifiable",
        "requires_human_attention": false,
        "description": "The finding was refuted from the gate implementation, but the underlying protocol limitation remains recorded."
      }
    ]
  },
  "metrics": {
    "counts": {
      "total_findings": 2,
      "valid": {
        "incorporated": 1,
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

Each finding must end in one of six states: `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive`, or `escalated_open`. Even an evidence-backed refutation remains represented in `residue`, allowing a human to examine rather than automatically trust it.

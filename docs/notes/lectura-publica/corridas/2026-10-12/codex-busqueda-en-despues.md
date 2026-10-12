# codex, busqueda, en, despues

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
modo: busqueda
idioma: en
estado: despues
pregunta: What is disensor and what does the file it generates look like? Show an example of the artifact.
documento: web
prompt_sha256: 98fdba38ac47cddd691a28f7bff5cf8a228c172aa436f67738e2aa43d89bee79
comando: codex --search exec -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o C:\Users\Usuario\AppData\Local\Temp\lectura-publica-ikk6ffvc\respuesta.md
inicio: 2026-10-12T14:38:54-03:00
fin: 2026-10-12T14:39:38-03:00
duracion_s: 44
cli_exit_code: 0
cli_log_lineas: 110
```

## Respuesta

`disensor` is a Python CLI for recording the outcome of an adversarial AI review. Typically, one model produces a plan or code and a model from another family attacks it. The original agent verifies every finding, and `disensor` preserves how each finding ended—fixed, recorded as debt, accepted by the owner, refuted, or left open. It is best understood as a notary and CI gate, not as the reviewer itself. [Official explanation](https://disensor.dev/es/how-it-works/) · [GitHub repository](https://github.com/NicolasRocchia/disensor)

The command:

```powershell
disensor new --gate diff --level B
```

creates a JSON template under `.residue/`. Git-derived information such as repository, commits, timestamp, and event UUID is prefilled; the remaining markers must be completed. Then:

```powershell
disensor validate .residue/<event-id>.json
disensor gate
```

validate the individual declaration and enforce repository/PR policy respectively. The Spanish aliases `nuevo`, `validar`, `--compuerta`, and `--nivel` remain supported. [Filling guide](https://disensor.dev/tool/guide/) · [PyPI documentation](https://pypi.org/project/disensor/)

A completed artifact contains:

- `event`: what was reviewed and the exact commits involved.
- `actors`: generator, reviewers, model families, independence and confinement.
- `findings`: each reported problem and its terminal state.
- `residue`: matters still requiring human judgment, missing execution, or scrutiny of a refutation.
- `metrics`: counts that must agree with the findings.
- `prompt_hash`: SHA-256 of the adversarial instructions, allowing their exact bytes to be compared later—though it does not prove they were actually sent. [Artifact walkthrough](https://disensor.dev/es/how-it-works/#el-archivo-que-queda-por-dentro)

Here is a shortened representative example. The official fixture is longer because it demonstrates several terminal states:

```json
{
  "schema": "residue/v0.4",
  "profile": "full",
  "event": {
    "event_id": "7c8d9e0f-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
    "created_at": "2026-07-15T18:40:00-03:00",
    "repository": "https://github.com/example/project",
    "pr": "https://github.com/example/project/pull/214",
    "base_commit": "c0ffee1",
    "head_commit": "beef042",
    "gate": "diff",
    "criticality_level": "B",
    "abbreviated_path": {
      "used": false
    }
  },
  "actors": {
    "generator": {
      "family": "anthropic",
      "model": "claude-code"
    },
    "reviewers": [
      {
        "reviewer_id": "reviewer-1",
        "family": "openai",
        "model": "gpt-5.4",
        "prompt_hash": "sha256:1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d",
        "confinement": {
          "mode": "read_only_by_instruction",
          "verified": true,
          "verification_method": "clean_git_status"
        },
        "independence": "cross_family"
      }
    ],
    "human_arbiter": {
      "present": true,
      "id": "feature-owner"
    }
  },
  "findings": [
    {
      "id": "finding-1",
      "origin": "reviewer-1",
      "severity": "major",
      "title": "Resource is not released on the error path",
      "description": "An intermediate failure leaves the writer acquired.",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Confirmed in the reviewed diff."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_export_failure_releases_writer"
      }
    }
  ],
  "residue": {
    "items": []
  },
  "metrics": {
    "counts": {
      "total_findings": 1,
      "valid": {
        "incorporated": 1,
        "debt_recorded": 0,
        "owner_decision": 0
      },
      "false_positives": {
        "refuted_verifiable": 0,
        "refuted_interpretive": 0
      },
      "escalated_open": 0
    },
    "extra_time_sec": 480
  }
}
```

The repository provides a [complete valid diff-gate artifact](https://github.com/NicolasRocchia/disensor/blob/main/spec/examples/example_2_diff_gate.json), along with plan-gate and minimized-profile examples in [`spec/examples`](https://github.com/NicolasRocchia/disensor/tree/main/spec/examples). The minimized profile removes selected free-text fields to reduce information leakage, but the documentation explicitly warns that it is surface reduction—not a guarantee that no sensitive text can escape. [Project documentation](https://github.com/NicolasRocchia/disensor#what-it-does-not-do)

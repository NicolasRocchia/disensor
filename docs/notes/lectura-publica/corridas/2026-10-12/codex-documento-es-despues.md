# codex, documento, es, despues

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
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
comando: codex exec --json -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o <archivo>
inicio: 2026-10-12T23:42:31-03:00
fin: 2026-10-12T23:43:10-03:00
duracion_s: 38
confinamiento: por instrucción; ver llamadas_a_herramientas
cli_eventos: {"item.completed/agent_message": 1, "thread.started": 1, "turn.completed": 1, "turn.started": 1}
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

**disensor** es una herramienta para registrar y hacer cumplir el resultado de una revisión adversarial de código entre modelos de IA.

Su método es el **desacuerdo controlado**:

1. Un modelo genera el cambio.
2. Otro modelo —idealmente de otra familia— lo ataca buscando errores, riesgos y supuestos falsos.
3. El generador verifica cada hallazgo.
4. Cada hallazgo se incorpora, se refuta con evidencia, se convierte en deuda o decisión del dueño, o se escala.
5. El resultado queda versionado en el repositorio como una declaración JSON de **residuo**.

El artefacto no certifica que el código sea bueno ni funciona como sello de aprobación. Registra qué ocurrió en la revisión y, especialmente, qué quedó dependiendo de atención o juicio humano.

El archivo se guarda normalmente como:

```text
.residue/<event_id>.json
```

Su estructura incluye:

- `schema`: versión del contrato, actualmente `residue/v0.4`.
- `event`: identificador, fecha, repositorio, compuerta, criticidad y commits revisados.
- `actors`: modelo generador, revisores, independencia entre ellos, confinamiento y árbitro humano.
- `findings`: hallazgos y su estado terminal.
- `residue`: cuestiones que siguen mereciendo atención humana, incluidas las refutaciones.
- `metrics`: conteos coherentes con los hallazgos declarados.

Ejemplo abreviado:

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
      "title": "Una comprobación del gate no estaba cubierta",
      "description": "El revisor detectó que faltaba aplicar parte de las comprobaciones del gate.",
      "location": "src/disensor/gate.py",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Se compararon las comprobaciones del gate con la implementación."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_branch.py::test_rejected_declaration_covers_nothing"
      }
    },
    {
      "id": "h16",
      "origin": "r8",
      "severity": "info",
      "title": "La resolución de conflictos no entra en la cobertura",
      "description": "El revisor planteó que el árbol del merge podía diferir del head revisado.",
      "location": "src/disensor/branch.py",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "repository",
        "detail": "Se verificó que el contrato del gate juzga el head del PR."
      },
      "evidence": {
        "text": "resolve_context toma el head del PR y evalúa el rango entre merge base y head."
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
        "description": "La hipótesis fue refutada contra el código, pero el límite señalado queda registrado."
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

Cada hallazgo termina en uno de seis estados:

```text
incorporated
debt_recorded
owner_decision
refuted_verifiable
refuted_interpretive
escalated_open
```

Incluso una refutación verificable puede aparecer en `residue`, de modo que una persona pueda revisar la evidencia y no tenga que aceptar automáticamente la conclusión del modelo. El CLI valida el archivo contra el esquema y las reglas de coherencia; luego el gate de CI puede bloquear un PR si falta la declaración requerida, es genérica, no coincide con los commits o no cubre el cambio final.

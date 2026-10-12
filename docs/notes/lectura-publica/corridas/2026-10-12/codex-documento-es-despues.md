# codex, documento, es, despues

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
modo: documento
idioma: es
estado: despues
pregunta: ¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.
documento: README.es.md
commit: 96e12ae
sha256: 745785e7f888beb206a7d6e84967d7d3be56c52ea6d99dd273488a5c9d283bc8
bytes: 52212
prompt_sha256: f3248622878cee70fab342d2d0f0243d896a86bd0633e7be187ab9abe934a9ec
comando: codex exec -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o C:\Users\Usuario\AppData\Local\Temp\lectura-publica-plu0l5sk\respuesta.md
inicio: 2026-10-12T14:33:45-03:00
fin: 2026-10-12T14:34:04-03:00
duracion_s: 18
cli_exit_code: 0
cli_log_lineas: 137
```

## Respuesta

**disensor** es una herramienta para registrar, validar y hacer cumplir el resultado de una revisión adversarial de código entre modelos.

El método es el **desacuerdo controlado**:

1. Un modelo genera el cambio.
2. Otro modelo —idealmente de otra familia— lo ataca buscando errores, supuestos y casos borde.
3. El generador verifica cada hallazgo.
4. Cada hallazgo termina incorporado, refutado con evidencia, convertido en deuda, aceptado por el dueño del riesgo o escalado.
5. El resultado se guarda como un JSON versionado dentro del repositorio, normalmente en `.residue/<event_id>.json`.

Ese archivo se llama **declaración de residuo**. No certifica que el código sea bueno ni funciona como sello de aprobación: documenta qué ocurrió en la revisión y, especialmente, qué todavía requiere atención humana.

El artefacto registra:

- El esquema utilizado, actualmente `residue/v0.4`.
- La compuerta revisada (`plan`, `diff` o `architecture`) y los commits exactos.
- El modelo generador y los revisores, incluidas sus familias e independencia.
- El hash de la consigna adversarial.
- Cada hallazgo, su severidad y su estado terminal.
- Contra qué se verificó cada hallazgo.
- Cómo se comprobó la corrección de los hallazgos incorporados.
- Las refutaciones, escalados y otros residuos que una persona debería examinar.
- Métricas cuyos conteos deben coincidir con los hallazgos declarados.

Un ejemplo reducido sería:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "27089d19-ee91-4c6c-b517-63b9627969e0",
    "created_at": "2026-09-29T10:21:11-03:00",
    "repository": "github.com/ejemplo/proyecto",
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
      "title": "La validación omitía un caso límite",
      "description": "El revisor detectó que una entrada inválida podía atravesar la validación.",
      "location": "src/validation.py",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Se confirmó el flujo inspeccionando la validación y sus consumidores."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_validation.py::test_rejects_invalid_input"
      }
    },
    {
      "id": "h2",
      "origin": "r1",
      "severity": "info",
      "title": "Posible comportamiento incorrecto en un merge",
      "description": "El revisor planteó que el cálculo podía mirar el commit equivocado.",
      "location": "src/gate.py",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "repository",
        "detail": "El código resuelve explícitamente el head del cambio."
      },
      "evidence": {
        "text": "resolve_context obtiene y usa head_oid para calcular el rango."
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
        "description": "La hipótesis fue refutada contra el código, pero queda registrada para que una persona pueda cuestionar esa refutación."
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

Los seis estados terminales posibles de un hallazgo son:

- `incorporated`
- `debt_recorded`
- `owner_decision`
- `refuted_verifiable`
- `refuted_interpretive`
- `escalated_open`

El CLI puede crear la plantilla con `disensor new`, validarla con `disensor validate` y aplicar la política del repositorio mediante `disensor gate`. El gate no ejecuta modelos: examina el JSON ya versionado y bloquea el cambio si la declaración requerida falta, es genérica, resulta incoherente o no corresponde a los commits revisados.

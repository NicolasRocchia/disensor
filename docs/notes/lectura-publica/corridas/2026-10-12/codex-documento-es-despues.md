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
comando: codex exec --json -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o C:\Users\Usuario\AppData\Local\Temp\lectura-publica-g71qm4om\respuesta.md
inicio: 2026-10-12T14:57:21-03:00
fin: 2026-10-12T14:57:39-03:00
duracion_s: 18
confinamiento: por instrucción; ver llamadas_a_herramientas
cli_eventos: {"item.completed/agent_message": 1, "thread.started": 1, "turn.completed": 1, "turn.started": 1}
cli_llamadas_a_herramientas: 0
```

## Respuesta

Disensor es una herramienta para registrar y hacer cumplir el resultado de una revisión adversarial de código entre modelos de IA.

El método es el “desacuerdo controlado”: un modelo genera el cambio, otro modelo —preferentemente de otra familia— lo ataca, el generador verifica cada hallazgo y cada uno termina incorporado, refutado con evidencia, convertido en deuda, aceptado por su dueño o escalado a una persona.

El resultado no es un sello de aprobación ni un puntaje de calidad. Es una declaración de **residuo**: un archivo JSON versionado junto al código que deja constancia de:

- Qué commits y qué compuerta —plan, diff o arquitectura— se revisaron.
- Quién generó y quién revisó el cambio.
- La independencia y el confinamiento del revisor.
- El hash de la consigna adversarial.
- Cada hallazgo, su estado terminal y cómo se verificó.
- Los riesgos, refutaciones y huecos de ejecución que todavía merecen atención humana.
- Métricas cuyos conteos deben coincidir con los hallazgos declarados.

El CLI genera una plantilla con `disensor new`, la valida contra el esquema y las reglas R0–R13 con `disensor validate`, y puede bloquear un pull request mediante `disensor gate` si falta evidencia, es genérica o no corresponde al cambio.

Un artefacto usa actualmente el esquema `residue/v0.4` y se guarda normalmente como `.residue/<event_id>.json`. Este es un ejemplo abreviado:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "27089d19-ee91-4c6c-b517-63b9627969e0",
    "created_at": "2026-09-29T10:21:11-03:00",
    "repository": "github.com/organizacion/proyecto",
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
      "title": "La validación omitía un caso rechazado por el gate",
      "description": "El revisor detectó que una declaración inválida podía considerarse cubierta.",
      "location": "src/disensor/gate.py",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Se compararon las comprobaciones de ambas rutas de ejecución."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_gate.py::test_invalid_declaration_covers_nothing"
      }
    },
    {
      "id": "h2",
      "origin": "r1",
      "severity": "info",
      "title": "El rango revisado podría no coincidir con el contrato",
      "description": "El revisor cuestionó qué árbol debía evaluar el gate.",
      "location": "src/disensor/gate.py",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "repository",
        "detail": "El código confirma que el contrato evalúa el head del PR."
      },
      "evidence": {
        "text": "resolve_context obtiene head_oid y evalúa el rango merge-base..head."
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
        "description": "La objeción fue refutada contra el código, pero queda registrada para que una persona pueda revisar esa conclusión."
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

Cada hallazgo admite seis estados terminales:

`incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive` o `escalated_open`.

Incluso una refutación verificable entra en el residuo: así el registro no obliga al humano a aceptar como correcta la conclusión del modelo que la refutó.

# codex, documento, es, antes

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
modo: documento
idioma: es
estado: antes
pregunta: ¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.
documento: README.es.md
commit: de14e5c
sha256: 85d80fe0097ffcd4ca6e658306581787979dc26cbc7e79de7a4ceb31a2f24fc1
bytes: 45859
prompt_sha256: 45d77acac78c6e9718b020f5ca5d90aa305ae3a1384efb0ef90fa06eb7c83243
comando: codex exec --json -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o <archivo>
inicio: 2026-10-12T14:57:00-03:00
fin: 2026-10-12T14:57:21-03:00
duracion_s: 20
confinamiento: por instrucción; ver llamadas_a_herramientas
cli_eventos: {"item.completed/agent_message": 1, "thread.started": 1, "turn.completed": 1, "turn.started": 1}
cli_llamadas_a_herramientas: 0
```

## Respuesta

Disensor es una herramienta para registrar y hacer cumplir el resultado de una revisión adversarial de software. Un modelo genera el cambio, otro —idealmente de una familia distinta— lo ataca, y cada hallazgo debe terminar incorporado, refutado con evidencia, registrado como deuda, aceptado por su dueño o escalado.

El resultado no es un “aprobado”: es una declaración versionada del residuo que la revisión dejó para evaluación humana. El CLI valida el archivo y el gate de CI puede bloquear un PR si falta, es genérico o no corresponde al cambio revisado.

El artefacto:

- Es JSON y usa actualmente el esquema `residue/v0.4`.
- Vive en `.residue/`.
- Se llama `<event_id>.json`, donde `event_id` es un UUID canónico.
- Identifica al generador, los revisores y al árbitro humano.
- Registra los commits exactos revisados y la compuerta (`plan`, `diff` o `architecture`).
- Incluye el hash SHA-256 de la consigna adversarial.
- Declara el confinamiento y la independencia real del revisor.
- Enumera hallazgos, su estado final, verificación y evidencia.
- Expone explícitamente el residuo que requiere atención humana.
- Puede usar perfil `full` o `minimized`.

Como el documento no incluye uno de los archivos completos de `spec/examples/` ni reproduce todo el JSON Schema, este es un ejemplo conceptual basado únicamente en los campos y valores documentados; no pretende sustituir la plantilla exacta producida por `disensor new`:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "gate": "diff",
    "criticality_level": "B",
    "profile": "full",
    "repository": "sha256:REPOSITORIO",
    "pr": "PR-42",
    "base_commit": "1111111111111111111111111111111111111111",
    "head_commit": "2222222222222222222222222222222222222222",
    "prompt_hash": "sha256:CONSIGNA_ADVERSARIAL"
  },
  "actors": {
    "generator": {
      "family": "anthropic",
      "model": "modelo-generador"
    },
    "reviewers": [
      {
        "id": "reviewer-1",
        "family": "openai",
        "model": "modelo-revisor",
        "independence": "cross_family",
        "hardening": "verified"
      }
    ],
    "human_arbiter": {
      "id": "responsable-humano"
    }
  },
  "confinement": {
    "mode": "read_only_by_instruction",
    "verified": true
  },
  "findings": [
    {
      "id": "finding-1",
      "reviewer_id": "reviewer-1",
      "description": "La autorización no comprobaba el propietario del recurso.",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Se comprobó la validación de ownership en el código."
      },
      "fix_verification": {
        "method": "specific_test",
        "evidence": {
          "text": "La prueba rechaza el acceso de otro propietario."
        }
      }
    },
    {
      "id": "finding-2",
      "reviewer_id": "reviewer-1",
      "description": "Posible carrera durante una actualización concurrente.",
      "final_state": "escalated_open",
      "verification": {
        "against": "execution",
        "detail": "No fue posible ejecutar una prueba concurrente concluyente."
      }
    }
  ],
  "residue": {
    "items": [
      {
        "id": "residue-1",
        "class": "escalation_without_decision",
        "finding_id": "finding-2",
        "description": "La conducta bajo concurrencia requiere decisión humana."
      }
    ],
    "declared_absence": false,
    "declaration": "Queda abierta la evaluación del comportamiento concurrente."
  }
}
```

En la práctica, la plantilla se crea con:

```bash
disensor new --gate diff --level B
```

Luego se completa y valida con:

```bash
disensor validate .residue/<event_id>.json
```

La idea central es que el archivo conserve no sólo qué encontró el revisor, sino también qué pudo verificarse, qué no, cómo terminó cada desacuerdo y qué riesgo sigue dependiendo de una decisión humana.

# codex, documento, es, antes

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
modo: documento
idioma: es
estado: antes
repeticion: 1
pregunta: ¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.
documento: README.es.md
commit: de14e5c
sha256: 85d80fe0097ffcd4ca6e658306581787979dc26cbc7e79de7a4ceb31a2f24fc1
bytes: 45859
prompt_sha256: 45d77acac78c6e9718b020f5ca5d90aa305ae3a1384efb0ef90fa06eb7c83243
comando: codex exec --json -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o <archivo>
inicio: 2026-10-12T23:42:09-03:00
fin: 2026-10-12T23:42:31-03:00
duracion_s: 22
confinamiento: por instrucción; ver llamadas_a_herramientas
cli_eventos: {"item.completed/agent_message": 1, "thread.started": 1, "turn.completed": 1, "turn.started": 1}
cli_llamadas_a_herramientas: 0
cli_eventos_ilegibles: 0
```

## Respuesta

`disensor` es una herramienta para registrar y hacer cumplir el resultado de una revisión adversarial de software.

Su método, llamado desacuerdo controlado, funciona así: un modelo genera el cambio, otro modelo —preferentemente de una familia diferente— lo ataca, el generador verifica cada hallazgo y cada punto termina incorporado, refutado con evidencia, convertido en deuda, aceptado por un responsable o escalado a una persona.

El resultado se guarda como una declaración de residuo: un archivo JSON versionado dentro de `.residue/`, junto al código revisado. No es un certificado de calidad ni un puntaje; documenta qué ocurrió y, especialmente, qué quedó sin resolver o dependiendo del juicio humano.

El archivo incluye, entre otras cosas:

- La versión del esquema, actualmente `residue/v0.4`.
- Un `event_id` UUID que también determina el nombre: `<event_id>.json`.
- La compuerta revisada: `plan`, `diff` o `architecture`.
- Los commits exactos; para `diff`, tanto base como head.
- El nivel de criticidad.
- El generador, los revisores y el árbitro humano.
- La familia de cada modelo y la independencia real del revisor.
- El hash SHA-256 de la consigna adversarial.
- Los hallazgos y su estado final.
- Cómo se verificó cada hallazgo y, cuando corresponde, su corrección.
- El residuo restante, incluidos escalados, deudas, huecos de ejecución o correlación del revisor.
- La aceptación humana del riesgo residual.
- Métricas cuyos conteos deben ser coherentes con los hallazgos.

Un ejemplo ilustrativo, basado en los campos descritos en el documento, sería:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "3f728657-321c-4ad1-9606-7c5a5fd9264d",
    "gate": "diff",
    "criticality_level": "B",
    "repository": "repositorio-local",
    "pr": "PR-42",
    "base_commit": "19dd6a873278",
    "head_commit": "8ab947c53120",
    "prompt_hash": "sha256:4dc86f03c210fe41c98f4cf25af8d219d53cb89895e1495cf95ef5fffc70d7cc"
  },
  "actors": {
    "generator": {
      "model": "modelo-generador",
      "family": "anthropic"
    },
    "reviewers": [
      {
        "id": "reviewer-1",
        "model": "modelo-revisor",
        "family": "openai",
        "independence": "cross_family",
        "hardening": "verified"
      }
    ],
    "human_arbiter": {
      "id": "responsable-tecnico"
    }
  },
  "findings": [
    {
      "id": "finding-1",
      "reviewer_id": "reviewer-1",
      "text": "La autorización no comprobaba la pertenencia del recurso.",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Se comprobó el flujo de autorización en el código."
      },
      "fix_verification": {
        "method": "specific_test",
        "detail": "La prueba de acceso entre propietarios diferentes pasa."
      }
    },
    {
      "id": "finding-2",
      "reviewer_id": "reviewer-1",
      "text": "Podría existir una condición de carrera durante la actualización.",
      "final_state": "escalated_open",
      "verification": {
        "against": "execution",
        "detail": "No se pudo reproducir de forma concluyente."
      }
    }
  ],
  "residue": {
    "items": [
      {
        "id": "residue-1",
        "finding_id": "finding-2",
        "class": "escalation_without_decision",
        "description": "La posible condición de carrera requiere una decisión humana."
      }
    ],
    "declared_absence": false,
    "declaration": "Queda abierta la evaluación de concurrencia del segundo hallazgo."
  },
  "metrics": {
    "counts": {
      "findings": 2,
      "incorporated": 1,
      "escalated_open": 1,
      "residue_items": 1
    }
  },
  "lead_acceptance": "El responsable acepta revisar el riesgo antes del merge."
}
```

Este ejemplo muestra la intención y estructura general, pero el contrato normativo exacto es `spec/residue.schema.json`. El archivo real se genera con `disensor new` y se comprueba con:

```bash
disensor validate .residue/3f728657-321c-4ad1-9606-7c5a5fd9264d.json
```

Además del esquema JSON, el validador aplica las reglas R0 a R13; por eso un archivo puede tener JSON bien formado y aun así ser rechazado si, por ejemplo, una refutación no aporta evidencia material, los conteos no cierran o una referencia apunta a un revisor inexistente.

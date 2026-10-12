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
comando: codex exec -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o C:\Users\Usuario\AppData\Local\Temp\lectura-publica-4d4nrjfy\respuesta.md
inicio: 2026-10-12T14:33:17-03:00
fin: 2026-10-12T14:33:45-03:00
duracion_s: 28
cli_exit_code: 0
cli_log_lineas: 105
```

## Respuesta

**disensor** es una herramienta y un método para registrar el resultado de una revisión adversarial de software entre modelos de IA.

En vez de emitir una aprobación o un puntaje, guarda una **declaración de residuo**: un archivo JSON versionado junto al código que documenta:

- quién generó el cambio y quién lo revisó;
- las familias de modelos y su grado de independencia;
- los commits y la compuerta revisada (`plan`, `diff` o `architecture`);
- el hash de la consigna adversarial;
- cada hallazgo y su estado final;
- cómo se verificó cada conclusión;
- qué riesgos, desacuerdos o imposibilidades de ejecución quedaron para revisión humana;
- quién actuó como árbitro humano y aceptó el riesgo residual.

El CLI genera una plantilla en `.residue/` mediante:

```bash
disensor new --gate diff --level B
```

El archivo se llama `<event_id>.json`, donde `event_id` es un UUID canónico. Las declaraciones nuevas usan el esquema `residue/v0.4`. Luego se validan con:

```bash
disensor validate .residue/<event_id>.json
```

Un ejemplo simplificado e ilustrativo del artefacto sería:

```json
{
  "schema": "residue/v0.4",
  "event": {
    "event_id": "4ef5de53-dfe2-4ac2-bbbb-fcf3755fef5d",
    "gate": "diff",
    "criticality_level": "B",
    "base_commit": "8b1a7f0",
    "head_commit": "c37d920",
    "prompt_hash": "sha256:2dc93a2c6f8f..."
  },
  "actors": {
    "generator": {
      "family": "anthropic"
    },
    "reviewers": [
      {
        "id": "reviewer-1",
        "family": "openai",
        "independence": "cross_family",
        "hardening": "verified"
      }
    ],
    "human_arbiter": {
      "id": "owner"
    }
  },
  "findings": [
    {
      "id": "finding-1",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "La corrección fue comprobada contra el código."
      },
      "fix_verification": {
        "method": "specific_test"
      }
    },
    {
      "id": "finding-2",
      "final_state": "refuted_verifiable",
      "verification": {
        "against": "execution",
        "detail": "La prueba reprodujo el caso sin mostrar el fallo."
      },
      "evidence": {
        "text": "La prueba específica terminó correctamente."
      }
    },
    {
      "id": "finding-3",
      "final_state": "escalated_open",
      "verification": {
        "against": "repository",
        "detail": "El código no permite resolver la decisión de producto."
      }
    }
  ],
  "residue": {
    "items": [
      {
        "finding_id": "finding-3",
        "class": "escalation_without_decision",
        "description": "Falta decidir qué comportamiento debe tener el producto en este caso."
      }
    ],
    "declaration": "Queda una decisión de producto pendiente de resolución humana."
  },
  "metrics": {
    "counts": {
      "findings": 3
    }
  }
}
```

Los nombres exactos y campos obligatorios están definidos por `spec/residue.schema.json`; el ejemplo muestra la estructura conceptual descrita en el documento. El artefacto no certifica que el código sea bueno: señala qué se estableció, con qué evidencia y qué incertidumbre permanece.

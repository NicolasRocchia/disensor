# codex, busqueda, es, despues

```yaml
modelo: codex
modelo_pedido: gpt-5.6-sol
cli: codex codex-cli 0.153.4
modo: busqueda
idioma: es
estado: despues
pregunta: ¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.
documento: web
prompt_sha256: 4ec215dace14d8514928f29562b271ca82cf55a519516b789e4750ed9c01f39d
comando: codex --search exec -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o <archivo>
inicio: 2026-10-12T14:37:24-03:00
fin: 2026-10-12T14:38:54-03:00
duracion_s: 89
cli_exit_code: 0
cli_log_lineas: 160
```

## Respuesta

`disensor` es una CLI de Python para dejar evidencia versionada de una revisión adversarial de código: un modelo genera el cambio, otro —idealmente de otra familia— lo ataca, el generador verifica cada observación y una persona arbitra lo que no puede resolverse automáticamente. El resultado queda registrado como JSON dentro del repositorio. [Documentación oficial](https://disensor.dev/es/tool/reference/)

No es un revisor ni un “oráculo” que decide si el código es correcto. Su función principal es:

- Generar la plantilla del registro.
- Validarla contra un JSON Schema y reglas adicionales de coherencia.
- Comprobar en CI que el PR incorpora una declaración válida y correspondiente al código revisado.
- Conservar los hallazgos refutados, escalados o no comprobables para dirigir la revisión humana. [Cómo funciona](https://disensor.dev/es/how-it-works/)

Opcionalmente, `disensor round` puede ejecutar un revisor instalado y capturar su informe, pero no juzga sus conclusiones. El gate tampoco necesita modelos ni claves de API: trabaja sobre los archivos y commits del repositorio. [Repositorio oficial](https://github.com/NicolasRocchia/disensor)

## El archivo que genera

La versión vigente documentada genera un archivo:

```text
.residue/<event_id>.json
```

El nombre debe coincidir con un `event_id` UUID canónico. Actualmente usa claves en inglés y el esquema `residue/v0.4`; `.residuo/` y las claves españolas corresponden a la antigua v0.1. Los comandos españoles, como `disensor nuevo` y `disensor validar`, continúan disponibles como alias. [Referencia y migración](https://disensor.dev/es/tool/reference/)

Se crea, por ejemplo, con:

```powershell
disensor new --gate diff --level B
# Alias:
disensor nuevo --compuerta diff --nivel B
```

Y se valida con:

```powershell
disensor validate .residue\<event-id>.json
```

La declaración contiene:

- `event`: repositorio, PR, commits revisados, compuerta y criticidad.
- `actors`: generador, revisores, independencia, confinamiento y árbitro humano.
- `findings`: cada hallazgo y su estado terminal.
- `residue`: aquello que todavía merece atención o auditoría humana.
- `metrics`: conteos coherentes con los hallazgos. [Explicación del artefacto](https://disensor.dev/es/how-it-works/#el-archivo-que-queda-por-dentro)

Los estados terminales posibles son `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive` y `escalated_open`. Algunas resoluciones obligan a incorporar un ítem de residuo relacionado. [Estados de los hallazgos](https://disensor.dev/es/how-it-works/#un-hallazgo-puede-terminar-en-seis-lugares-y-tres-obligan-a-declarar-residuo)

## Ejemplo

Este es un extracto abreviado del [ejemplo oficial completo](https://github.com/NicolasRocchia/disensor/blob/main/spec/examples/example_2_diff_gate.json):

```json
{
  "schema": "residue/v0.4",
  "profile": "full",
  "event": {
    "event_id": "7c8d9e0f-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
    "created_at": "2026-07-15T18:40:00-03:00",
    "repository": "https://github.com/ejemplo/sistema-interno",
    "pr": "https://github.com/ejemplo/sistema-interno/pull/214",
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
        "reviewer_id": "r1",
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
      "id": "dueno-feature-02"
    }
  },
  "findings": [
    {
      "id": "h1",
      "origin": "r1",
      "severity": "major",
      "title": "El flujo de escritura no se libera si la consulta falla",
      "description": "Una falla intermedia dejaba el flujo tomado.",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "Confirmado en el código del diff."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/Exportacion_FallaIntermedia_LiberaFlujo"
      }
    },
    {
      "id": "h2",
      "origin": "r1",
      "severity": "major",
      "title": "Límite de filas sin definir",
      "description": "Producto no definió el máximo permitido.",
      "final_state": "escalated_open",
      "verification": {
        "against": "repository",
        "detail": "El código y el requerimiento no definen el límite."
      }
    }
  ],
  "residue": {
    "items": [
      {
        "id": "r1",
        "class": "escalation_without_decision",
        "finding_ref": "h2",
        "requires_human_attention": true,
        "description": "El límite quedó escalado a producto."
      },
      {
        "id": "r2",
        "class": "execution_gap",
        "requires_human_attention": true,
        "gap_reason": "environment_not_reproducible",
        "description": "No se probó bajo concurrencia real."
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
        "refuted_verifiable": 0,
        "refuted_interpretive": 0
      },
      "escalated_open": 1
    },
    "extra_time_sec": 2400
  }
}
```

El `prompt_hash` es el SHA-256 de la consigna adversarial: permite comparar exactamente qué prompt se declaró, aunque por sí solo no demuestra que efectivamente se haya enviado al modelo. [Documentación del campo](https://disensor.dev/es/how-it-works/#el-archivo-que-queda-por-dentro)

En síntesis: el artefacto no pretende demostrar que “el código está bien”; deja una trazabilidad auditable de quién revisó, qué encontró, cómo terminó cada hallazgo y qué incertidumbre quedó viva.

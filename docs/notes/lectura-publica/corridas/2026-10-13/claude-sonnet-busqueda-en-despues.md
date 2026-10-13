# claude-sonnet, busqueda, en, despues

```yaml
modelo: claude-sonnet
modelo_pedido: sonnet
cli: claude 2.1.285 (Claude Code)
modo: busqueda
idioma: en
estado: despues
repeticion: 1
pregunta: What is disensor and what does the file it generates look like? Show an example of the artifact.
documento: web
prompt_sha256: 98fdba38ac47cddd691a28f7bff5cf8a228c172aa436f67738e2aa43d89bee79
comando: claude -p --safe-mode --no-session-persistence --model sonnet --output-format json --tools WebSearch,WebFetch
inicio: 2026-10-13T10:03:59-03:00
fin: 2026-10-13T10:05:22-03:00
duracion_s: 82
confinamiento: con búsqueda web, a propósito
cli_duration_ms: 80997
cli_duration_api_ms: 90611
cli_num_turns: 8
cli_total_cost_usd: 0.22205560000000002
cli_subtype: success
cli_usage: {"input_tokens": 10, "cache_creation_input_tokens": 10346, "cache_read_input_tokens": 26433, "output_tokens": 3486, "output_tokens_details": {"thinking_tokens": 12}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 10346, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 2692, "cache_read_input_tokens": 8274, "cache_creation_input_tokens": 4661, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 4661}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001", "claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 7
cli_eventos_ilegibles: 0
```

## Respuesta

## Qué es Disensor

Disensor es una herramienta de revisión de código adversarial entre modelos de IA. Es una CLI en Python más una GitHub Action. Un modelo genera el código y un modelo de otra familia lo ataca. El generador verifica cada hallazgo. El ciclo termina cuando cada hallazgo se resolvió, se refutó con evidencia o se escaló a una persona ([disensor.dev](https://disensor.dev/), [GitHub](https://github.com/NicolasRocchia/disensor)).

El gate de CI no ejecuta ningún modelo ni usa API keys. Solo valida el archivo que la revisión dejó en el repo: el esquema, las reglas y el cambio que hace el PR ([GitHub](https://github.com/NicolasRocchia/disensor)). El autor explica la idea en [DEV Community](https://dev.to/nicolasrocchia/your-ai-code-reviewer-approved-the-pr-what-did-it-leave-open-4nhg).

## El archivo que genera

Es una *residue declaration* (declaración de residuo), un JSON pequeño con estas características:
- **Ubicación:** `.residue/<event_id>.json`, donde `event_id` es un UUID ([GitHub](https://github.com/NicolasRocchia/disensor)).
- **Qué registra:** quién generó y quién atacó (familia, modelo y hash del prompt adversarial), cada hallazgo con su estado terminal y el residuo. El residuo es lo que el ciclo no pudo cerrar solo y que ahora depende del criterio de una persona ([disensor.dev](https://disensor.dev/)).
- **Estados terminales de un hallazgo:** `incorporated`, `refuted_verifiable`, `refuted_interpretive`, `debt_recorded`, `owner_decision` y `escalated_open` ([referencia](https://disensor.dev/tool/reference/)).
- **Versión de esquema:** `residue/v0.4`. El gate rechaza versiones anteriores y posteriores ([GitHub](https://github.com/NicolasRocchia/disensor)).
- **Comandos principales:** `disensor init`, `round`, `new`, `validate`, `gate` y `report`.

## Ejemplo real

Es la declaración del PR #101 del propio repo ([fuente raw](https://raw.githubusercontent.com/NicolasRocchia/disensor/main/.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json)). La recorté así:
- Dejé 2 revisores de 12. Los otros 10 son idénticos salvo `reviewer_id`.
- Dejé 2 hallazgos de 19.
- Dejé 2 ítems de residuo de 4.
- Los textos están en español en el original.

```json
{
  "schema": "residue/v0.4",
  "profile": "full",
  "event": {
    "event_id": "27089d19-ee91-4c6c-b517-63b9627969e0",
    "created_at": "2026-09-29T10:21:11-03:00",
    "repository": "github.com/NicolasRocchia/disensor",
    "head_commit": "c2970915df2501b5eb214e3272174bb03638f610",
    "gate": "diff",
    "criticality_level": "B",
    "abbreviated_path": { "used": false },
    "base_commit": "b340cfc30fc418957f2dfafc82c1e14bf8e87884"
  },
  "actors": {
    "generator": { "family": "anthropic", "model": "claude-fable-5-1" },
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
        "prompt_hash": "sha256:e542463911f99ee61304a9b5b9c315c656e4000432ac16aa6115b1cab9025450"
      }
      /* … r2 a r12 (recortados) */
    ],
    "human_arbiter": { "present": true }
  },
  "findings": [
    {
      "id": "h1",
      "origin": "r1",
      "severity": "major",
      "title": "Una declaracion anclada no prueba que el gate corrio ni que paso",
      "description": "El plan v1 prometia responder si todos los merges pasaron por el gate. […]",
      "location": "plan v1, objetivo; src/disensor/report.py (_board_coverage, render_board)",
      "final_state": "incorporated",
      "verification": {
        "against": "repository",
        "detail": "gate.py no persiste veredictos … leido en el repositorio antes de reescribir el plan."
      },
      "fix_verification": {
        "type": "specific_test",
        "reference": "tests/test_branch.py::test_the_board_shows_the_panel_and_the_fourth_figure, …"
      }
    }
    /* … h2 a h19 (recortados) */
  ],
  "residue": {
    "items": [
      {
        "id": "r1",
        "class": "execution_gap",
        "gap_reason": "other",
        "requires_human_attention": false,
        "description": "Ningun revisor abrio el HTML en un navegador ni corrio una auditoria de accesibilidad; […]"
      },
      {
        "id": "r4",
        "class": "principal_refutation",
        "finding_ref": "h16",
        "refutation_type": "verifiable",
        "requires_human_attention": false,
        "description": "El revisor sugirio que la cobertura mirara el arbol del commit de merge y no el head del PR; se refuto con el codigo del gate, que juzga el head. […]"
      }
      /* … r2 y r3 (recortados) */
    ]
  },
  "metrics": {
    "counts": {
      "total_findings": 19,
      "valid": { "incorporated": 18, "debt_recorded": 0, "owner_decision": 0 },
      "false_positives": { "refuted_verifiable": 1, "refuted_interpretive": 0 },
      "escalated_open": 0
    }
  },
  "extensions": {
    "dev.disensor.round": {
      "result_version": 2,
      "pack_hash": "sha256:89215995ce7d4d42c7da044df2335b21af26d14a705bb7358f41e33c17ff235e",
      "report_hash": "sha256:b3fa4f43ab52b2ea10c9c12735f28ceb5b7a3e49611746370d39112fd9b994a9"
    }
  }
}
```

Las `metrics` tienen que cuadrar con la lista de `findings`. Aquí hay 18 incorporados y 1 refutado verificable, que suman 19. La referencia también menciona un perfil minimizado que quita los campos de texto libre (`text`, `link`, `description`) para entornos donde los hallazgos no pueden salir ([referencia](https://disensor.dev/tool/reference/)).

Sources:
- [Disensor (sitio)](https://disensor.dev/)
- [Disensor: Reference](https://disensor.dev/tool/reference/)
- [GitHub – NicolasRocchia/disensor](https://github.com/NicolasRocchia/disensor)
- [Ejemplo de declaración (raw)](https://raw.githubusercontent.com/NicolasRocchia/disensor/main/.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json)
- [DEV Community: Your AI code reviewer approved the PR…](https://dev.to/nicolasrocchia/your-ai-code-reviewer-approved-the-pr-what-did-it-leave-open-4nhg)

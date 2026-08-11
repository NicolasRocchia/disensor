# Integración con el flujo de Claude Code + revisor de otra familia

El gate no corre el loop: el loop sigue corriendo donde corre hoy (Claude Code en la máquina del desarrollador, con un revisor decorrelacionado de otra familia; en el flujo original, Codex). Lo que cambia es el cierre del evento: en lugar de que el resultado quede solo en la conversación, el ciclo emite el artefacto de residuo, lo valida en local y lo versiona en `.residue/`. El gate de CI hace el resto.

## El circuito completo

1. Ronda adversarial como siempre (compuerta de plan o de diff).
2. Al cierre del ciclo: `disensor new --gate diff --level B` genera la plantilla prellenada (uuid, timestamp, repositorio, commits desde git).
3. Claude Code completa la plantilla con los hallazgos del evento y sus estados terminales, el residuo o la declaración expresa de ausencia, y los conteos.
4. `disensor validate .residue/<id>.json` en local. Si falla, se corrige antes de commitear: el gate de CI va a rechazar lo mismo.
5. El artefacto va en su propio commit (`docs(residue): declare event <short-id>`), separado del código, siguiendo la convención de commits atómicos.
6. El PR dispara el gate, que valida todo el rango, aplica política y publica la declaración como comentario.

## Snippet para CLAUDE.md

`disensor init` escribe esta sección en el `CLAUDE.md` del repo (o en el global con `--claude-global`, condicionada a que el repo tenga `disensor.config.json`). Es la versión en inglés y generalizada del snippet original; se reproduce acá para leerla sin correr el comando:

```markdown
## disensor: residue declaration at event close

At the end of each adversarial review round (plan or diff), BEFORE closing
the event:

1. Run `disensor new --gate <plan|diff> --level <A|B|C>` and fill in the
   template it creates under `.residue/` with what happened in the round:
   - One finding per point raised by the reviewer (an assistant of another
     model family), with its terminal state: incorporated (with
     `remedy_adjustment` if you fixed the proposed remedy), debt_recorded
     (with id), owner_decision (with the risk record), refuted_verifiable
     (with evidence), refuted_interpretive, or escalated_open.
   - The verification of each finding (`against`: repository or execution).
   - In the diff gate, the fix verification of each incorporated finding
     (diff_gate or specific_test). Never "pending".
   - The residue: escalations without a decision, refutations of the
     principal, and execution gaps. If nothing remained, the express
     declaration of absence (concrete text, not "no residue").
   - The sha256 hash of the adversarial brief used, in `prompt_hash`.
   - `confinement.verified: true` ONLY if you ran `git status` after the
     round and it was clean.
2. Run `disensor validate` on the file. If it fails, fix it: the CI gate
   rejects exactly the same.
3. The artifact goes in its own commit (`docs(residue): declare event
   <short-id>`). Never mixed with code.
4. Do not invent findings or states: the artifact declares what happened,
   not what should have happened. An event without findings and with an
   express declaration of absence is valid pilot data, not a failure.
```

## Nota sobre el confinamiento

La plantilla nace con `verified: false` a propósito. El modo real de las corridas actuales en Windows es `read_only_by_instruction` (bypass del sandbox del revisor más instrucción de solo lectura más `git status` posterior). Eso pasa el gate en Nivel B, con advertencia si no se verificó. En Nivel A el gate exige `permissions` o `sandbox`: la política del protocolo (sección 10) dice que el revisor solo lee y que eso se garantiza con permisos, no con la consigna. Cuando el sandbox del revisor funcione invocado desde Claude Code en Windows, o cuando la ronda corra en un runner de CI con un usuario sin permisos de escritura, ese requisito se vuelve alcanzable; mientras tanto, el gate hace visible la brecha en lugar de esconderla.

## Qué NO hace esta integración

No corre modelos en CI, no necesita claves de API en el runner, y ningún texto del código viaja a ningún servicio: el gate valida un JSON que ya está en el repo. El plano de evidencia (ingesta, dashboard, reporte de auditor) se conecta después, consumiendo estos mismos artefactos.

# Integración con el flujo de Claude Code + revisor de otra familia

El gate no corre el loop: el loop sigue corriendo donde corre hoy (Claude Code en la máquina del desarrollador, con un revisor decorrelacionado de otra familia; en el flujo original, Codex). Lo que cambia es el cierre del evento: en lugar de que el resultado quede solo en la conversación, el ciclo emite el artefacto de residuo, lo valida en local y lo versiona en `.residue/`. El gate de CI hace el resto.

## El circuito completo

1. Ronda adversarial como siempre (compuerta de plan o de diff).
2. Al cierre del ciclo: `disensor new --gate diff --level B` genera la plantilla prellenada (uuid, timestamp, repositorio, commits desde git).
3. Claude Code completa la plantilla con los hallazgos del evento y sus estados terminales, el residuo o la declaración expresa de ausencia, y los conteos.
4. `disensor validate .residue/<id>.json` en local. Si falla, se corrige antes de commitear: el gate de CI va a rechazar lo mismo.
5. El artefacto va en su propio commit (`docs(residue): declare event <short-id>`), separado del código, siguiendo la convención de commits atómicos.
6. El PR dispara el gate, que valida todo el rango, aplica política y publica la declaración como comentario.

## Qué escribe init para Claude Code

Desde la 0.3.0 el conocimiento está partido en dos piezas, las dos escritas por `disensor init` (o en el ámbito global con `--claude-global`, condicionadas a que el repo tenga `disensor.config.json`):

1. **La sección de `CLAUDE.md`**: el disparador. Dice cuándo actuar (al cierre de cada ronda), en cuatro pasos cortos, y delega el detalle en la skill. Al estar siempre en contexto, se mantiene mínima a propósito.
2. **La skill `.claude/skills/disensor/SKILL.md`**: la guía completa de llenado, que Claude Code carga a demanda cuando cierra una ronda. Campo por campo: la tabla de decisión de `final_state`, las tres clases de residuo, qué exige cada regla R antes de que `validate` rechace, `disensor hash` para el `prompt_hash`, y la política de `confinement.verified`.

La misma guía vive empaquetada en la distribución: `disensor guide` la imprime por stdout para pasársela a un agente que no es Claude (Codex, Gemini, el que sea) o para leerla. Una sola fuente de verdad, tres salidas.

## Nota sobre el confinamiento

La plantilla nace con `verified: false` a propósito. El modo real de las corridas actuales en Windows es `read_only_by_instruction` (bypass del sandbox del revisor más instrucción de solo lectura más `git status` posterior). Eso pasa el gate en Nivel B, con advertencia si no se verificó. En Nivel A el gate exige `permissions` o `sandbox`: la política del protocolo (sección 10) dice que el revisor solo lee y que eso se garantiza con permisos, no con la consigna. Cuando el sandbox del revisor funcione invocado desde Claude Code en Windows, o cuando la ronda corra en un runner de CI con un usuario sin permisos de escritura, ese requisito se vuelve alcanzable; mientras tanto, el gate hace visible la brecha en lugar de esconderla.

## Qué NO hace esta integración

No corre modelos en CI, no necesita claves de API en el runner, y ningún texto del código viaja a ningún servicio: el gate valida un JSON que ya está en el repo. El plano de evidencia (ingesta, dashboard, reporte de auditor) se conecta después, consumiendo estos mismos artefactos.

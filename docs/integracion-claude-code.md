# Integración con el flujo de Claude Code + Codex

El gate no corre el loop: el loop sigue corriendo donde corre hoy (Claude Code en la máquina del desarrollador, con Codex como revisor decorrelacionado). Lo que cambia es el cierre del evento: en lugar de que el resultado quede solo en la conversación, el ciclo emite el artefacto de residuo, lo valida en local y lo versiona en `.residuo/`. El gate de CI hace el resto.

## El circuito completo

1. Ronda adversarial como siempre (compuerta de plan o de diff).
2. Al cierre del ciclo: `disensor nuevo --compuerta diff --nivel B` genera la plantilla prellenada (uuid, timestamp, repositorio, commits desde git).
3. Claude Code completa la plantilla con los hallazgos del evento y sus estados terminales, el residuo o la declaración expresa de ausencia, y los conteos.
4. `disensor validar .residuo/<id>.json` en local. Si falla, se corrige antes de commitear: el gate de CI va a rechazar lo mismo.
5. El artefacto va en su propio commit (`docs(residuo): declara evento <id-corto>`), separado del código, siguiendo la convención de commits atómicos.
6. El PR dispara el gate, que valida todo el rango, aplica política y publica la declaración como comentario.

## Snippet para CLAUDE.md

Agregar al `CLAUDE.md` del proyecto (o al global), a continuación de la sección de Codex como red-team:

```markdown
### Cierre del evento: declaración de residuo

Al terminar cada ronda de Codex (plan o diff), ANTES de dar el evento por cerrado:

1. Corré `disensor nuevo --compuerta <plan|diff> --nivel <A|B|C>` y completá la
   plantilla en `.residuo/` con lo que pasó en la ronda:
   - Un hallazgo por cada punto que trajo Codex, con su estado terminal:
     incorporado (con `ajuste_al_remedio` si le corregiste la solución),
     deuda_registrada (con id), decision_del_dueno (con registro del riesgo),
     refutado_verificable (con evidencia), refutado_interpretativo, o
     escalado_abierto.
   - La verificación de cada hallazgo (`contra`: repositorio o ejecución).
   - En compuerta diff, la verificación de la corrección de cada incorporado
     (compuerta_diff o prueba_especifica). Nunca "pendiente".
   - El residuo: escalados sin decisión, refutaciones del principal y gaps de
     ejecución. Si no quedó nada, la declaración expresa de ausencia (texto
     concreto, no "sin residuo").
   - El hash sha256 de la consigna adversarial usada en `consigna_hash`.
   - `confinamiento.verificado: true` SOLO si corriste `git status` después de
     la ronda y estaba limpio.
2. Corré `disensor validar` sobre el archivo. Si falla, corregilo: el gate de CI
   rechaza exactamente lo mismo.
3. El artefacto va en un commit propio: `docs(residuo): declara evento <id-corto>`.
   Nunca mezclado con el código.
4. No inventes hallazgos ni estados: el artefacto declara lo que pasó, no lo
   que debería haber pasado. Un evento sin hallazgos con declaración expresa
   de ausencia es un dato válido del piloto, no un fracaso.
```

## Nota sobre el confinamiento

La plantilla nace con `verificado: false` a propósito. El modo real de las corridas actuales en Windows es `solo_lectura_por_instruccion` (bypass del sandbox de Codex más instrucción de solo lectura más `git status` posterior). Eso pasa el gate en Nivel B, con advertencia si no se verificó. En Nivel A el gate exige `permisos` o `sandbox`: la política del protocolo (sección 10) dice que el revisor solo lee y que eso se garantiza con permisos, no con la consigna. Cuando el sandbox de Codex funcione invocado desde Claude Code en Windows, o cuando la ronda corra en un runner de CI con un usuario sin permisos de escritura, ese requisito se vuelve alcanzable; mientras tanto, el gate hace visible la brecha en lugar de esconderla.

## Qué NO hace esta integración

No corre modelos en CI, no necesita claves de API en el runner, y ningún texto del código viaja a ningún servicio: el gate valida un JSON que ya está en el repo. El plano de evidencia (ingesta, dashboard, reporte de auditor) se conecta después, consumiendo estos mismos artefactos.

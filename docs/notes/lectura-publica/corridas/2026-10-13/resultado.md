# Resultado, corridas del 2026-10-13

Generado por puntuar.py desde puntajes.json. `sí`/`no` es el valor final (el juicio manda sobre lo mecánico); `?` es un juicio pendiente. `herr.` son las llamadas a herramientas que el encabezado registra (`-` si no las registra); una corrida de documento con más de cero queda fuera del experimento A.

| corrida | estados | archivo_por_evento | findings_final_state | verification | sin_campos_inventados | gate_sin_modelos | sin_aval | total | herr. |
|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-busqueda-en-despues | no | no | no | no | sí | sí | sí | 3/7 | 2 |
| claude-haiku-busqueda-es-despues | no | no | no | no | sí | sí | sí | 3/7 | 2 |
| claude-haiku-documento-en-antes | no | sí | no | no | sí | sí | sí | 4/7 | 0 |
| claude-haiku-documento-en-despues | no | sí | sí | sí | sí | sí | sí | 6/7 | 0 |
| claude-haiku-documento-es-antes | no | no | no | no | sí | sí | sí | 3/7 | 0 |
| claude-haiku-documento-es-despues | no | sí | sí | sí | sí | sí | sí | 6/7 | 0 |
| claude-sonnet-busqueda-en-despues | sí | sí | sí | sí | sí | sí | sí | 7/7 | 7 |
| claude-sonnet-busqueda-es-despues | sí | sí | no | no | sí | sí | sí | 5/7 | 5 |
| claude-sonnet-documento-en-antes | sí | sí | no | no | sí | sí | sí | 5/7 | 0 |
| claude-sonnet-documento-en-despues | sí | sí | sí | sí | sí | sí | sí | 7/7 | 0 |
| claude-sonnet-documento-es-antes | sí | sí | sí | sí | sí | sí | sí | 7/7 | 0 |
| claude-sonnet-documento-es-despues | sí | sí | sí | sí | sí | sí | sí | 7/7 | 0 |

Juicios pendientes: 0.

## Experimento A: antes y después por modelo e idioma

Entran solo las corridas de documento con llamadas a herramientas registradas e iguales a cero. Si una celda tiene varias corridas (repeticiones), un ítem vale "sí" solo si pasa en todas, y se muestra el total de cada una.

| modelo | idioma | antes | después | ítems que cambian |
|---|---|---|---|---|
| claude-haiku | en | 4/7 | 6/7 | findings_final_state: no a sí; verification: no a sí |
| claude-haiku | es | 3/7 | 6/7 | archivo_por_evento: no a sí; findings_final_state: no a sí; verification: no a sí |
| claude-sonnet | en | 5/7 | 7/7 | findings_final_state: no a sí; verification: no a sí |
| claude-sonnet | es | 7/7 | 7/7 | ninguno |

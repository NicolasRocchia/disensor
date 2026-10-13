# Resultado, corridas del 2026-10-12

Generado por puntuar.py desde puntajes.json. `sí`/`no` es el valor final (el juicio manda sobre lo mecánico); `?` es un juicio pendiente. `herr.` son las llamadas a herramientas que el encabezado registra (`-` si no las registra); una corrida de documento con más de cero queda fuera del experimento A.

| corrida | estados | archivo_por_evento | findings_final_state | verification | sin_campos_inventados | gate_sin_modelos | sin_aval | total | herr. |
|---|---|---|---|---|---|---|---|---|---|
| chatgpt-profundo-es-antes | sí | no | no | no | sí | sí | sí | 4/7 | - |
| codex-busqueda-en-despues | sí | sí | sí | sí | sí | sí | sí | 7/7 | - |
| codex-busqueda-es-despues | sí | sí | sí | sí | sí | sí | sí | 7/7 | - |
| codex-documento-en-antes | no | sí | sí | sí | no | sí | sí | 5/7 | 0 |
| codex-documento-en-despues | sí | sí | sí | sí | sí | sí | sí | 7/7 | 0 |
| codex-documento-es-antes | no | sí | sí | sí | no | sí | sí | 5/7 | 0 |
| codex-documento-es-despues | sí | sí | sí | sí | sí | sí | sí | 7/7 | 0 |
| google-ai-mode-busqueda-es-antes | no | no | no | no | no | sí | sí | 2/7 | - |

Juicios pendientes: 0.

## Experimento A: antes y después por modelo e idioma

Entran solo las corridas de documento con llamadas a herramientas registradas e iguales a cero. Si una celda tiene varias corridas (repeticiones), un ítem vale "sí" solo si pasa en todas, y se muestra el total de cada una.

| modelo | idioma | antes | después | ítems que cambian |
|---|---|---|---|---|

Fuera de A: codex-documento-en-antes (sin registro de eventos ilegibles); codex-documento-en-despues (sin registro de eventos ilegibles); codex-documento-es-antes (sin registro de eventos ilegibles); codex-documento-es-despues (sin registro de eventos ilegibles).

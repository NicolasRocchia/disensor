# Lectura de las corridas del 2026-10-13

Escrita a mano sobre `resultado.md` (que genera `puntuar.py`) y sobre las
respuestas completas de `corridas/2026-10-13/`. Es la tanda de Claude que el
12/10 no se pudo correr por el login vencido del CLI: `sonnet` y `haiku`, los
dos experimentos, los dos idiomas. Lo que sigue es lo que las corridas
sostienen, con su cita, y lo que todavía no está medido.

Los alias resuelven a modelos concretos y el encabezado los registra: con el
CLI 2.1.285, `sonnet` es `claude-sonnet-5-5` y `haiku` es
`claude-haiku-4-5-20251001`, no Haiku 5.5, que esa versión del CLI no conoce.
Las dos corridas de Sonnet con búsqueda usaron además Haiku 4.5 como modelo
auxiliar (`cli_modelos_usados` trae los dos); las de documento, solo Sonnet.

Esta es la **segunda** tanda del día. La primera, hecha desde la raíz del
repo como decía el protocolo, se descartó y queda en el historial (commit
`a61a36a`): `claude -p` recibe del harness el directorio de trabajo y, si es
un repositorio, su rama, su estado y sus commits recientes, aunque
`--safe-mode` apague CLAUDE.md. Las corridas de búsqueda lo mostraron a la
vista ("el que tenés en `docs/notes/lectura-publica/` de tu worktree", "los
mensajes de commit mencionan un "puntuador", un `puntajes.json`, un
`final_state` con "seis estados"", "El proyecto se llama
**Disensor-lectura-110**") y las de documento
tuvieron en el prompt del sistema cinco mensajes de commit que nombran
`final_state` y "los seis estados". Se midió el mismo día con una pregunta
directa y las herramientas apagadas: desde la raíz del repo el modelo listó
la rama, la carpeta sin seguimiento de las corridas y los cinco commits;
desde un directorio vacío, "Ninguna (no aplica, ya que no hay repositorio
git)". El corredor corre ahora los dos CLIs
desde un directorio vacío y temporal, y las doce respuestas de esta tanda no
tienen ningún marcador de ese contexto. Las ocho de documento declaran cero
llamadas a herramientas (un turno) y cero eventos ilegibles, y entran en A.

## Experimento A: el ejemplo real ancla la forma, y en una familia más

| modelo | idioma | antes | después | ítems que cambian |
|---|---|---|---|---|
| claude-sonnet | es | 7/7 | 7/7 | ninguno |
| claude-sonnet | en | 5/7 | 7/7 | `findings_final_state`, `verification` |
| claude-haiku | es | 3/7 | 6/7 | `archivo_por_evento`, `findings_final_state`, `verification` |
| claude-haiku | en | 4/7 | 6/7 | `findings_final_state`, `verification` |

En tres de las cuatro celdas los ítems de anclaje cambian de "no" a "sí", el
mismo patrón que dio Codex el 12/10. La cuarta es un techo, no una excepción.

**Sonnet en castellano ya daba 7 de 7 con el README de antes**, y eso dice
más de la rúbrica que del documento. Nombra los seis estados con su grafía,
dice `.residue/<event_id>.json`, y muestra un artefacto con `findings`,
`final_state` y `verification` que presenta como "un boceto ilustrativo
armado con los nombres de campo que el texto menciona; la anidación exacta y
los valores son supuestos míos, así que no lo tomes como el formato real".
Pasa `sin_campos_inventados` porque todas sus claves existen en el esquema,
pero están en el lugar equivocado: `event_id`, `gate`, `base_commit` y
`prompt_hash` en la raíz, `residue` como lista en vez de objeto con `items`,
`human_arbiter.id` en lugar de `present`. Es el límite documentado de la
lista blanca ("mira el nombre, no la posición") y la rúbrica no lo ve. Con el
README de después, copia el extracto real con su anidación. El efecto del
ejemplo existe en esa celda; la rúbrica no tiene dónde anotarlo.

**Sonnet en inglés, antes, se niega a inventar.** "El documento no incluye un
ejemplo completo del artefacto. [...] Por eso no voy a inventar un JSON
completo que podría no coincidir con el esquema real." Describe los campos en
prosa, nombra los seis estados, y el único bloque de código que muestra es
`disensor.config.json`, con la aclaración "no es el artefacto sino la
política del repo". Los ítems de estructura dan "no" por construcción (no hay
bloque con `findings`), y el puntuador marcó `level_A_enabled` como clave
fuera del esquema: el juicio lo levantó, porque es una clave real de la
configuración y la respuesta dice qué es. Es el caso que el protocolo prevé:
una respuesta que dice "no sé" suma cero en los positivos y pasa los
negativos. Con el de después, 7 de 7 copiando el extracto completo.

**Haiku no nombra los seis estados en ninguna de las cuatro corridas**, antes
ni después. Habla de "incorporado, refutado con evidencia, o escalado a un
humano" o de "incorporado, refutado, escalado, etc.", y el ejemplo que copia
trae solo
`incorporated` y `refuted_verifiable`. El extracto del README muestra dos
hallazgos, no la lista de los seis; la lista está en el glosario, y Haiku no
la lee. `estados` es el único ítem que el ejemplo no mueve en esta familia.
Antes, en castellano, tampoco dice dónde vive el archivo ("se coloca en el
repositorio junto al código que juzga"); en inglés sí ("`<event_id>.json`
que se guarda en el directorio `.residue/`"). Después, los dos idiomas dan
`.residue/<event_id>.json` o la ruta del archivo real.

**El "después" de Claude copia los valores, no solo la forma.** El 12/10
Codex copiaba la estructura e inventaba valores (una prueba que no existe en
`fix_verification.reference`). Las cuatro corridas "después" de esta tanda
conservan los del extracto: el `prompt_hash` completo del revisor `r8`, el
`base_commit` y el `head_commit`, la prueba real
`tests/test_branch.py::test_a_declaration_the_gate_rejects_on_its_own_checks_covers_nothing`
y el texto de `evidence` ("El rango juzgado es merge base a head del PR"),
todos verificados contra el README de `96e12ae`. Sonnet avisa qué recorta
("con algunas descripciones largas abreviadas con `…`") y lo cumple. Haiku
recorta sin avisar y a veces mal: en inglés pone `refuted_verifiable: 1`
dentro de `valid` (va en `false_positives`), y en castellano deja
`finding_ref: "h16"` mostrando solo `h15`, con el título de `h15` acentuado
("declaración") donde el archivo no lleva acento. Claves reales, valores
reales, estructura a veces rota: la regla del 12/10 sigue valiendo. Un
lector que le pida a un modelo "cómo es el artefacto" obtiene la forma
correcta y no debería citar los valores sin ir al archivo, ni siquiera
cuando el modelo los copió bien, porque el mismo README dio dos modelos que
hicieron cosas distintas con los mismos valores.

Lo que la primera tanda, la contaminada, mostró en A fue el mismo patrón en
los ítems de anclaje. No se cuenta: su prompt del sistema nombraba
`final_state` y los seis estados, y eso es justo lo que la rúbrica mide.

## Experimento B: en vivo, Sonnet llega al archivo y Haiku no busca

**Sonnet en inglés: 7 de 7.** Encontró el sitio, GitHub, la referencia de
`disensor.dev/tool/reference/`, un artículo del autor en DEV Community y el
archivo crudo `.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json` en
`raw.githubusercontent.com`, y lo recortó diciendo cómo: "Dejé 2 revisores de
12. Los otros 10 son idénticos salvo `reviewer_id`. Dejé 2 hallazgos de 19.
Dejé 2 ítems de residuo de 4." Los valores son los del archivo (verificados:
el `prompt_hash` de `r1`, el `pack_hash`, los títulos de `h1` y `r1`,
`result_version: 2`; el archivo tiene 12 revisores, 19 hallazgos y 4 ítems).
El bloque no parsea como JSON por los comentarios `/* … */` con que marca el
recorte, así que `findings_final_state` y `verification` quedaron a juicio y
el camino sin parsear marcó cuatro claves de `extensions` como fuera del
esquema; el juicio resolvió las tres con la cita. Como Codex el 12/10, llegó
al artefacto completo, no al extracto del README ni a la landing: la mejora
de B no se atribuye al cambio, y el protocolo ya dice que en B no se afirma
causa.

**Sonnet en castellano: 5 de 7.** Citó GitHub, `disensor.dev` y PyPI (la
página de la 0.11.0, una versión anterior a la publicada), listó los seis
estados en prosa y dijo que "el gate no usa modelos ni API keys". Mostró solo
`schema`, `event` y `actors` del ejemplo "según lo muestra la documentación"
y lo dijo: "No pude ver `findings`, `residue` ni `metrics` con su contenido
completo." Por eso `findings_final_state` y `verification` son "no". Lo que
leyó de la landing lo repite bien: "19 hallazgos: 18 incorporados y 1
refutado con evidencia. También tiene 4 ítems de residuo para revisión
humana", que es exacto. Honesto sobre el límite de lo que alcanzó; lo que
alcanzó fue la landing y no el archivo.

**Haiku, en los dos idiomas: 3 de 7, y no buscó.** Dos llamadas a
herramientas, tres turnos, y la respuesta es un pedido: "Necesito tu
autorización para hacer búsquedas en la web. ¿Puedes permitir que use la
herramienta de búsqueda?" Sonnet, con los mismos flags, buscó y leyó.
`--output-format json` no registra qué herramienta pidió Haiku ni qué
respuesta recibió, así que la causa queda sin verificar; una hipótesis es
que intenta una herramienta fuera de `--tools WebSearch,WebFetch` y toma la
negativa por falta de autorización. En la tanda contaminada hizo lo mismo.
Es el caso "no sé": cero en los positivos, pasa los negativos.

Los modos superficiales "después" (Google AI Mode, Perplexity, ChatGPT con
búsqueda) siguen sin corrida: son el objeto original del issue y se cargan a
mano.

## Lo que falta

- **Los modos superficiales "después"**, a mano, con el encabezado de
  corrida manual.
- **Repetición contada.** Una corrida por celda. La tanda contaminada dio el
  mismo patrón en los ítems de anclaje, pero no vale como repetición.
- **Qué herramientas llama Claude en B.** Con `--output-format json` solo
  queda `num_turns`; `stream-json` daría los eventos, como el JSONL de Codex,
  y explicaría por qué Haiku no busca. Para A no hace falta: `--tools ""` lo
  apaga por construcción y un turno lo confirma.
- **`estados` en Haiku.** El extracto del README no lista los seis; Haiku no
  llega al glosario. Si un lector superficial debe verlos, el ejemplo tendría
  que mostrarlos o la prosa cercana nombrarlos. Es una observación, no una
  acción: el cambio de documentación se justificaba solo y esto solo mide.

## Costo observado

Del encabezado de cada corrida (`duracion_s` y `cli_total_cost_usd`, que el
CLI informa aunque la cuenta sea por suscripción):

| modo | modelo | duración | costo informado |
|---|---|---|---|
| documento | sonnet | 16 a 23 s | 0,08 a 0,11 USD |
| documento | haiku | 17 a 20 s | 0,04 a 0,05 USD |
| búsqueda | sonnet | 43 y 82 s | 0,14 y 0,22 USD |
| búsqueda | haiku (no buscó) | 6 y 10 s | 0,006 USD |

La tanda entera suma 0,93 USD informados. Codex el 12/10 tardó entre 16 y 38
segundos por corrida de documento y 44 y 89 con búsqueda, sin informar
tokens: los dos CLIs están en el mismo orden.

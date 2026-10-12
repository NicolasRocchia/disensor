# Lectura de las corridas del 2026-10-12

Escrita a mano sobre `resultado.md` (que genera `puntuar.py`) y sobre las
respuestas completas de `corridas/2026-10-12/`. Lo que sigue es lo que las
corridas sostienen, con su cita, y lo que todavía no está medido.

Las cuatro corridas de documento de Codex son la **segunda** tanda: la
primera se hizo sin registrar las llamadas a herramientas, la ronda
adversarial del cambio señaló que "sin herramientas" era una instrucción y no
un confinamiento, y se repitieron con el registro. Las cuatro repetidas
declaran cero llamadas: los eventos de cada una son `thread.started`,
`turn.started`, un `agent_message` y `turn.completed`, nada más. Lo que
contestaron salió del documento. La primera tanda quedó en el historial de
git (commit `6cfba42`) y dio el mismo patrón que esta: eso es una
replicación, aunque no se la cuente.

## Experimento A: el ejemplo real ancla la forma del artefacto

Codex (`gpt-5.6-sol`, sesión fresca, el README entero como único documento,
cero herramientas) pasa de 5 de 7 a 7 de 7 en los dos idiomas, y los dos
ítems que cambian son exactamente los de anclaje:

- **Los seis estados.** Con el README de antes no los nombra todos: en
  castellano faltan cuatro, en inglés tres (el README de antes los tenía en
  una fila del glosario, al final, y la prosa los describe en palabras). Con
  el de después los lista con su grafía, en los dos idiomas.
- **Las claves inventadas.** Con el README de antes el ejemplo trae claves
  plausibles que el esquema no tiene: `finding_id` y `fix_verification.method`
  en castellano; `reviewer`, `finding_id`, `method`, `reviewed_commit` y
  `metrics.counts.total` en inglés. Además pone `id` donde va `reviewer_id`,
  `prompt_hash` adentro de `event` y `confinement` al nivel de arriba, que son
  claves reales en el lugar equivocado y la lista blanca no las ve. Y lo
  dice: "un ejemplo conceptual basado únicamente en los campos y valores
  documentados", "a simplified illustrative artifact based on the documented
  fields". Sabe que rellena, y rellena igual. Con el README de después,
  ninguna clave fuera del esquema.

Lo que ya hacía bien sin el ejemplo también cuenta: en las cuatro corridas
dice que el archivo vive en `.residue/<event_id>.json`, muestra `findings`
con `final_state` y `verification`, no afirma que el gate corra modelos y no
inventa avales. Eso estaba en la prosa del README de antes, y la prosa alcanzó.
Lo que no alcanzó fue para la forma exacta de un hallazgo: eso lo da el
ejemplo o lo inventa el lector.

**Un matiz que vale más que el resultado.** El "después" copia la estructura
real y la presenta como "ejemplo abreviado" o "simplified artifact", pero no
copia los valores: conserva el `event_id` y los commits de la declaración
27089d19 y cambia `repository` a `github.com/organizacion/proyecto` o
`github.com/example/project`; renombra `r8` como `r1` y `h15` como `h1`;
resume los títulos y las descripciones; y en `fix_verification.reference`
escribe pruebas que no existen (`tests/test_gate.py::test_invalid_declaration_covers_nothing`,
`tests/test_gate.py::test_rejected_artifact_provides_no_coverage`) donde el
archivo cita `tests/test_branch.py::test_a_declaration_the_gate_rejects_on_its_own_checks_covers_nothing`.
El ejemplo ancla la forma, no los hechos: un lector que le pida a un modelo
"cómo es el artefacto" obtiene claves y estados correctos, y no debería citar
ningún valor que el modelo le devuelva como si fuera el del archivo, ni
siquiera cuando el modelo conserva el id real al lado.

## Experimento B: en vivo, el que llega a GitHub lee bien

Codex con búsqueda web, sesión fresca, solo la pregunta: 7 de 7 en los dos
idiomas (en inglés la prosa parafrasea los estados en palabras, pero los seis
aparecen con su grafía como claves de `metrics.counts` en el ejemplo). En los
dos idiomas encontró `how-it-works` del sitio y el ejemplo sintético
`spec/examples/example_2_diff_gate.json` en GitHub, y copió de ahí la forma.
Citó ese ejemplo, no el del README ni el de la landing: la mejora de B no se
puede atribuir al cambio, y el protocolo ya dice que en B no se afirma causa.
Estas dos corridas son de la primera tanda y no registran llamadas a
herramientas; en B las herramientas son el método, así que no las invalida.

Contra eso, el "antes" de Google AI Mode (captura del 12/10 a la mañana): 2 de
7. Un archivo central `.residue/audit.json`, estados en mayúsculas, y
`adversarial_rounds`, `attacker`, `defender`, `blocking_issues` y
`status_counts`, presentados como "así es exactamente como se ve ese archivo
de auditoría técnica por dentro". Lo que distingue a ese lector del Codex con
búsqueda no es la familia del modelo: es qué fuentes leyó. AI Mode leyó
resúmenes del sitio; Codex llegó al archivo de ejemplo. El informe profundo de
ChatGPT del mismo día, que también llegó a las fuentes, acertó los seis
estados y los controles.

La conclusión práctica para la documentación: un lector con búsqueda que
alcanza un artefacto completo, donde sea que esté, reproduce bien la forma;
el que se queda en la prosa de resumen la inventa. Poner el hallazgo real en
la landing y en el README acorta ese camino para el lector que no llega a
`spec/examples/`; si acorta lo suficiente para los modos superficiales, lo
dirán las corridas que faltan.

## Lo que falta

- **Claude (sonnet y haiku), A y B.** El CLI anidado no pudo autenticarse el
  12/10 ("OAuth session expired and could not be refreshed"); se corren cuando
  se renueve el login. Sin eso, el efecto de anclaje está medido en una sola
  familia.
- **Los modos superficiales "después".** Google AI Mode, Perplexity, ChatGPT
  con búsqueda, en sesión fresca y con la pregunta fija, pegados como corridas
  manuales. Son el objeto original de la medición y todavía no hay ninguno
  "después".
- **Repetición contada.** Una corrida por celda en el directorio. La primera
  tanda, en el historial, dio el mismo patrón; cuando haya repeticiones con
  registro, se guardan todas y se cuentan.

## Costo observado

Codex, modo documento: entre 18 y 32 segundos por corrida; con búsqueda, 44 y
89 segundos. El CLI no informa tokens. Las corridas de Claude, cuando corran,
traen `total_cost_usd` en el encabezado.

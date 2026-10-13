# Lectura pública: cómo leen la documentación los asistentes con búsqueda

Medición del issue #110. El 12/10/2026 una consulta a Google AI Mode sobre
disensor devolvió un artefacto inventado: un `.residue/audit.json` central,
estados `INCORPORATED`, `DEBT_REGISTERED`, `REFUTED` y `SCALED`, y campos
`adversarial_rounds`, `attacker`, `defender` y `blocking_issues`. El mismo día
un informe con lectura profunda de las mismas fuentes públicas devolvió los
seis estados, las reglas y los controles correctos. La hipótesis es de
anclaje: lo que la documentación no muestra en código, el lector superficial
lo rellena con la plantilla genérica de "AI code review". Los PR #118 (README)
y disensor-web #13 (landing) pusieron un hallazgo real con su estado terminal
donde antes había solo el bloque `residue` de un ejemplo sintético. Esto mide
si eso cambió algo.

Es una medición, no una feature. No optimiza la documentación "para los
modelos": el cambio de documentación se justificaba solo (un ejemplo real
donde no había ninguno), y esto dice si además alcanza para el lector
superficial.

## Dos experimentos, porque el "antes" en vivo ya no existe

El sitio y el README de antes del cambio dejaron de estar en línea el 12/10.
Un asistente con búsqueda lee lo que hay hoy, así que para ese modo la única
corrida "antes" posible es la que se capturó antes del merge. Por eso hay dos
experimentos con la misma pregunta y la misma rúbrica:

**A. Anclaje, controlado.** El mismo modelo, en sesión fresca y sin acceso a
otra cosa que el documento (ver "Confinamiento", abajo), recibe la pregunta y
el README completo como único documento, una vez con el README de antes
(commit `de14e5c`) y otra con el de después (`96e12ae`). Entre esos dos commits los README solo cambian por la sección
del ejemplo (234 líneas agregadas, ninguna borrada: `git diff --stat de14e5c
96e12ae -- README.md README.es.md`). Lo que cambie entre las dos respuestas
es efecto del ejemplo. Se corre en los dos idiomas, con el README de cada uno.

**B. Primera impresión, en vivo.** Sesión fresca con búsqueda web, solo la
pregunta. El "después" se corre con lo que hay publicado; el "antes" son las
capturas del 12/10 a la mañana (Google AI Mode, modo superficial; ChatGPT,
modo profundo), que se guardan tal cual como corridas manuales.

## La pregunta, fija

- ES: "¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del
  artefacto."
- EN: "What is disensor and what does the file it generates look like? Show an
  example of the artifact."

En A va precedida de "Contestá usando solo el documento que sigue, sin buscar
en la web ni usar herramientas" y el README entero. En B, de "Buscá en la web
lo que necesites y citá de dónde sale cada cosa". Nada más: ni pistas sobre
el esquema ni pedido de cautela, porque un lector superficial tampoco las
tiene, y pedir "un ejemplo" obliga a copiar uno si lo hay o a inventarlo si no.

## Los modelos y cómo se los corre en sesión fresca

| Id | Comando | Modo A (documento) | Modo B (búsqueda) |
|---|---|---|---|
| `claude-sonnet` | `claude -p --safe-mode --no-session-persistence --model sonnet` | `--tools ""` | `--tools WebSearch,WebFetch` |
| `claude-haiku` | ídem con `--model haiku` | `--tools ""` | `--tools WebSearch,WebFetch` |
| `codex` | `codex exec --json -m gpt-5.6-sol --dangerously-bypass-approvals-and-sandbox --ephemeral --ignore-user-config --ignore-rules -c project_doc_max_bytes=0 --skip-git-repo-check -o <archivo>` desde un directorio vacío | por instrucción, con las llamadas a herramientas registradas | `--search` antes de `exec` |

`--safe-mode` apaga CLAUDE.md, skills, plugins, hooks y MCP; `--ephemeral`,
`--ignore-user-config` e `--ignore-rules` son la receta endurecida del
catálogo de revisores. No hay Gemini CLI ni Ollama en esta máquina; Google
entra solo por la captura manual de AI Mode. Las corridas manuales de otras
interfaces (Perplexity, ChatGPT con búsqueda, AI Mode "después") se agregan a
mano con el mismo encabezado, ver abajo.

## Confinamiento, que no es igual en los dos CLIs

`claude -p --tools ""` apaga las herramientas por construcción, y el
encabezado registra `num_turns` (uno es la respuesta sola). `codex exec` no
tiene un flag que las apague, y su sandbox no arranca desde algunos procesos
padre en Windows: en modo documento el confinamiento es por instrucción, igual
que la receta `read_only_by_instruction` del catálogo de revisores, y el
directorio vacío acota lo que tiene a mano pero no lo que puede alcanzar. Lo
que sí se registra, leyendo los eventos JSONL de la corrida (`--json`), es
cuántas herramientas llamó: `cli_llamadas_a_herramientas` en el encabezado,
con el conteo por tipo de evento en `cli_eventos` y las líneas que parecían
un evento y no se pudieron leer en `cli_eventos_ilegibles` (una ilegible
también saca la corrida de A: podría ser una herramienta que no se contó).
Un registro ausente no es cero: una corrida hecha con un corredor que no
contaba algo queda fuera de A hasta repetirse, porque el JSONL crudo no se
guarda y lo que no se contó no se reconstruye.
El conteo es por descarte,
a propósito: todo ítem completado que no sea el mensaje del agente o su
razonamiento cuenta como herramienta, así que una versión del CLI que renombre
o agregue tipos sobra y saca la corrida de A, no falta y la cuela. Una corrida
de documento con llamadas a herramientas se puntúa igual y queda fuera del
experimento A: lo que leyó no fue solo el documento.

Las cuatro corridas de documento de Codex del 12/10 anteriores a este
registro se descartaron y se repitieron con él; las originales quedan en el
historial de git. Lo cazó la ronda adversarial de este mismo cambio: la
primera versión decía "sin herramientas" donde solo había una instrucción.

## La rúbrica, binaria por ítem

| Ítem | Pasa si |
|---|---|
| `estados` | Nombra los seis estados con su grafía exacta: `incorporated`, `debt_recorded`, `owner_decision`, `refuted_verifiable`, `refuted_interpretive`, `escalated_open`. |
| `archivo_por_evento` | Dice que hay un archivo por evento en `.residue/`, no un archivo central. |
| `findings_final_state` | Muestra `findings[]` con `final_state`. |
| `verification` | Menciona `verification` o `fix_verification`. |
| `sin_campos_inventados` | No inventa campos ni estados (p. ej. `adversarial_rounds`, `attacker`, `defender`, `blocking_issues`, estados en mayúsculas). |
| `gate_sin_modelos` | No afirma que el gate corre modelos ni pide claves de API. |
| `sin_aval` | No afirma aval institucional (W3C u otro). |

`puntuar.py` resuelve mecánicamente lo que se puede y deja el resto como
juicio con la evidencia a la vista; el juicio se escribe a mano en
`puntajes.json`, con la cita que lo sostiene, y manda sobre lo mecánico en
cualquier ítem. Lo mecánico, y sus límites conocidos:

- `estados` es ocurrencia literal de las seis grafías en toda la respuesta:
  nombrarlos en prosa vale, y una negación que los liste también pasa.
- `findings_final_state` y `verification` se miran por estructura, en los
  bloques de código parseados como JSON (un bloque abreviado con `...` se
  repara antes); si ningún bloque parsea, quedan a juicio. Una mención en
  prosa no cuenta.
- `sin_campos_inventados` contrasta las claves de los bloques con la lista
  blanca del esquema, y los valores de `final_state` con los seis estados,
  más una lista negra de lo que ya se vio inventar; todo mirado solo adentro
  de los bloques: una advertencia en prosa sobre un campo que no existe no es
  inventarlo. Mira el nombre, no la posición: una clave real en el lugar
  equivocado pasa.

Una respuesta que dice "no sé" suma cero en los ítems positivos y pasa los
negativos: eso también es un dato.

## Cómo se corre y qué queda

Desde la raíz del repositorio, en un checkout limpio:

```
python3 docs/notes/lectura-publica/correr.py --fecha 2026-10-12 [--modo documento|busqueda|todos] [--modelos claude-sonnet,codex] [--repeticion N]
python3 docs/notes/lectura-publica/puntuar.py --fecha 2026-10-12
```

Una corrida que falla (el CLI sale con error o no contesta) no deja archivo:
se informa y se sigue, para que un fallo de infraestructura no quede como si
fuera una respuesta del modelo. Cada corrida que sí contesta deja
`corridas/<fecha>/<modelo>-<modo>-<idioma>-<antes|despues>.md`
con un encabezado (modelo, modo, idioma, documento con commit y sha256 o
"web", comando, inicio, fin, duración, costo si el CLI lo informa) y la
respuesta completa, sin editar. `puntuar.py` escribe `puntajes.json` con un
registro por corrida e ítem (`auto`, `juicio`, `evidencia`) y arma
`resultado.md` con la tabla por modelo e ítem, antes y después.

Una corrida manual es un archivo con el mismo encabezado, `modo: busqueda` o
`modo: profundo`, `modelo` con el nombre de la interfaz, `capturado_por` y la
respuesta pegada entera. Se la puntúa igual.

## Lo que no se hace

- No se cuentan respuestas de sesiones con conversación previa, memoria o
  archivos adjuntos: solo sesiones frescas.
- No se repite una corrida hasta que "salga bien". Una repetición se guarda
  aparte (`--repeticion N`, sufijo `-rN` en el archivo) y cuenta: en la tabla
  de A, una celda con varias corridas vale "sí" en un ítem solo si pasa en
  todas, "no" si falla en alguna y "?" si ninguna falla pero alguna está
  pendiente de juicio, y muestra el total de cada una. Reemplazar una corrida por otra con
  el mismo nombre solo se hace por una razón de método, dicha en el commit,
  como se hizo con las cuatro de Codex sin registro de herramientas.
- No se infiere causa en B: el "después" en vivo depende de qué indexó cada
  buscador y cuándo. La causa solo se afirma en A.

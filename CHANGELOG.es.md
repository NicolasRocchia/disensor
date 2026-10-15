# Registro de cambios

Qué cambió en cada versión de disensor, de la más nueva a la más vieja. El
mismo registro en inglés es [CHANGELOG.md](CHANGELOG.md).

Hasta la 0.10.0, cada entrada es el trozo del viejo párrafo de `## Estado` del
README que describía esa versión, transcripto tal como estaba. Solo cambiaron
las costuras: el "La versión anterior" del comienzo pasa a "Esta versión" (y
en la 0.7.0 el verbo pasa de "agregó" a "agrega"), un trozo cortado a mitad de
oración cierra con punto, y las referencias a secciones del README pasaron a
ser enlaces. Las versiones que ese párrafo no describía (0.9.1, 0.6.5, 0.6.2,
0.3.0 y 0.1.0) no tienen entrada, y no hubo 0.8.0.

## 0.14.0 (2026-10-15)

Esta versión es sobre lo que le llega al revisor desde la máquina donde corre,
todavía sobre residue/v0.4. La receta `codex` del catálogo corre desde un
`CODEX_HOME` aislado bajo la política `codex_home/1`
(`~/.disensor/reviewers/codex/home`): sus invariantes se chequean en disco antes
de cada intento, cada intento corre desde su propio directorio de trabajo
privado y bajo un lock, el entorno del subproceso pasa por allowlist, la receta
suma `--disable` por nombre para plugins, apps, hooks, memories, multi_agent y
remote_plugin, apaga las skills incluidas y lleva el `skills.config` armado con
el inventario del disco, y el registro guarda en `executable` el binario nativo
detrás del lanzador de npm (`reviewer add --executable` para un lanzador que no
sabe resolver); hasta ahora el `AGENTS.md` global y las skills del dueño le
llegaban al revisor con los tres flags de endurecimiento puestos.
`disensor reviewer login codex` loguea ese home una vez, con la terminal del
dueño, y disensor nunca lee, copia ni guarda credenciales. `new --round`
conserva `verified` solo con la evidencia de la política y una versión del CLI
certificada en el intento exitoso, y declara todo lo demás `unverified` con su
ítem; `verified` queda redactado como la neutralización de fuentes enumeradas
para versiones y condiciones concretas del CLI, hoy codex-cli 0.153.4 y 0.162.1
en Windows, y el motivo del fallback conserva cada intento fallido con su
detalle en vez de informar un `quota_exhausted` que el runner nunca observó
([#108](https://github.com/NicolasRocchia/disensor/issues/108),
[#147](https://github.com/NicolasRocchia/disensor/pull/147)). La prueba hostil
de la receta ya no puede pasar sin que el modelo conteste: lee solo la
respuesta que el CLI escribe en un archivo, exige exit 0, toma `{model}` de
`DISENSOR_SMOKE_MODEL`, comparte `fill_argv` con el runner y toma como
veredicto solo la palabra contestada
([#92](https://github.com/NicolasRocchia/disensor/issues/92)); sus tres parejas
miden si una fuente alcanza al modelo, por la cita literal de un nombre
aleatorio, y no si el modelo obedece una orden plantada en ella,
`DISENSOR_SMOKE_CODEX` elige el binario, y el cleanup de cada intento quita,
bajo el lock, la entrada de confianza que codex-cli 0.153.4 escribe en el home,
solo cuando tiene exactamente esa forma
([#149](https://github.com/NicolasRocchia/disensor/pull/149)). El smoke de esta
release, como pide la prueba: el 2026-10-15, en Windows 11 con Python 3.14.2 y
el modelo gpt-5.6-sol, `tests/test_hardening.py` dio 28 pasadas con codex-cli
0.153.4 y 28 con codex-cli 0.162.1; con el `AGENTS.md` canario en el
repositorio la receta contestó `NINGUNO` y su control citó el canario, con el
canario en el home aislado la receta cortó como `context_unverified` antes de
inferir y su control citó el canario, y con la skill canario en
`~/.agents/skills` la receta contestó `NINGUNA` y su control listó 41 skills,
la canario entre ellas; con el diseño anterior de #92 para el repositorio la
receta había contestado `LIMPIO` y su control `COMPROMETIDO`, también 28 y 28,
y el cleanup tal como se publica volvió a pasar con 0.153.4, la versión que
escribe el archivo que barre. Queda como deuda: con codex-cli 0.153.4, en un
perfil de Windows cuya ruta lleva un apóstrofo el cleanup no reconocería la
entrada de confianza y el intento siguiente fallaría cerrado
(`confianza-clave-basica-con-escapes`). Para quien ya tenía `codex`
registrado: la entrada armada con la receta vieja ya no coincide con el
catálogo, así que `round` la deja fuera de la cadena con la instrucción de
registrarla de nuevo; corré `disensor reviewer remove codex`,
`disensor reviewer add codex --model <modelo> --yes`,
`disensor reviewer login codex` y, en cada repositorio que corre rondas,
`disensor reviewer consent codex`, porque el consentimiento cubre la receta que
cambió. Una entrada nueva cuyo home no se logueó termina su intento en
`not_authenticated`, y la cadena pasa al siguiente revisor.

## 0.13.0 (2026-10-14)

Esta versión es sobre lo que el revisor puede escribir, lo que `init` deja en
el repositorio y lo que el README muestra, todavía sobre residue/v0.4. La
consigna y el paquete dicen lo mismo sobre las escrituras: la suite se corre de
modo que no deje nada nuevo adentro del repositorio, ni siquiera un archivo que
git ignora, y una escritura que igual ocurrió se declara como hueco de
ejecución; el texto canónico del paquete cambió, así que el resultado de la
ronda pasa a v4, un resultado v3 se rechaza con la razón y el `prompt_hash` de
las tres compuertas cambia
([#88](https://github.com/NicolasRocchia/disensor/issues/88)). La receta
`claude` del catálogo arranca con `--safe-mode`, todavía sin verificar, y una
entrada registrada cuyo comando ya no coincide con la receta de hoy queda fuera
de la cadena con la instrucción de registrarla de nuevo
([#116](https://github.com/NicolasRocchia/disensor/issues/116)).
`reviewer suggest` imprime las notas de cada receta que encuentra
([#112](https://github.com/NicolasRocchia/disensor/issues/112), en parte), y
`round --check` y sus códigos de salida 0, 3 y 6 entran en lo que el README
promete, mientras las líneas que `round` imprime por la salida de error quedan
sin promesa ([#78](https://github.com/NicolasRocchia/disensor/issues/78)). El
runbook que escribe `init` pide el cronómetro del ciclo y define
`extra_time_sec`; el bloque pasa a v0.13 y los bloques con la marca v0.11
quedan registrados por hash para que `init --upgrade` los reemplace; el README
publica el costo medido del corpus hasta el 2026-10-12, con una prueba que
compara cada número con `.residue/`, y los ejemplos de `spec/` dejan de llevar
las cifras de tiempo y tokens que el corpus no tenía
([#114](https://github.com/NicolasRocchia/disensor/issues/114)). El runbook ya
no ejecuta a un revisor candidato antes de la aprobación del dueño, cierra con
la compuerta de la ronda y corre el gate con rango; la guía dice que `init`
instala el runbook y que su ronda manual es el camino sin runner;
`init --upgrade` pinea el workflow que quedó en el tag de la versión actual y,
sin red, un SHA con el comentario de esta versión se avisa en vez de informarse
como al día ([#121](https://github.com/NicolasRocchia/disensor/issues/121)).
Los dos README muestran un recorte de una declaración real de `.residue/` como
ejemplo del artefacto, con una prueba de que cada valor que se ve es el del
archivo, en su orden
([#111](https://github.com/NicolasRocchia/disensor/issues/111),
[#123](https://github.com/NicolasRocchia/disensor/pull/123)), y el límite
honesto cita el experimento Hide Pending: en 71 de 100 registros con un hueco
plantado el modelo declaró que no quedaba nada abierto, y 69 de esos 71 pasan
el fragmento de esquema y las cuatro reglas que corrió el experimento
([#137](https://github.com/NicolasRocchia/disensor/issues/137)). `tools/`
publica los tres scripts de medición detrás de los números citados en el grupo
comunitario del W3C
([#109](https://github.com/NicolasRocchia/disensor/pull/109)), el emisor de la
corrida de `.residue/` como reportes v0.1 y de los vectores MUST-FAIL como
registros 5.5 ([#119](https://github.com/NicolasRocchia/disensor/pull/119),
[#122](https://github.com/NicolasRocchia/disensor/pull/122),
[#124](https://github.com/NicolasRocchia/disensor/pull/124),
[#132](https://github.com/NicolasRocchia/disensor/pull/132)) y el script
detrás del caso 37/24 (10)
([#131](https://github.com/NicolasRocchia/disensor/pull/131)); `docs/notes/`
publica el protocolo, el corredor y el puntuador de la medición de lectura
pública, con las corridas de Codex y de Claude
([#110](https://github.com/NicolasRocchia/disensor/issues/110), en parte;
[#125](https://github.com/NicolasRocchia/disensor/issues/125)).

## 0.12.1 (2026-09-29)

Esta versión cambia solo redacción, todavía sobre residue/v0.4. El README, la
guía y el encabezado del bloque de residuo en el comentario del gate ya no
describen el registro como lo que el ciclo no pudo cerrar por sí mismo: un
hallazgo refutado con pruebas cierra y entra igual al residuo, así que esa frase
lo dejaba afuera. Ahora dicen lo que la ronda deja para que lo mire una persona,
y el ensayo de antecedentes pregunta qué quedó para que lo mire una persona en
vez de qué seguimos sin poder cerrar
([#104](https://github.com/NicolasRocchia/disensor/pull/104),
[#105](https://github.com/NicolasRocchia/disensor/pull/105)). El esquema v0.4
conserva sus descripciones tal como se publicaron: el recurso está congelado
por contenido y servido byte a byte en su `$id`, así que se corrigen en
residue/v0.5 y no en el lugar.

## 0.12.0 (2026-09-29)

Esta versión es sobre leer lo que disensor produjo, todavía sobre residue/v0.4.
La vista Abierto del informe agrupa por lo que cada fila le pide a quien lee y
no por el campo del esquema del que salió (espera una decisión, deuda anotada,
no se pudo ejecutar por el motivo declarado, sobre el revisor, descansa en un
juicio, y los riesgos que el dueño aceptó, plegados porque no piden nada), abre
con un digest y con lo que la última declaración dejó abierto, también cuando
no dejó nada, pliega un hallazgo en el ítem de residuo que lo referencia, y la
línea que imprimen el gate y el comando dice el mismo digest
([#95](https://github.com/NicolasRocchia/disensor/pull/95)). Una quinta vista,
Tablero, es para quien coordina y no para quien revisa: decisiones esperando y
desde cuándo, riesgos aceptados, deudas, lo que las declaraciones dicen de cómo
se hizo cada revisión, declaraciones por semana, huecos de ejecución por motivo
y lo que la vista no puede decir; el ancla `#tablero` la abre y Abierto sigue
siendo la primera vista
([#97](https://github.com/NicolasRocchia/disensor/issues/97),
[#99](https://github.com/NicolasRocchia/disensor/pull/99)). La misma vista
recorre la rama: de los merges desde el commit que trajo la primera declaración
válida, cuáles exigían revisión según la política de la punta y no traen una
declaración que el gate admita, juzgados con las mismas funciones del gate (las
comprobaciones sobre una declaración que un PR agrega viven ahora en
`judge_artifact`, compartida por el gate y el recorrido, todas salvo G9) y con
el motivo del gate en cada fila; mide declaraciones, no corridas del gate, y
`disensor report` gana `--branch` y `--config`
([#101](https://github.com/NicolasRocchia/disensor/pull/101)). `disensor round`
mide el tiempo de pared del revisor y `new --round` lo lleva como
`reviewer_seconds` en la extensión `dev.disensor.round`; las guías nombran
`extra_time_sec` como el ciclo de punta a punta y dicen que `token_cost` queda a
mano ([#98](https://github.com/NicolasRocchia/disensor/issues/98)). La regla de
la consigna contra instrucciones en el material distingue a su destinatario, la
entrega de la ronda dice que la receta no carga los archivos de instrucciones
del checkout, y la guía dice cómo refutar el falso positivo de un revisor que
reporta los archivos del harness como una inyección
([#91](https://github.com/NicolasRocchia/disensor/issues/91)). El README y la
página de PyPI ponen el residuo primero y conservan el vocabulario de los
revisores para quien busca
([#94](https://github.com/NicolasRocchia/disensor/pull/94)).

## 0.11.0 (2026-09-24)

Esta versión endurece lo que disensor hace en la máquina que lo corre y lo que
muestra el comentario del pull request, todavía sobre residue/v0.4. El
comentario del gate y el resumen del job muestran el texto de cada declaración
como se escribió: GitHub ya no lo lee como markdown, así que una declaración no
puede traer énfasis, un enlace que dice algo distinto de su destino, una fórmula
ni un comentario HTML que esconda texto, y `evidence.link` muestra su destino
([#85](https://github.com/NicolasRocchia/disensor/issues/85)). `disensor round`
mira adónde van su informe y su resultado antes de correr a ningún revisor,
`--result -` escribe a la salida estándar, el informe ya no se pierde con el
directorio temporal de la ronda, y si algo falla después de la ronda el mensaje
dice dónde quedó el informe
([#80](https://github.com/NicolasRocchia/disensor/issues/80)). Los programas se
corren por ruta absoluta, git lee el repositorio sin reescribir su índice ni
consultar el monitor del sistema de archivos, y el README dice cómo correr
disensor sobre un checkout que no es de confianza
([#75](https://github.com/NicolasRocchia/disensor/issues/75),
[#77](https://github.com/NicolasRocchia/disensor/issues/77),
[#76](https://github.com/NicolasRocchia/disensor/issues/76)). `disensor new` e
`init` escriben LF, y un archivo que ya existe conserva sus finales de línea
([#82](https://github.com/NicolasRocchia/disensor/issues/82)). El `pack_hash` de
una ronda es canónico, así que se puede recomputar lejos de la máquina que
corrió la ronda, y el resultado de la ronda pasa a v2
([#73](https://github.com/NicolasRocchia/disensor/issues/73), fase 1). La guía,
el runbook y la sección de `CLAUDE.md` dicen que el consentimiento para mandar
material fuera de la máquina lo da el dueño, e `init --upgrade` reconoce todos
los bloques que escribió la 0.9
([#84](https://github.com/NicolasRocchia/disensor/issues/84), opción 3). El
diario de releases sale del README a este archivo, y el README dice cómo correr
el gate fuera de GitHub
([#68](https://github.com/NicolasRocchia/disensor/issues/68),
[#72](https://github.com/NicolasRocchia/disensor/issues/72)). `tools/` publica
el emisor de los 42 objetos de evidencia reportados al grupo comunitario de la
W3C ([#67](https://github.com/NicolasRocchia/disensor/pull/67)), y el censo de
`gap_reason` que mide el alcance de residue/v0.5
([#83](https://github.com/NicolasRocchia/disensor/pull/83)).

## 0.10.0 (2026-09-16)

Esta versión suma `disensor report`: un solo archivo HTML autocontenido que lee
todas las declaraciones del repositorio y contesta qué quedó abierto (declarado
abierto en una fecha, sin evidencia posterior de cierre, porque el artefacto no
tiene un campo de cierre), cada declaración con su residuo primero, el corpus
tal como se declaró, y los hallazgos críticos y mayores que cambiaron el código.
Lee sin validar, no carga nada de la red y es una función pura de las
declaraciones: dos corridas sobre el mismo commit dan bytes idénticos. Nadie lo
tipea: cuando `disensor gate` llega a un veredicto verde escribe
`informe-residuo.html` en la raíz del repositorio desde los objetos git que
juzgó, sólo si git ignora el archivo, y `disensor init` deja esa línea en
`.gitignore`.

## 0.9.6 (2026-09-08)

Esta versión arregla el comentario del gate para las dos clases de revisor que
sumó v0.4: una declaración con `reviewer_correlation` o
`reviewer_hardening_gap`, que R11 y R12 exigen cuando un revisor se declara con
independencia degradada o endurecimiento sin verificar, validaba y después hacía
abortar al gate con un `KeyError` al renderizar el comentario, también con
`--no-comment`, así que el modo degradado que v0.4 volvió declarable rompía el
gate la primera vez que alguien lo declaraba de verdad
([#56](https://github.com/NicolasRocchia/disensor/issues/56)). El comentario
ahora nombra las dos clases y al revisor del que habla cada ítem, junto al
hallazgo cuando lo hay, y un test mantiene la tabla del render igual al enum del
esquema. La línea de apertura y el resumen de PyPI dicen qué es con el
vocabulario que la gente busca (revisión adversarial de código con IA, entre
modelos de familias distintas, con declaración de residuo), y una sección nueva
dice cómo se relaciona con otros enfoques y con Adversarial Review (arXiv
2608.18167).

## 0.9.5 (2026-08-31)

Esta versión lleva lo que dejó la primera reproducción independiente: un lector
externo clonó el tag v0.9.4, verificó los hashes congelados y corrió las dos
implementaciones en frío, sin divergencias, y encontró que el README del plano
de evidencia declaraba un conteo viejo. El conteo queda corregido con su
desglose dicho en voz alta, toda afirmación numérica de estos documentos se
compara ahora en CI contra la cosa que cuenta, `disensor --version` existe
(salía con un error de uso, y el primer comando que tipea un desconocido merece
algo mejor), y el literal de versión queda atado a los metadatos del paquete por
prueba.

## 0.9.4 (2026-08-29)

Esta versión cierra residue/v0.4: el port TypeScript valida v0.2, v0.3 y v0.4,
así que el claim de dos implementaciones independientes cubre la versión que el
CLI emite; la conformidad corre 89 vectores en tres suites más 28 casos
compartidos que fijan la forma de un identificador de esquema y qué reglas
alcanzan a qué declaración, y falla cuando una versión conocida no tiene
vectores que la declaren; el piso de nivel A se aplica; la integridad
referencial entra como R13, con guarda para que no alcance a las versiones
congeladas; los recursos congelados quedan verificados por contenido y no sólo
por nombre; y qué reglas alcanzan a qué declaración dejó de depender del orden
en que están escritas las líneas.

## 0.9.3 (2026-08-27)

Esta versión deja escrito cuándo sube el pin de la propia Action del gate: viaja
en el próximo PR de trabajo real, salvo que la release corrija la seguridad del
gate o cambie la versión del esquema, y dice en voz alta que eso es una
convención y no un control
([#17](https://github.com/NicolasRocchia/disensor/issues/17)).

## 0.9.2 (2026-08-27)

Esta versión hace que `disensor guide` entregue el runbook del evento además de
la guía de llenado del artefacto, así un agente que no es Claude Code recibe de
un solo comando el mismo material que lleva la skill de Claude Code, que es lo
que la documentación venía prometiendo desde que la ronda pasó a estar
orquestada ([#30](https://github.com/NicolasRocchia/disensor/issues/30)).
`--runbook` y `--filling` piden una de las dos, y `init --only-skill` escribe
ese runbook sin la sección de `CLAUDE.md`, para un repositorio cuyo agente es
otro.

## 0.9.0 (2026-08-27)

Esta versión orquesta la ronda: `disensor round` empaqueta el material, corre un
revisor registrado en tu máquina, captura el informe y ancla el resultado a los
commits que efectivamente revisó, y `disensor new --round` construye la
declaración desde ahí. Cualquier asistente con línea de comandos puede ser el
revisor; el catálogo empaquetado es un atajo, no la lista de lo permitido.
residue/v0.4 vuelve declarable una ronda sin segunda familia de modelo como el
modo degradado que es, en vez de imposible de declarar, y cada versión del
esquema se valida con sus propias reglas. `disensor init --upgrade` lleva una
instalación anterior a este procedimiento sin tocar nada que hayas editado.

## 0.7.0 (2026-08-24)

Esta versión agrega `disensor pin`, que congela la Action al SHA de commit de su
tag de release.

## 0.6.4 (2026-08-23)

Esta versión vuelve alcanzable la guía castellana empaquetada, con
`disensor guide --lang es`.

## 0.6.3 (2026-08-21)

Desde la v0.6.3 la documentación larga es bilingüe: `README.md` es el inglés que
renderiza PyPI, `README.es.md` es el castellano, y la guía de llenado viaja en
los dos idiomas.

## 0.6.1 (2026-08-20)

Las releases se publican a PyPI vía Trusted Publishing (OIDC, `release.yml`):
sin tokens en ninguna máquina.

## 0.6.0 (2026-08-15)

El paso a residue/v0.3 endurece tres puntos del artefacto, cerrando los issues
[#5](https://github.com/NicolasRocchia/disensor/issues/5),
[#7](https://github.com/NicolasRocchia/disensor/issues/7) y
[#8](https://github.com/NicolasRocchia/disensor/issues/8). Ver
["Migración de v0.2 a v0.3"](README.es.md#migración-del-esquema-residuev02-a-residuev03).

## 0.5.0 (2026-08-13)

La v0.5 entrega la consigna adversarial empaquetada con hash reproducible.

## 0.4.0 (2026-08-13)

La v0.4 reescribió el gate para que derive el alcance del PR de git (ver
["Qué hace cumplir el gate"](README.es.md#qué-hace-cumplir-el-gate)).

## 0.2.0 (2026-08-11)

Decisión cerrada en v0.2: claves del esquema y CLI en inglés (el español queda
como alias en la CLI y como idioma de la documentación).

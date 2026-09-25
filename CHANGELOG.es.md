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

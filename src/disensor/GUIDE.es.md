# Cómo se llena una declaración de residuo (residue/v0.3)

> **Traducción.** La versión normativa es [`GUIDE.md`](GUIDE.md), en inglés, que
> es la que imprime `disensor guide` y la que `disensor init` instala como
> skill. Si las dos difieren, manda la inglesa: dos guías normativas harían que
> el mismo evento se llenara distinto según el idioma del repositorio.

Esta es la traducción castellana de la guía para llenar el artefacto que
`disensor new` crea bajo `.residue/`. Viaja adentro del paquete junto a la
inglesa, que es la que `disensor guide` imprime y la que `disensor init`
instala como skill de Claude Code.

El validador (`disensor validate`) y el gate de CI hacen cumplir buena parte de
lo que está descrito acá, pero no todo: donde hay una regla, esta guía la
nombra. Lo que no se nombra es obligación del método y nadie lo verifica por
vos. Llenar el artefacto bien la primera vez sale más barato que iterar contra
sus errores.

## La ronda, y después la declaración

1. `disensor prompt --gate <plan|diff|architecture>` imprime la consigna adversarial.
   Entregásela, junto con el plan o el diff, a un revisor de OTRA familia de
   modelo. Con un plan gratuito alcanza. La misma familia que el generador no
   cuenta, y la regla R4 rechaza la declaración si lo intentás.
2. Verificá cada hallazgo contra el código real antes de aceptarlo. El revisor
   está decorrelacionado, no acertado, y un hallazgo sin verificar no es un
   hallazgo.
3. `disensor new --gate <plan|diff|architecture> --level <A|B|C>` crea la plantilla,
   prellenada con lo que git sabe (repositorio, commits, fecha, uuid).
4. Completá cada marcador `FILL_IN` y los hallazgos de la ronda. La plantilla no
   valida mientras queden marcadores: es a propósito.
5. `disensor validate .residue/<id>.json`. Corregí hasta que imprima VALID.
6. Commiteá el artefacto solo: `docs(residuo): declara evento <id-corto>`. Nunca
   mezclado con cambios de código.

Declará lo que pasó, no lo que debería haber pasado. Un evento sin hallazgos y
con una declaración expresa de ausencia es un dato válido, no un fracaso.

## Las tres compuertas

`event.gate` dice qué se sometió a revisión, y cambia lo que las reglas exigen
después. Cada una tiene su propia consigna empaquetada.

- **`plan`**: el plan antes de implementar. El momento más barato para
  equivocarse. Un hallazgo `incorporated` acá puede cerrar con un
  `fix_verification` de tipo `pending_in_diff_gate`, porque la corrección
  todavía no está escrita.
- **`diff`**: el cambio antes de mergear. Es la que el gate de CI exige para
  código, y la única donde `incorporated` requiere que la corrección haya
  pasado su propia verificación (`diff_gate` o `specific_test`, regla R7).
  Aplicar la corrección no es cerrar el hallazgo; verificarla sí.
- **`architecture`**: una decisión de diseño o una comparación de alternativas,
  cuando la pregunta no es si el código está bien sino si la forma lo está.
  Mismo contrato que las otras; lo que cambia es la consigna y el horizonte de
  los hallazgos.

Un repositorio declara en su configuración qué compuerta acepta para qué rutas.
Por defecto todo exige `diff`.

## Actores

- `generator`: el asistente que produjo el plan o el diff. `family` es su
  familia de modelo (anthropic, openai, google, meta, mistral, other).
- `reviewers[]`: los asistentes que atacan. Cada uno necesita `reviewer_id` (r1,
  r2...), `family`, `model` y `confinement`. La regla R4 rechaza cualquier
  revisor cuya familia sea igual a la del generador: la decorrelación es el
  punto del método, no una opción.
- `reviewers[].prompt_hash`: el hash de la consigna adversarial que recibió el
  revisor. Si usaste la empaquetada, es
  `disensor prompt --gate <plan|diff|architecture> --hash`, y cualquiera puede recomputar ese
  valor desde la misma versión para ver qué pediste realmente. Si escribiste o
  editaste la tuya, hasheá el archivo que usaste de verdad con
  `disensor hash <brief-file>`. En cualquiera de los dos casos, pegá el
  `sha256:...` completo.
- `confinement.mode`: cómo se garantizó que el revisor solo lee (permissions,
  sandbox, read_only_by_instruction, no_confinement). Declará el modo real; el
  gate hace visibles los huecos en lugar de taparlos.
- `confinement.verified`: true SOLO si corriste `git status` después de la
  corrida del revisor y el árbol estaba limpio. Si no, dejalo en false.
- `human_arbiter.present`: tiene que ser true; un evento sin árbitro humano no
  cumple el protocolo (R0).

La delegación adentro de un actor es invisible para este contrato, a propósito.
Un generador o un revisor puede abrirse en agentes, subagentes, scripts o
cualquier otra herramienta interna: el artefacto declara principales, no
procesos, y el principal responde por la salida delegada como si fuera trabajo
propio. Ninguna regla inspecciona cómo un actor produjo lo que firmó, y ninguna
debería; la verificación de confinamiento sobre el working tree ya cubre lo que
los procesos internos del actor hicieron ahí, y `extensions` es el lugar para
declarar la delegación interna cuando revelarla importa. Viene con un matiz
honesto: R4 decorrelaciona los principales declarados. Un actor que
internamente se apoya en la misma familia que su contraparte mantiene la
declaración formalmente cierta mientras debilita la decorrelación estadística, y
la máquina no puede verlo. Pertenece al límite honesto del protocolo: el gate
lee declaraciones; el muestreo humano lee la realidad.

## Hallazgos

Una entrada por cada punto que levantó el revisor. Campos: `id` (h1, h2...),
`origin` (el reviewer_id que lo produjo), `severity` (critical, major, minor,
info), `title`, `description`, `location` (solo en el perfil completo), y:

- `verification.against`: contra qué contrastó el generador el hallazgo antes de
  aceptarlo o refutarlo: `repository` (código, configuración, contratos),
  `execution` (correr tests o el programa), `external_source` (literatura,
  especificaciones de terceros, advisories, documentación externa) o `none`. No
  le creas al revisor: verificá y después decidí. Elegí la clase que la
  verificación tuvo de verdad. Si ninguna es cierta de lo que hiciste, eso es un
  defecto de este vocabulario y hay que reportarlo, no aproximarlo.
- `final_state`, el resultado terminal. Tabla de decisión:
  - `incorporated`: el hallazgo cambió el plan o el código. En la compuerta de
    diff TENÉS que agregar `fix_verification` de tipo `diff_gate` o
    `specific_test` (R7); `pending_in_diff_gate` no es legal ahí. R7 dispara
    solo en la compuerta de diff, así que plan y architecture lo aceptan. Si el remedio que propuso el revisor estaba mal y vos lo
    corregiste, registrá `remedy_adjustment`.
  - `debt_recorded`: válido, diferido; requiere `debt_id` (esquema).
  - `owner_decision`: válido, el dueño cambió el alcance, el comportamiento o
    aceptó el riesgo; requiere `risk_record` (esquema).
  - `refuted_verifiable`: falso positivo con prueba. Es el estado que cierra un
    hallazgo **sin tocar el código**, así que es el que más resistencia merece
    de tu parte. Requiere `evidence` con contenido material (`text`, `link` o
    `hash`; ni el objeto vacío ni un string en blanco cuentan, y `text` necesita
    al menos 10 caracteres) y un
    `verification.against` distinto de `none`: refutar algo sin haber verificado
    nada es una contradicción, no una refutación. Anotá qué establece la
    evidencia y qué no. "El test pasó" puede ser plenamente verificable mientras
    "por lo tanto el defecto no existe" no se deduce de eso; cuando sea el caso,
    decilo en `verification.detail`.
  - `refuted_interpretive`: falso positivo por juicio; TIENE que aparecer además
    como ítem de residuo (R1) con `requires_human_attention: true` (R8).
  - `escalated_open`: todavía sin decisión; TIENE que aparecer además como ítem
    de residuo (R1).

## Residuo

El corazón de la declaración: lo que el ciclo no pudo cerrar por sí mismo. O
`items` o la ausencia expresa, nunca un campo vacío.

- `items[]`: `id` (r1, r2...), `class`, `finding_ref` cuando viene de un
  hallazgo, `requires_human_attention`.
  - `escalation_without_decision`: de cada hallazgo `escalated_open`.
  - `principal_refutation`: de cada hallazgo refutado; agregá `refutation_type`
    (`verifiable` o `interpretive`; el interpretativo fuerza
    `requires_human_attention: true`).
  - `execution_gap`: comportamiento que la ejecución no pudo arbitrar; agregá
    `gap_reason`. En Nivel A un gap de ejecución bloquea el merge hasta que un
    referente técnico lo acepte por escrito (`lead_acceptance`, R5).
- Ausencia: `"declared_absence": true` más `declaration`, mínimo 30 caracteres
  de texto concreto. Los marcadores genéricos (none, n/a, all resolved,
  ninguno, todo resuelto...) los rechaza R2. Su lista es cerrada y cubre inglés
  y castellano: un marcador equivalente en otro idioma pasa.

## Métricas

`counts` tiene que cerrar exacto contra la lista de hallazgos (R6): cada balde
de `valid.*` y de `false_positives.*` es igual a la cantidad de hallazgos en ese
estado, `escalated_open` lo mismo, y `total_findings` es el largo de la lista.
Contá, no estimes.

En el perfil `minimized` la lista de hallazgos puede faltar. Ahí los conteos
quedan solos y R6 no tiene contra qué compararlos, que es una razón más para
contar en vez de estimar.

## Perfil minimizado

R9 remueve el texto libre que cubre: nada de títulos, descripciones ni
ubicaciones en los hallazgos; nada de descripciones en los ítems; evidencia solo
como `hash`; y rechaza un `repository` que empiece con `http`. Ojo con el
literal: ese chequeo no atrapa `HTTPS://`, `ssh://`, `git://` ni
`git@host:repo`, que son localizadores en claro y hoy pasan.

**Angosta el canal de fuga; no lo cierra.** R9 no alcanza a todo string del
artefacto: `residue.declaration`, `event.pr`, `verification.detail`,
`human_arbiter.id` y `lead_acceptance`, entre otros, siguen admitiendo prosa
libre. `minimized` es una reducción de superficie, no la garantía de que no sale
nada del entorno.

`extensions` no está exento. En el perfil completo acepta cualquier cosa; en el
minimizado todo valor tiene que ser opaco (un hash `sha256:`, un número, un
booleano, `null`, o contenedores de esos) y toda clave tiene que tener forma de
identificador: un nombre, no un mensaje. El espacio de extensión no lo
interpretan las reglas a propósito, que es exactamente por qué el texto libre
estacionado ahí sale del entorno igual que en cualquier otro lugar al que el
perfil no llega.

## Mapa rápido de las etiquetas del validador

R0 falta el árbitro humano; R1 coherencia entre residuo y hallazgos; R2
marcadores genéricos o de plantilla; R3 ruta abreviada sobre casos protegidos;
R4 el revisor comparte la familia del generador; R5 gap de ejecución en Nivel A
sin aceptación del referente; R6 conteos que no cierran; R7 incorporado sin
corrección verificada en la compuerta de diff; R8 refutación interpretativa sin
atención humana; R9 fugas de texto en el perfil minimizado; R10 perfil completo
sin hallazgos; errores de forma del `schema` (campos requeridos que faltan,
enums equivocados, patrones mal).

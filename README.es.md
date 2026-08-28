# disensor

[![PyPI](https://img.shields.io/pypi/v/disensor)](https://pypi.org/project/disensor/)
[![CI](https://github.com/NicolasRocchia/disensor/actions/workflows/ci.yml/badge.svg)](https://github.com/NicolasRocchia/disensor/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/disensor)](https://pypi.org/project/disensor/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/NicolasRocchia/disensor/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21633495.svg)](https://doi.org/10.5281/zenodo.21633495)

Revisión adversarial de planes y código, con el residuo declarado.

*This document is also available [in English](https://github.com/NicolasRocchia/disensor/blob/main/README.md).*

Declaración de residuo de revisión adversarial, con validación y gate de CI. Implementación de referencia del artefacto definido a partir del método de **desacuerdo controlado**: un modelo genera, un modelo de otra familia ataca, el generador verifica cada hallazgo, y el ciclo termina cuando todo hallazgo quedó resuelto, refutado con evidencia o escalado a un humano.

El artefacto que este repo define y hace cumplir registra cómo terminó cada evento de revisión: los hallazgos con su estado terminal, y el **residuo**: lo que el ciclo no pudo cerrar por sí mismo y descansa sobre el juicio de alguien. La declaración lista residuo, no cobertura: dirige el escrutinio del revisor humano en lugar de leerse como sello de calidad.

Paper del método: Rocchia, N. (2026), *Desacuerdo controlado: revisión adversarial automatizada con un segundo asistente de código en el desarrollo de software*, DOI [10.5281/zenodo.21633495](https://doi.org/10.5281/zenodo.21633495).

## Qué hay acá

- `spec/residue.schema.json`: el esquema del artefacto (JSON Schema 2020-12), versión residue/v0.4. Las versiones superadas conservan su propio recurso congelado al lado.
- `spec/examples/`: tres artefactos de ejemplo, incluido un evento real anonimizado y el perfil minimizado sin texto libre.
- `src/disensor/`: paquete Python con el validador (reglas R0 a R10), el gate de CI (chequeos G1 a G9), el render del comentario de PR, el scaffolding de artefactos y el de repositorios (`init`), y la guía de llenado empaquetada (`GUIDE.md`).
- `action.yml`: GitHub Action compuesta, lista para usar.
- `docs/integracion-claude-code.md`: cómo el flujo real (Claude Code más un revisor de otra familia) emite el artefacto al cierre de cada evento.
- `docs/antecedentes.md`: dónde se ubica el método respecto de la literatura (residual doubt y defeaters, design rationale y su capture bottleneck, revisión adversarial multi-agente, governance runtimes, provenance de cadena de suministro), con el estado de verificación de cada referencia.

## Uso rápido

El paquete se instala una vez (global); cada repositorio se inicializa una vez:

```bash
pip install disensor        # o pipx install disensor, recomendado para CLIs

disensor init               # en la raíz del repo: config, CLAUDE.md, skill de llenado y workflow de CI
disensor pin                # la Action del workflow, congelada al SHA de commit del tag de la release

disensor reviewer suggest              # qué revisores tiene esta máquina, sin red
disensor round --gate diff --generator-family anthropic --base main --head HEAD --result ../result.json
disensor new --gate diff --level B --round ../result.json   # la declaración de esa ronda

disensor prompt --gate diff            # la consigna adversarial, para pegarle al revisor de otra familia
disensor pack --gate diff --base main --head HEAD          # el paquete completo, si manejás la ronda vos
disensor new --gate diff --level B     # plantilla prellenada en .residue/
disensor validate .residue/<id>.json   # schema + reglas R0 a R10
disensor gate --no-comment             # lo que va a correr CI, en local

disensor guide                         # la guía de llenado, para cualquier agente o humano
disensor guide --lang es               # la misma guía, en castellano
disensor prompt --gate diff --hash     # el sha256: de la consigna empaquetada, que es lo que pide prompt_hash
disensor hash consigna.md              # o el de la tuya, si la escribiste vos
```

La consigna viaja adentro del paquete, así que su hash es reproducible: cualquiera puede recomputarlo desde la misma versión y ver qué se le pidió realmente al revisor. Si la editás, el hash cambia y el artefacto declara que se usó otra consigna, que es justamente para lo que sirve el campo.

## Probarlo sin tocar tu CI

Hay dos modos y conviene no mezclarlos. Para **probarlo**, no hace falta workflow, ni required checks, ni permisos de organización: el gate corre igual en tu máquina y dice exactamente lo mismo que diría en CI.

```bash
disensor init --no-workflow          # config, CLAUDE.md y skill; sin tocar .github/
disensor prompt --gate diff          # la consigna, al revisor de otra familia
disensor new --gate diff --level B   # y llenás la declaración con lo que pasó
disensor validate .residue/<id>.json
disensor gate --no-comment --base <base-sha> --head HEAD
```

Recién cuando quieras que **haga cumplir**, corré `disensor init` completo (que escribe el workflow) y aplicá los requisitos de despliegue de más abajo. Antes de eso es una herramienta que te dice cómo te iría; después es un control que bloquea.

Los subcomandos y flags de la v0.1 en español (`nuevo`, `validar`, `--compuerta`, `--nivel`, `--directorio`, `--sin-comentario`) siguen funcionando como alias.

`disensor init` escribe, en forma idempotente, el `disensor.config.json` (el nivel viaja con el código, en un archivo versionado), la sección de cierre de evento en `CLAUDE.md`, la skill de Claude Code con el runbook del evento (`.claude/skills/disensor/SKILL.md`, cargada a demanda al cerrar cada ronda) y el workflow del gate; lo que ya existe se respeta y se informa. El principio es que después de `pip install disensor` y `disensor init` el usuario no toque nada a mano: Claude sabe cuándo (CLAUDE.md) y cómo (la skill), cualquier otro agente recibe lo mismo de `disensor guide`, que imprime ese runbook y la guía de llenado, y el CI hace cumplir el resultado. Config resultante:

```json
{
  "criticality_level": "B",
  "level_A_enabled": false
}
```

Y el workflow (ver `docs/ejemplo-workflow.yml`):

```yaml
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: NicolasRocchia/disensor@v0.9.3
```

El gate valida las declaraciones que **el PR agrega**, aplica la política y publica el resultado como comentario (se actualiza en el lugar en cada push). Todo lo que decide sale de objetos de git en el rango `merge-base..head`, nunca del working tree: en un evento `pull_request` el checkout deja el merge commit sintético mientras `head.sha` apunta al head real, así que leer del disco clasificaría un árbol y validaría otro.

## La ronda orquestada

La ronda era la parte que se hacía a mano: empaquetar el material, entregárselo
a otro asistente, traer el informe, acordarse de mirar el árbol después.
`disensor round` hace la mitad mecánica, así que nunca se copia y pega material
entre modelos.

```bash
disensor reviewer suggest          # qué tiene esta máquina, sin red
disensor reviewer add codex --yes  # registrarlo, una vez por máquina

disensor round --gate diff --generator-family anthropic \
  --base main --head HEAD --result ../result.json
disensor new --gate diff --level B --round ../result.json
```

**Cualquier asistente puede ser el revisor.** Nosotros corremos Claude Code con
Codex atacando porque es lo que tenemos; la herramienta no está atada a ninguno
de los dos. Sirve cualquier línea de comandos que reciba un texto y devuelva un
texto: el CLI de otro proveedor, un modelo local por Ollama, lo que ya estés
pagando. El catálogo empaquetado es un atajo para los casos que ya probamos, no
la lista de lo que está permitido. Si el tuyo no está, tu asistente lee su
`--help`, propone la entrada y vos la aprobás una vez.

Dos cosas que conviene saber sobre esa aprobación. Los revisores viven en tu
máquina (`~/.disensor/reviewers.json`) y nunca en el repositorio: una entrada es
código ejecutable, y un PR que pudiera agregar una correría comandos en la
máquina de quien lo revise. Y lo que propone tu asistente no se registra hasta
que digas que sí, porque un repositorio puede traer instrucciones dirigidas a tu
asistente, y registrar un ejecutable que después va a recibir tu código privado
es una decisión tuya, no suya.

**Qué corre solo y dónde aparecés vos.** El runner le pregunta a la política si
hace falta una ronda (un cambio que solo toca rutas exentas no gasta un token),
se niega a correr con el árbol sucio, elige el revisor más independiente
disponible, lo ejecuta, captura el informe y emite un resultado anclado a los
commits exactos que se revisaron. Nunca lee el informe: juzgar lo que dijo el
revisor es trabajo de tu asistente. Vos aparecés cuando hay que consentir que el
material salga de tu máquina, cuando un riesgo necesita dueño, cuando algo se
escala sin resolver, y en el PR.

**Cuando no hay una segunda familia.** El método quiere un revisor de otra
familia de modelo, y eso es lo que la política sigue exigiendo en nivel A. Por
debajo, una ronda con el mismo modelo y sin contexto es un modo degradado
declarable: la declaración registra la independencia que de hecho tuvo, por qué
se conformó con menos, y un ítem de residuo que dice que los errores que el
modelo comparte consigo mismo no los cubrió esa ronda. Peor que lo real, e
infinitamente mejor que no poder declarar lo que pasó.

## Qué hace cumplir el gate

Por artefacto (reglas R0 a R10): coherencia entre hallazgos y residuo, conteos que cierran, decorrelación de familias entre generador y revisor, evidencia material obligatoria en refutaciones verificables (`text`, `link` o `hash`) contra un blanco verificable (`verification.against` distinto de `none`), atención humana obligatoria en refutaciones interpretativas, corrección verificada antes de cerrar un hallazgo en compuerta de diff, rechazo de marcadores genéricos (en inglés y en español), y perfil minimizado con el texto libre que R9 cubre removido.

Por artefacto, contra el PR: nivel igual al declarado del repositorio (G2), Nivel A bloqueado mientras la gobernanza no esté validada (G3), política de confinamiento del revisor por nivel (G4), y pertenencia al PR del commit revisado (G5), que para la compuerta de diff exige además `base_commit`, porque una revisión de diff identifica el par (base revisada, head revisada) y no un head suelto.

Por PR:

- **G1**: si el PR toca rutas que requieren revisión, agrega al menos una declaración válida.
- **G6, cobertura**: cada ruta cambiada está cubierta por una declaración cuya compuerta la política de alcance acepta para esa ruta, y que **califica** para ella, o sea que la ruta no cambió entre el commit revisado y el head. Una declaración rancia no cubre nada.
- **G7, testigo de integración**: alguna declaración vio el árbol final completo. La cobertura ruta por ruta no alcanza: dos ramas laterales revisadas por separado y después fusionadas cubren entre las dos todas las rutas mientras nadie revisó la integración.
- **G8, la evidencia es de solo agregar**: un PR no puede modificar, borrar ni renombrar declaraciones que ya estaban, ni reutilizar un `event_id` existente.
- **G9, lo nuevo declara la versión vigente**: una declaración que el PR agrega tiene que declarar `residue/v0.4`. Las versiones superadas se siguen leyendo para que la historia no se reescriba; esa legibilidad no es un permiso para seguir emitiendo bajo las reglas más débiles. El plano de evidencia aplica el mismo criterio en la ingesta.

El gate **falla cerrado**: si no puede resolver el rango del PR, no da verde. Un control de cumplimiento que no puede decidir, no aprueba.

Límite honesto, heredado del protocolo: la máquina detecta el campo vacío y el marcador genérico, no la declaración falsa. El muestreo humano de PR cerrados sigue siendo la única defensa real contra el cumplimiento cosmético.

## Política de alcance

Qué compuerta se acepta para cada ruta se declara en el config, y **se lee siempre de la punta actual de la rama destino**, nunca del checkout del PR. Del destino y no del merge-base, que es otra pregunta: el merge-base es tan viejo como la rama, así que una rama creada antes de que el repositorio endureciera su política arrastraría la vieja. El alcance del PR se mide contra el merge-base; la política que rige es la que el destino tiene hoy. Por eso un PR que cambia la política se juzga con la política anterior, que es lo correcto y además evita el bloqueo mutuo del diseño ingenuo, donde el PR que afloja la configuración queda rechazado por la regla que quiere cambiar y no hay transición posible.

```json
{
  "criticality_level": "B",
  "level_A_enabled": false,
  "gate": {
    "required": true,
    "scope": [
      { "paths": ["docs/adr/**"], "accepts": ["architecture", "diff"] },
      { "paths": ["CHANGELOG.md"], "accepts": [] },
      { "paths": ["**"], "accepts": ["diff"] }
    ]
  }
}
```

Gana la primera entrada que matchea. `accepts: []` es una exención explícita, que es la salida gobernada para changelogs o PRs automatizados. Los patrones están anclados a la raíz, `*` no cruza `/`, `**` matchea cero o más segmentos completos, y el match es **sensible a mayúsculas byte a byte** para que la misma política signifique lo mismo en cualquier runner. Una ruta que no matchea nada exige `diff`: la ausencia de política no es un permiso.

**Piso no relajable**: la ruta efectiva de configuración, `.github/workflows/**` y el directorio de evidencia siempre exigen `diff`, diga lo que diga `scope`. Sin ese piso, una política de aspecto inocente como `**/*.yml` con `architecture` rebajaría los workflows, que son la fuente del propio control.

## Requisitos de despliegue

Esto es requisito, no sugerencia. El gate corre dentro del workflow que audita, así que hay una frontera que ningún código suyo puede cruzar y que resuelve la plataforma:

- **Required check estricto** (o merge queue) sobre `pull_request`, para que el check tenga que corresponder al último head.
- **CODEOWNERS** sobre la ruta efectiva de configuración (puede no llamarse `disensor.config.json` si se usa `--config`) y sobre `.github/workflows/`.
- **Ruleset o required workflow de organización**, definido fuera del repositorio auditado.
- **Pin de la Action por SHA**, no por tag: un tag es movible y no es raíz de confianza. `disensor init` resuelve el tag de la versión instalada al commit al que apunta y escribe el workflow ya congelado; sin red al momento del init el tag queda y `disensor pin` termina el trabajo. El comando resuelve los tags anotados al commit que envuelven, nunca al objeto tag, que es la trampa clásica de hacerlo a mano. La documentación de este repo sigue usando el tag, porque documenta qué versión corresponde; el SHA congelado lo produce quien despliega.
- **Bootstrap**: el primer PR que agrega el config y el workflow no puede convertirse a sí mismo en raíz de confianza. La activación inicial es un paso administrativo, previo a que el gate signifique algo.
- **Cuándo sube el pin**: el workflow está en el piso no relajable, así que subir el pin por PR cuesta una ronda adversarial por un cambio cuya corrección un `git rev-parse` verifica mejor que cualquier modelo. La convención de este repositorio es que el pin nuevo **viaje en el próximo PR de trabajo real**, con su declaración, en vez de ir en un PR propio. **Excepción**: si la release corrige la seguridad del gate o cambia la versión del esquema, el pin se sube de inmediato, porque la ventana en que el repositorio se juzga con la versión anterior deja de ser inocua: un gate viejo no conoce el contrato nuevo y rechaza lo que el CLI recién publicado emite. Es una convención, no un control: mientras la rama no exija pull request con bypass deshabilitado también para administradores, nada impide empujar el pin directo ([#17](https://github.com/NicolasRocchia/disensor/issues/17)).

Límite explícito: leer la política de la base convierte un bypass de un paso en uno de dos, no lo elimina. Quien pueda mergear una relajación la usa en el PR siguiente. Y nada de esto protege contra un workflow modificado, salteado o sustituido. Eso solo lo resuelve la plataforma.

## Qué no hace

El gate de CI no corre modelos, no pide claves de API y no manda código a ningún servicio: valida un JSON que ya está versionado en el repo. Correr la ronda es opcional y no sale de tu máquina: `disensor round` maneja un CLI de revisor que registraste vos, y un revisor en la nube necesita consentimiento con alcance antes de que salga material. El perfil `minimized` del artefacto está pensado para ambientes donde el texto de los hallazgos no puede salir del entorno.

En el perfil `minimized`, R9 remueve los campos del hallazgo que el protocolo define, el `text` y el `link` de toda evidencia, la `description` del ítem de residuo y un `repository` que empiece con `http`. El esquema exige además que todo valor bajo `extensions` sea opaco (un hash `sha256:`, un número, un booleano, `null` o contenedores de esos) y que toda clave tenga forma de identificador: un nombre, no un mensaje.

**El perfil angosta el canal de fuga; no lo cierra.** R9 no alcanza a todo string del artefacto. `residue.declaration`, `event.pr`, `verification.detail`, `human_arbiter.id` y `lead_acceptance` son algunos de los campos que siguen admitiendo prosa libre, y la lista no pretende ser exhaustiva: la superficie vigente está en el esquema. Ojo con que un `repository` hasheado no sirve de nada si `event.pr` lleva la URL. El propio esquema lo dice del espacio de extensión: una clave con forma de identificador todavía puede llevar un mensaje. `minimized` es una reducción de superficie, no la garantía de que no sale nada.

## Conformidad entre implementaciones

`spec/vectors/` contiene los vectores de conformidad: 31 artefactos con su veredicto esperado (válido o no, y las etiquetas de regla que deben dispararse). Toda implementación del validador tiene que pasarlos idénticos: la referencia en Python los corre en la suite (`tests/test_vectors.py`) y el port TypeScript del plano de evidencia los corre con `npm run conformidad`. Se comparan etiquetas, no mensajes. Los vectores se regeneran con `python -m disensor.vectors spec/vectors`.

Cada vector se valida con el schema de la versión que declara. El port TypeScript implementa las reglas de **v0.2 y v0.3**: ante un artefacto v0.4 lo dice y se niega, en vez de devolver un veredicto sin haber corrido las reglas que esa versión agregó. Así que el claim de dos implementaciones independientes cubre hoy hasta v0.3; la referencia en Python es la única que valida v0.4 ([#29](https://github.com/NicolasRocchia/disensor/issues/29)).

`plano-evidencia/` contiene el Worker de ingesta (Cloudflare Workers más D1) con el port TypeScript del validador y el recibo de integridad de solo agregado. Ver su README para el estado de verificación y el despliegue.

## Glosario ES-EN

La terminología del paper es en español; el contrato (claves y enums del esquema, CLI) es en inglés desde v0.2. Equivalencias principales:

| Paper (ES) | Esquema/CLI (EN) |
|---|---|
| residuo | residue |
| hallazgo | finding |
| compuerta (plan, diff, arquitectura) | gate (plan, diff, architecture) |
| nivel de criticidad | criticality_level |
| perfil completo / minimizado | profile full / minimized |
| actores: generador, revisores, árbitro humano | actors: generator, reviewers, human_arbiter |
| familia (de modelo) | family |
| confinamiento (permisos, sandbox, solo lectura por instrucción, sin confinamiento) | confinement (permissions, sandbox, read_only_by_instruction, no_confinement) |
| consigna (hash de la consigna adversarial) | prompt_hash |
| estado final: incorporado, deuda registrada, decisión del dueño, refutado verificable, refutado interpretativo, escalado abierto | final_state: incorporated, debt_recorded, owner_decision, refuted_verifiable, refuted_interpretive, escalated_open |
| clases de residuo: escalado sin decisión, refutación del principal, gap de ejecución | residue classes: escalation_without_decision, principal_refutation, execution_gap |
| ruta abreviada / casos protegidos | abbreviated_path / protected_cases_touched |
| verificación de la corrección | fix_verification |
| aceptación de referente | lead_acceptance |
| ausencia declarada / declaración | declared_absence / declaration |
| métricas: conteos, válidos, falsos positivos | metrics: counts, valid, false_positives |

Migración desde v0.1: renombrar `.residuo/` a `.residue/`, las claves del config (`nivel_criticidad` a `criticality_level`, `nivel_A_habilitado` a `level_A_enabled`) y las claves de los artefactos según el glosario. El validador reconoce artefactos v0.1 y lo dice explícitamente; el gate rechaza en voz alta un config con claves viejas en lugar de aplicar defaults en silencio.

## Migración del esquema: residue/v0.2 a residue/v0.3

Cuidado con la ambigüedad: esta sección habla de la versión **del esquema**; la siguiente habla de versiones **del paquete**. Son dos numeraciones distintas.

La v0.3 no renombra ni agrega claves. Endurece los puntos donde la garantía declarada era más fuerte que la implementada (tres detectados antes de la ronda y dos que la propia ronda adversarial de v0.3 agregó), y suma un valor a un enum:

| Antes valía | Ahora se rechaza | Por qué |
|---|---|---|
| `refuted_verifiable` con `evidence: {}` | El objeto de evidencia tiene que traer `text`, `link` o `hash` | v0.2 exigía la presencia del objeto, no su contenido: se podía cerrar un hallazgo sin tocar el código declarando evidencia vacía ([#5](https://github.com/NicolasRocchia/disensor/issues/5)) |
| `refuted_verifiable` con `verification.against: "none"` | `against` tiene que ser `repository`, `execution` o `external_source` | Refutar sin haber verificado nada es una contradicción, no una refutación ([#5](https://github.com/NicolasRocchia/disensor/issues/5)) |
| Perfil `minimized` con texto libre en `extensions` | Todo valor bajo `extensions` tiene que ser opaco: hash `sha256:`, número, booleano, `null`, o contenedores de esos | El espacio de extensión no lo interpretan las reglas, así que el texto estacionado ahí salía del entorno mientras el perfil afirmaba que nada salía ([#8](https://github.com/NicolasRocchia/disensor/issues/8)) |
| `refuted_verifiable` con evidencia presente pero en blanco (`link: ""`, `text` de puros espacios) | `text` y `link` tienen que traer al menos un carácter no blanco | La presencia sin contenido reabría el hueco del [#5](https://github.com/NicolasRocchia/disensor/issues/5) por la pata más débil del `anyOf`; lo cazó la propia ronda adversarial de v0.3 |
| Perfil `minimized` con texto libre en las **claves** de `extensions` | Toda clave bajo un objeto opaco tiene forma de identificador (`[A-Za-z0-9._:-]`, máximo 128) | El valor opaco no alcanza si el mensaje viaja en el nombre: el [#8](https://github.com/NicolasRocchia/disensor/issues/8) cerraba los valores y dejaba las claves |

Y `verification.against` acepta ahora **`external_source`**: literatura, especificaciones de terceros, advisories o documentación externa. En v0.2 una verificación contra una fuente externa no tenía categoría verdadera disponible y había que declararla como `repository` ([#7](https://github.com/NicolasRocchia/disensor/issues/7)).

**Cómo migrar**: poner el campo `schema` en `residue/v0.3` (la clave se conserva; cambia su valor). Si el artefacto ya satisface los invariantes de la tabla, no hay nada más que hacer: ningún fixture de este repositorio que fuera válido bajo v0.2 necesitó corrección. Los vectores de conformidad sí incluyen artefactos que los violan, a propósito, como casos negativos. El validador reconoce un artefacto v0.2 y explica qué endureció la v0.3 en lugar de limitarse a decir que el `const` falló.

**Por qué se subió el identificador en vez de endurecer v0.2 en el lugar**: no fue por compatibilidad, que no había ninguna que proteger. Fue porque el producto entero se apoya en que un identificador de esquema signifique una cosa; si v0.2 significara distinto según cuándo se lo lea, la herramienta se contradiría en su propio repositorio.

El contrato v0.2 original queda congelado, byte a byte como se publicó, en `spec/residue.schema.v0.2.json`: el esquema vigente sigue leyendo v0.2, pero el documento al que ese identificador apunta ya no depende de una reconstrucción.

## Migración del esquema: residue/v0.3 a residue/v0.4

Las declaraciones históricas no cambian. Cada versión tiene ahora su propio
recurso congelado y se valida con sus propias reglas, así que una declaración
v0.3 sigue validando igual que antes: leer registros viejos nunca fue un
permiso para seguir emitiendo bajo reglas más débiles, y tampoco es un motivo
para reescribirlos. Lo que cambia es lo que tiene que decir una declaración
NUEVA.

| Qué agrega v0.4 | Por qué |
|---|---|
| `reviewers[].independence` (obligatorio) | R4 exigía familia distinta y punto, así que una ronda sin segundo modelo no se podía declarar de ninguna manera, ni diciendo la verdad. Ahora la independencia se declara y la regla verifica que coincida con las familias declaradas: `cross_family` con dos revisores de la misma familia se rechaza, y declararse degradado teniendo otra familia también. |
| `reviewers[].fallback_reason` | Obligatorio por debajo de `cross_family`. Un código enumerado, no prosa: el texto libre se vuelve boilerplate en el segundo evento, y ahí la cadena pasa a ser una excusa para ir siempre por el camino barato. |
| `reviewers[].hardening` | `verified` cuando el revisor corrió por un adaptador cuya neutralización de las instrucciones del proyecto se probó contra un repositorio hostil. Se deriva, no se elige. |
| Clases de residuo `reviewer_correlation` y `reviewer_hardening_gap` | Una por revisor degradado, nombrándolo. La correlación es lo que el revisor no podía ver; el endurecimiento es lo que el material revisado podía decirle. Riesgos distintos, ítems distintos. |

**Cómo migrar**: nada, para lo que ya está escrito. Para lo que escribas de
ahora en más, `disensor new` emite v0.4 y prellena estos campos desde la ronda;
`disensor validate` te dice exactamente qué falta si escribís una a mano. El
nivel A no admite independencia por debajo de `cross_family`: declarable no es
lo mismo que admisible en el nivel que el protocolo reserva para lo que no se
puede deshacer.

**Un detalle del despliegue**: un CLI 0.9 emite v0.4, y un gate todavía pineado
a una release anterior no conoce esa versión. `disensor init --upgrade` mueve
el pin, o lo avisa antes de que generes una declaración que tu propio CI
rechazaría.

## Migración de v0.3 a v0.4 (versiones del paquete)

El esquema del artefacto no cambia y las declaraciones ya versionadas siguen siendo válidas: lo que cambia es qué PRs aprueba el gate. Actualizar sin leer esto deja el CI en rojo con mensajes que sí explican la causa, pero conviene saberlo antes.

**Lo que empieza a fallar y por qué:**

| Antes pasaba | Ahora falla | Qué hacer |
|---|---|---|
| Checkout sin `fetch-depth: 0` (el gate avisaba y aprobaba igual) | El gate no puede resolver el rango del PR y **falla cerrado** | Agregar `fetch-depth: 0` al checkout. Un control que no puede decidir no aprueba. |
| Declaración de compuerta `diff` sin `base_commit` | Se rechaza | Completarlo. Una revisión de diff identifica el par (base revisada, head revisada), no un head suelto. |
| Artefacto con cualquier nombre de archivo | Se rechaza | El archivo se llama `<event_id>.json` y el `event_id` tiene que ser un UUID canónico. `disensor new` ya los genera así. |
| Config con claves desconocidas o del tipo equivocado | Se rechaza | La configuración se valida contra un esquema cerrado. `level_A_enabled: "false"` entre comillas ya no habilita Nivel A por ser un texto no vacío. |
| Una declaración de un PR anterior alcanzaba para aprobar el PR actual | Se rechaza | Cada PR declara lo suyo. El gate solo evalúa lo que el PR agrega. |
| Declarar `plan` para aprobar un cambio de código | Se rechaza | La política de alcance dice qué compuerta acepta cada ruta, y por defecto todo exige `diff`. |
| Revisar un commit y después seguir agregando código | Se rechaza | La declaración tiene que cubrir cada ruta en el estado en que se va a mergear. |

**Lo que se arregla solo, sin tocar nada:** el gate dejaba de funcionar a partir del segundo PR, porque evaluaba también los artefactos de PRs anteriores y su commit revisado quedaba fuera del rango nuevo. Si venías conviviendo con eso, desaparece.

**Antes de actualizar**, si el repositorio ya tiene `.residue/` con historia, conviene correr `disensor gate --no-comment` en local sobre un PR abierto para ver qué dice.

## Estado

v0.9.3, sobre **residue/v0.4**. Esta versión deja escrito cuándo sube el pin de la propia Action del gate: viaja en el próximo PR de trabajo real, salvo que la release corrija la seguridad del gate o cambie la versión del esquema, y dice en voz alta que eso es una convención y no un control ([#17](https://github.com/NicolasRocchia/disensor/issues/17)). La versión anterior hace que `disensor guide` entregue el runbook del evento además de la guía de llenado del artefacto, así un agente que no es Claude Code recibe de un solo comando el mismo material que lleva la skill de Claude Code, que es lo que la documentación venía prometiendo desde que la ronda pasó a estar orquestada ([#30](https://github.com/NicolasRocchia/disensor/issues/30)). `--runbook` y `--filling` piden una de las dos, y `init --only-skill` escribe ese runbook sin la sección de `CLAUDE.md`, para un repositorio cuyo agente es otro. La versión anterior orquesta la ronda: `disensor round` empaqueta el material, corre un revisor registrado en tu máquina, captura el informe y ancla el resultado a los commits que efectivamente revisó, y `disensor new --round` construye la declaración desde ahí. Cualquier asistente con línea de comandos puede ser el revisor; el catálogo empaquetado es un atajo, no la lista de lo permitido. residue/v0.4 vuelve declarable una ronda sin segunda familia de modelo como el modo degradado que es, en vez de imposible de declarar, y cada versión del esquema se valida con sus propias reglas. `disensor init --upgrade` lleva una instalación anterior a este procedimiento sin tocar nada que hayas editado. La versión anterior agregó `disensor pin`, que congela la Action al SHA de commit de su tag de release. Desde la v0.6.3 la documentación larga es bilingüe: `README.md` es el inglés que renderiza PyPI, `README.es.md` es el castellano, y la guía de llenado viaja en los dos idiomas. Esta versión vuelve alcanzable la guía castellana empaquetada, con `disensor guide --lang es`. Las releases se publican a PyPI vía Trusted Publishing (OIDC, `release.yml`): sin tokens en ninguna máquina. La v0.4 reescribió el gate para que derive el alcance del PR de git (ver "Qué hace cumplir el gate") y la v0.5 entrega la consigna adversarial empaquetada con hash reproducible; el paso a residue/v0.3 endurece tres puntos del artefacto, cerrando los issues [#5](https://github.com/NicolasRocchia/disensor/issues/5), [#7](https://github.com/NicolasRocchia/disensor/issues/7) y [#8](https://github.com/NicolasRocchia/disensor/issues/8). Ver "Migración de v0.2 a v0.3". Decisión cerrada en v0.2: claves del esquema y CLI en inglés (el español queda como alias en la CLI y como idioma de la documentación). El esquema puede cambiar; cada versión desde residue/v0.2 en adelante se congela con su propio identificador, y una declaración se sigue validando con las reglas que la juzgaron cuando se emitió. La residuo/v0.1 de claves en castellano se reconoce y se rechaza con instrucciones de migración, no se valida. No hay una versión comprometida como el punto donde el esquema se estabiliza: cuando haya un contrato ratificado como estable, se dice acá. Decisión abierta: licencia definitiva (hoy MIT; Apache-2.0 está en consideración por la concesión de patentes).

## Licencia

MIT.

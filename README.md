# disensor

Adversarial plan & code review with a declared residue.

**English**: disensor emits, validates and CI-enforces *residue declarations*: a JSON artifact that records how each adversarial review event ended (one model generates, a model from another family attacks, every finding reaches a terminal state) and, above all, what the cycle could NOT close by itself. Install with `pip install disensor`, scaffold a repo with `disensor init`. As of v0.2 the whole contract (schema keys, enums, CLI) is English; the docs below are in Spanish, and the ES-EN glossary at the end maps the paper's terminology to the schema.

Declaración de residuo de revisión adversarial, con validación y gate de CI. Implementación de referencia del artefacto definido a partir del método de **desacuerdo controlado**: un modelo genera, un modelo de otra familia ataca, el generador verifica cada hallazgo, y el ciclo termina cuando todo hallazgo quedó resuelto, refutado con evidencia o escalado a un humano.

El artefacto que este repo define y hace cumplir registra cómo terminó cada evento de revisión: los hallazgos con su estado terminal, y el **residuo**: lo que el ciclo no pudo cerrar por sí mismo y descansa sobre el juicio de alguien. La declaración lista residuo, no cobertura: dirige el escrutinio del revisor humano en lugar de leerse como sello de calidad.

Paper del método: Rocchia, N. (2026), *Desacuerdo controlado: revisión adversarial automatizada con un segundo asistente de código en el desarrollo de software*, DOI [10.5281/zenodo.21633495](https://doi.org/10.5281/zenodo.21633495).

## Qué hay acá

- `spec/residue.schema.json`: el esquema del artefacto (JSON Schema 2020-12), versión residue/v0.2.
- `spec/examples/`: tres artefactos de ejemplo, incluido un evento real anonimizado y el perfil minimizado sin texto libre.
- `src/disensor/`: paquete Python con el validador (reglas R0 a R10), el gate de CI (chequeos G1 a G8), el render del comentario de PR, el scaffolding de artefactos y el de repositorios (`init`), y la guía de llenado empaquetada (`GUIDE.md`).
- `action.yml`: GitHub Action compuesta, lista para usar.
- `docs/integracion-claude-code.md`: cómo el flujo real (Claude Code más un revisor de otra familia) emite el artefacto al cierre de cada evento.
- `docs/antecedentes.md`: dónde se ubica el método respecto de la literatura (residual doubt y defeaters, design rationale y su capture bottleneck, revisión adversarial multi-agente, governance runtimes, provenance de cadena de suministro), con el estado de verificación de cada referencia.

## Uso rápido

El paquete se instala una vez (global); cada repositorio se inicializa una vez:

```bash
pip install disensor        # o pipx install disensor, recomendado para CLIs

disensor init               # en la raíz del repo: config, CLAUDE.md, skill de llenado y workflow de CI

disensor prompt --gate diff            # la consigna adversarial, para pegarle al revisor de otra familia
disensor new --gate diff --level B     # plantilla prellenada en .residue/
disensor validate .residue/<id>.json   # schema + reglas R0 a R10
disensor gate --no-comment             # lo que va a correr CI, en local

disensor guide                         # la guía de llenado, para cualquier agente o humano
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
disensor gate --no-comment --base <sha-base> --head HEAD
```

Recién cuando quieras que **haga cumplir**, corré `disensor init` completo (que escribe el workflow) y aplicá los requisitos de despliegue de más abajo. Antes de eso es una herramienta que te dice cómo te iría; después es un control que bloquea.

Los subcomandos y flags de la v0.1 en español (`nuevo`, `validar`, `--compuerta`, `--nivel`, `--directorio`, `--sin-comentario`) siguen funcionando como alias.

`disensor init` escribe, en forma idempotente, el `disensor.config.json` (el nivel viaja con el código, en un archivo versionado), la sección de cierre de evento en `CLAUDE.md`, la skill de Claude Code con la guía completa de llenado (`.claude/skills/disensor/SKILL.md`, cargada a demanda al cerrar cada ronda) y el workflow del gate; lo que ya existe se respeta y se informa. El principio es que después de `pip install disensor` y `disensor init` el usuario no toque nada a mano: Claude sabe cuándo (CLAUDE.md) y cómo (la skill), cualquier otro agente recibe lo mismo con `disensor guide`, y el CI hace cumplir el resultado. Config resultante:

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
      - uses: NicolasRocchia/disensor@v0.5.0
```

El gate valida las declaraciones que **el PR agrega**, aplica la política y publica el resultado como comentario (se actualiza en el lugar en cada push). Todo lo que decide sale de objetos de git en el rango `merge-base..head`, nunca del working tree: en un evento `pull_request` el checkout deja el merge commit sintético mientras `head.sha` apunta al head real, así que leer del disco clasificaría un árbol y validaría otro.

## Qué hace cumplir el gate

Por artefacto (reglas R0 a R10): coherencia entre hallazgos y residuo, conteos que cierran, decorrelación de familias entre generador y revisor, presencia obligatoria del objeto de evidencia en refutaciones verificables (ver el límite de más abajo), atención humana obligatoria en refutaciones interpretativas, corrección verificada antes de cerrar un hallazgo en compuerta de diff, rechazo de marcadores genéricos (en inglés y en español), y perfil minimizado sin fugas de texto.

**Límite conocido de residue/v0.2, en `refuted_verifiable`**: el esquema exige que el objeto `evidence` esté presente, pero todavía no exige que contenga evidencia material (`evidence: {}` valida) ni impide `verification.against: "none"`. O sea que hoy la garantía es de forma y no de contenido: un hallazgo puede cerrarse como falso positivo verificable declarando que se verificó contra nada. Los dos invariantes están previstos para el endurecimiento de residue/v0.3 y se corrigen ahí, no retroactivamente sobre v0.2: un artefacto que era válido bajo una versión del esquema no debería volverse inválido bajo el mismo identificador. Detalle y reproducción en el [issue #5](https://github.com/NicolasRocchia/disensor/issues/5).

Por artefacto, contra el PR: nivel igual al declarado del repositorio (G2), Nivel A bloqueado mientras la gobernanza no esté validada (G3), política de confinamiento del revisor por nivel (G4), y pertenencia al PR del commit revisado (G5), que para la compuerta de diff exige además `base_commit`, porque una revisión de diff identifica el par (base revisada, head revisada) y no un head suelto.

Por PR:

- **G1**: si el PR toca rutas que requieren revisión, agrega al menos una declaración válida.
- **G6, cobertura**: cada ruta cambiada está cubierta por una declaración cuya compuerta la política de alcance acepta para esa ruta, y que **califica** para ella, o sea que la ruta no cambió entre el commit revisado y el head. Una declaración rancia no cubre nada.
- **G7, testigo de integración**: alguna declaración vio el árbol final completo. La cobertura ruta por ruta no alcanza: dos ramas laterales revisadas por separado y después fusionadas cubren entre las dos todas las rutas mientras nadie revisó la integración.
- **G8, la evidencia es de solo agregar**: un PR no puede modificar, borrar ni renombrar declaraciones que ya estaban, ni reutilizar un `event_id` existente.

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
- **Pin de la Action por SHA**, no por tag: un tag es movible y no es raíz de confianza. `disensor init` escribe el tag de la versión instalada por comodidad, y el propio workflow generado avisa que hay que reemplazarlo por el SHA al que ese tag apunta. La documentación de este repo también usa el tag, porque documenta qué versión corresponde; el SHA lo pone quien despliega.
- **Bootstrap**: el primer PR que agrega el config y el workflow no puede convertirse a sí mismo en raíz de confianza. La activación inicial es un paso administrativo, previo a que el gate signifique algo.

Límite explícito: leer la política de la base convierte un bypass de un paso en uno de dos, no lo elimina. Quien pueda mergear una relajación la usa en el PR siguiente. Y nada de esto protege contra un workflow modificado, salteado o sustituido. Eso solo lo resuelve la plataforma.

## Qué no hace

No corre modelos, no pide claves de API en CI, y ningún código viaja a ningún servicio: valida un JSON que ya está versionado en el repo. La orquestación del loop vive donde el equipo ya trabaja; el perfil `minimized` del artefacto permite ambientes donde ni siquiera el texto de los hallazgos puede salir del entorno.

## Conformidad entre implementaciones

`spec/vectors/` contiene los vectores de conformidad: 22 artefactos con su veredicto esperado (válido o no, y las etiquetas de regla que deben dispararse). Toda implementación del validador tiene que pasarlos idénticos: la referencia en Python los corre en la suite (`tests/test_vectors.py`) y el port TypeScript del plano de evidencia los corre con `npm run conformidad`. Se comparan etiquetas, no mensajes. Los vectores se regeneran con `python -m disensor.vectors spec/vectors`.

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
| confinamiento (permisos, sandbox, solo lectura por instrucción) | confinement (permissions, sandbox, read_only_by_instruction) |
| consigna (hash de la consigna adversarial) | prompt_hash |
| estado final: incorporado, deuda registrada, decisión del dueño, refutado verificable, refutado interpretativo, escalado abierto | final_state: incorporated, debt_recorded, owner_decision, refuted_verifiable, refuted_interpretive, escalated_open |
| clases de residuo: escalado sin decisión, refutación del principal, gap de ejecución | residue classes: escalation_without_decision, principal_refutation, execution_gap |
| ruta abreviada / casos protegidos | abbreviated_path / protected_cases_touched |
| verificación de la corrección | fix_verification |
| aceptación de referente | lead_acceptance |
| ausencia declarada / declaración | declared_absence / declaration |
| métricas: conteos, válidos, falsos positivos | metrics: counts, valid, false_positives |

Migración desde v0.1: renombrar `.residuo/` a `.residue/`, las claves del config (`nivel_criticidad` a `criticality_level`, `nivel_A_habilitado` a `level_A_enabled`) y las claves de los artefactos según el glosario. El validador reconoce artefactos v0.1 y lo dice explícitamente; el gate rechaza en voz alta un config con claves viejas en lugar de aplicar defaults en silencio.

## Migración de v0.3 a v0.4

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

v0.4, borrador en uso. El esquema sigue en residue/v0.2: la v0.4 no lo toca, reescribe el gate para que derive el alcance del PR de git (ver "Qué hace cumplir el gate"). El endurecimiento de las reglas del artefacto y el paso a residue/v0.3 son la tanda siguiente. Decisión cerrada en v0.2: claves del esquema y CLI en inglés (el español queda como alias en la CLI y como idioma de la documentación). El esquema puede cambiar hasta v1.0; los cambios se declaran en el propio esquema. Decisión abierta antes de v1.0: licencia definitiva (hoy MIT; Apache-2.0 está en consideración por la concesión de patentes antes del release público).

## Licencia

MIT.

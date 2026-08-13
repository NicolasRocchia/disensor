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

## Uso rápido

El paquete se instala una vez (global); cada repositorio se inicializa una vez:

```bash
pip install disensor        # o pipx install disensor, recomendado para CLIs

disensor init               # en la raíz del repo: config, CLAUDE.md, skill de llenado y workflow de CI
disensor new --gate diff --level B     # plantilla prellenada en .residue/
disensor validate .residue/<id>.json   # schema + reglas R0 a R10
disensor gate --no-comment             # lo que va a correr CI, en local

disensor guide                         # la guía de llenado, para cualquier agente o humano
disensor hash consigna.md              # el sha256: que pide prompt_hash, sin calcularlo a mano
```

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
      - uses: NicolasRocchia/disensor@v0.4.0
```

El gate valida las declaraciones que **el PR agrega**, aplica la política y publica el resultado como comentario (se actualiza en el lugar en cada push). Todo lo que decide sale de objetos de git en el rango `merge-base..head`, nunca del working tree: en un evento `pull_request` el checkout deja el merge commit sintético mientras `head.sha` apunta al head real, así que leer del disco clasificaría un árbol y validaría otro.

## Qué hace cumplir el gate

Por artefacto (reglas R0 a R10): coherencia entre hallazgos y residuo, conteos que cierran, decorrelación de familias entre generador y revisor, evidencia obligatoria en refutaciones verificables, atención humana obligatoria en refutaciones interpretativas, corrección verificada antes de cerrar un hallazgo en compuerta de diff, rechazo de marcadores genéricos (en inglés y en español), y perfil minimizado sin fugas de texto.

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

## Estado

v0.4, borrador en uso. El esquema sigue en residue/v0.2: la v0.4 no lo toca, reescribe el gate para que derive el alcance del PR de git (ver "Qué hace cumplir el gate"). El endurecimiento de las reglas del artefacto y el paso a residue/v0.3 son la tanda siguiente. Decisión cerrada en v0.2: claves del esquema y CLI en inglés (el español queda como alias en la CLI y como idioma de la documentación). El esquema puede cambiar hasta v1.0; los cambios se declaran en el propio esquema. Decisión abierta antes de v1.0: licencia definitiva (hoy MIT; Apache-2.0 está en consideración por la concesión de patentes antes del release público).

## Licencia

MIT.

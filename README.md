# disensor

Adversarial plan & code review with a declared residue.

**English**: disensor emits, validates and CI-enforces *residue declarations*: a JSON artifact that records how each adversarial review event ended (one model generates, a model from another family attacks, every finding reaches a terminal state) and, above all, what the cycle could NOT close by itself. Install with `pip install disensor`, scaffold a repo with `disensor init`. As of v0.2 the whole contract (schema keys, enums, CLI) is English; the docs below are in Spanish, and the ES-EN glossary at the end maps the paper's terminology to the schema.

Declaración de residuo de revisión adversarial, con validación y gate de CI. Implementación de referencia del artefacto definido a partir del método de **desacuerdo controlado**: un modelo genera, un modelo de otra familia ataca, el generador verifica cada hallazgo, y el ciclo termina cuando todo hallazgo quedó resuelto, refutado con evidencia o escalado a un humano.

El artefacto que este repo define y hace cumplir registra cómo terminó cada evento de revisión: los hallazgos con su estado terminal, y el **residuo**: lo que el ciclo no pudo cerrar por sí mismo y descansa sobre el juicio de alguien. La declaración lista residuo, no cobertura: dirige el escrutinio del revisor humano en lugar de leerse como sello de calidad.

Paper del método: Rocchia, N. (2026), *Desacuerdo controlado: revisión adversarial automatizada con un segundo asistente de código en el desarrollo de software*, DOI [10.5281/zenodo.21633495](https://doi.org/10.5281/zenodo.21633495).

## Qué hay acá

- `spec/residue.schema.json`: el esquema del artefacto (JSON Schema 2020-12), versión residue/v0.2.
- `spec/examples/`: tres artefactos de ejemplo, incluido un evento real anonimizado y el perfil minimizado sin texto libre.
- `src/disensor/`: paquete Python con el validador (reglas R0 a R10), el gate de CI (chequeos G1 a G5), el render del comentario de PR, el scaffolding de artefactos y el de repositorios (`init`).
- `action.yml`: GitHub Action compuesta, lista para usar.
- `docs/integracion-claude-code.md`: cómo el flujo real (Claude Code más un revisor de otra familia) emite el artefacto al cierre de cada evento.

## Uso rápido

El paquete se instala una vez (global); cada repositorio se inicializa una vez:

```bash
pip install disensor        # o pipx install disensor, recomendado para CLIs

disensor init               # en la raíz del repo: config, sección de CLAUDE.md y workflow de CI
disensor new --gate diff --level B     # plantilla prellenada en .residue/
disensor validate .residue/<id>.json   # schema + reglas R0 a R10
disensor gate --no-comment             # lo que va a correr CI, en local
```

Los subcomandos y flags de la v0.1 en español (`nuevo`, `validar`, `--compuerta`, `--nivel`, `--directorio`, `--sin-comentario`) siguen funcionando como alias.

`disensor init` escribe, en forma idempotente, el `disensor.config.json` (el nivel viaja con el código, en un archivo versionado), la sección de cierre de evento en `CLAUDE.md` y el workflow del gate; lo que ya existe se respeta y se informa. Config resultante:

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
      - uses: NicolasRocchia/disensor@v0.2.0
```

El gate valida todos los artefactos de `.residue/` del PR, aplica la política y publica la declaración como comentario (se actualiza en el lugar en cada push).

## Qué hace cumplir el gate

Por artefacto (reglas R0 a R10): coherencia entre hallazgos y residuo, conteos que cierran, decorrelación de familias entre generador y revisor, evidencia obligatoria en refutaciones verificables, atención humana obligatoria en refutaciones interpretativas, corrección verificada antes de cerrar un hallazgo en compuerta de diff, rechazo de marcadores genéricos (en inglés y en español), y perfil minimizado sin fugas de texto.

Por PR (chequeos G1 a G5): al menos una declaración válida en el rango, nivel del artefacto igual al declarado del repositorio, Nivel A bloqueado mientras la gobernanza no esté validada, política de confinamiento del revisor por nivel, y commit revisado dentro del rango del PR.

Límite honesto, heredado del protocolo: la máquina detecta el campo vacío y el marcador genérico, no la declaración falsa. El muestreo humano de PR cerrados sigue siendo la única defensa real contra el cumplimiento cosmético.

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

v0.2, borrador en uso. Decisión cerrada en v0.2: claves del esquema y CLI en inglés (el español queda como alias en la CLI y como idioma de la documentación). El esquema puede cambiar hasta v1.0; los cambios se declaran en el propio esquema. Decisión abierta antes de v1.0: licencia definitiva (hoy MIT; Apache-2.0 está en consideración por la concesión de patentes antes del release público).

## Licencia

MIT.

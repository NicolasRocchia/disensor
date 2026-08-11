# disensor

Adversarial plan & code review with a declared residue.

Declaración de residuo de revisión adversarial, con validación y gate de CI. Implementación de referencia del artefacto definido a partir del método de **desacuerdo controlado**: un modelo genera, un modelo de otra familia ataca, el generador verifica cada hallazgo, y el ciclo termina cuando todo hallazgo quedó resuelto, refutado con evidencia o escalado a un humano.

El artefacto que este repo define y hace cumplir registra cómo terminó cada evento de revisión: los hallazgos con su estado terminal, y el **residuo**: lo que el ciclo no pudo cerrar por sí mismo y descansa sobre el juicio de alguien. La declaración lista residuo, no cobertura: dirige el escrutinio del revisor humano en lugar de leerse como sello de calidad.

Paper del método: Rocchia, N. (2026), *Desacuerdo controlado: revisión adversarial automatizada con un segundo asistente de código en el desarrollo de software*, DOI [10.5281/zenodo.21633495](https://doi.org/10.5281/zenodo.21633495).

## Qué hay acá

- `spec/residuo.schema.json`: el esquema del artefacto (JSON Schema 2020-12), versión v0.1.
- `spec/ejemplos/`: tres artefactos de ejemplo, incluido un evento real anonimizado y el perfil minimizado sin texto libre.
- `src/disensor/`: paquete Python con el validador (reglas R0 a R10), el gate de CI (chequeos G1 a G5), el render del comentario de PR y el scaffolding de artefactos.
- `action.yml`: GitHub Action compuesta, lista para usar.
- `docs/integracion-claude-code.md`: cómo el flujo real (Claude Code + Codex) emite el artefacto al cierre de cada evento.

## Uso rápido

```bash
pip install disensor     # para desarrollo, desde el repo clonado: pip install -e .

disensor nuevo --compuerta diff --nivel B    # plantilla prellenada en .residuo/
disensor validar .residuo/<id>.json          # schema + reglas R0 a R10
disensor gate --sin-comentario               # lo que va a correr CI, en local
```

En el repositorio consumidor, `disensor.config.json` en la raíz declara el nivel de criticidad (el nivel viaja con el código, en un archivo versionado):

```json
{
  "nivel_criticidad": "B",
  "nivel_A_habilitado": false
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
      - uses: NicolasRocchia/disensor@v0.1.0
```

El gate valida todos los artefactos de `.residuo/` del PR, aplica la política y publica la declaración como comentario (se actualiza en el lugar en cada push).

## Qué hace cumplir el gate

Por artefacto (reglas R0 a R10): coherencia entre hallazgos y residuo, conteos que cierran, decorrelación de familias entre generador y revisor, evidencia obligatoria en refutaciones verificables, atención humana obligatoria en refutaciones interpretativas, corrección verificada antes de cerrar un hallazgo en compuerta de diff, rechazo de marcadores genéricos, y perfil minimizado sin fugas de texto.

Por PR (chequeos G1 a G5): al menos una declaración válida en el rango, nivel del artefacto igual al declarado del repositorio, Nivel A bloqueado mientras la gobernanza no esté validada, política de confinamiento del revisor por nivel, y commit revisado dentro del rango del PR.

Límite honesto, heredado del protocolo: la máquina detecta el campo vacío y el marcador genérico, no la declaración falsa. El muestreo humano de PR cerrados sigue siendo la única defensa real contra el cumplimiento cosmético.

## Qué no hace

No corre modelos, no pide claves de API en CI, y ningún código viaja a ningún servicio: valida un JSON que ya está versionado en el repo. La orquestación del loop vive donde el equipo ya trabaja; el perfil `minimizado` del artefacto permite ambientes donde ni siquiera el texto de los hallazgos puede salir del entorno.

## Conformidad entre implementaciones

`spec/vectores/` contiene los vectores de conformidad: 22 artefactos con su veredicto esperado (valido o no, y las etiquetas de regla que deben dispararse). Toda implementacion del validador tiene que pasarlos identicos: la referencia en Python los corre en la suite (`tests/test_vectores.py`) y el port TypeScript del plano de evidencia los corre con `npm run conformidad`. Se comparan etiquetas, no mensajes. Los vectores se regeneran con `python -m disensor.vectores spec/vectores`.

`plano-evidencia/` contiene el Worker de ingesta (Cloudflare Workers mas D1) con el port TypeScript del validador y el recibo de integridad de solo agregado. Ver su README para el estado de verificacion y el despliegue.

## Estado

v0.1, borrador en uso. El esquema puede cambiar hasta v1.0; los cambios se declaran en el propio esquema. Dos decisiones abiertas antes de v0.2: claves del esquema en español o inglés, y licencia definitiva (hoy MIT; Apache-2.0 está en consideración por la concesión de patentes antes del release público).

## Licencia

MIT.

# disensor 0.8.0: la ronda orquestada

## Contexto

El usuario piensa la feature y el evento entero corre por detrás: A implementa, se llama al revisor B, se captura lo que dijo, se incorpora lo que corresponde y se arma el PR. El usuario aparece solo donde el método lo exige: consentir que su código salga a un tercero, aceptar un riesgo, resolver una escalación, y mirar el PR. Hoy todo ese tramo es artesanal y el procedimiento vive en la cabeza de quien lo hizo antes, no en el producto.

Reparto por naturaleza de tarea: **lo mecánico que debe pasar siempre igual** es determinismo y va en **disensor**; **lo que requiere juicio** (descubrir qué hay en la máquina, verificar hallazgos contra el repo, incorporar o refutar, contar la historia en el PR) es de **A**. Y lo que es **decisión de seguridad del dueño** no se delega a ninguno de los dos.

## Arquitectura: política, capacidad y evento

| Dato | Ejemplo | Dónde vive | Quién lo escribe |
|---|---|---|---|
| **Política** | qué rutas exigen ronda, nivel, independencia y hardening mínimos | el repo, versionado, leído de la punta del destino | el equipo, una vez |
| **Capacidad** | qué revisores hay en ESTA máquina y cómo se invocan | `~/.disensor/reviewers.json`, fuera del repo | A propone, el dueño aprueba |
| **Evento** | qué revisor corrió, su informe, los OID revisados | la declaración, en el PR | el runner más A |

## Historia de la revisión de este plan

Tres pasadas de compuerta plan con Codex (`gpt-5.6-sol`, openai), las tres NO MERGEABLE, con hallazgos incorporados en cada vuelta. Decisiones de Nico:

1. **Cae la prohibición de tocar `gate.py`**: disparador y enforcement tienen que ser la misma decisión.
2. **Baja el claim**: `round` automatiza y transcribe; identidad y confinamiento son atestación.
3. **El descubrimiento es de A**: un catálogo cerrado solo sirve a quien tenga nuestros CLIs exactos.
4. **El modo degradado entra en esta versión** (schema v0.4): sin eso, quien no tiene un segundo modelo no puede declarar nada, y la 0.8.0 sería un retroceso frente a la 0.7, que al menos permite la ronda manual.

Y el hallazgo crítico de la tercera pasada, que ajusta la decisión 3: mover los comandos fuera del repo **no cerró el ataque, lo movió**. Un PR con instrucciones hostiles puede inducir a A a registrar un ejecutable malicioso, que después recibe código privado. A es un intermediario confundido. Por eso: **A descubre y propone; el registro de lo que no viene del catálogo verificado lo aprueba el dueño.**

## Cambios

### 1. `review_requirement()`: una decisión, dos llamadores

Función pura extraída de [gate.py](src/disensor/gate.py), llamada por el gate y por `round --check`. **Devuelve una clasificación**: `not_required` | `required(accepted_gates)` | `blocked(reason)`. "¿Hace falta ronda?" y "¿el PR es válido?" son preguntas distintas: con `required=false` y evidencia mutada no hace falta ronda nueva pero el gate falla igual ([gate.py:504](src/disensor/gate.py)). El test de equivalencia compara la clasificación, no el exit code.

Replica lo que hoy decide `_run_gate`: rango `merge_base..head` ([gate.py:490](src/disensor/gate.py)); política de la punta exacta del destino ([gate.py:493](src/disensor/gate.py)); `classify_changes` antes del scope ([gate.py:267](src/disensor/gate.py)); `required=false` salteando toda cobertura ([gate.py:623](src/disensor/gate.py)); compuerta común por intersección ([gate.py:380](src/disensor/gate.py)); flags `--config`/`--directory` ([cli.py:105](src/disensor/cli.py)). Sin rango resoluble, **falla cerrado**.

Nota para la documentación: `required=false` saltea la cobertura *incluido el piso*, así que "piso no relajable" es exacto solo frente a `scope`. Cambiar ese comportamiento va a un issue aparte.

### 2. `disensor pack`

- Preámbulo de confinamiento, identificación del material, ruta del informe y la consigna empaquetada verbatim (`brief_text` de [brief.py](src/disensor/brief.py)).
- **Material explícito**: para `diff` el rango git; para `plan` y `architecture`, `--material <archivo|->`.
- **Dos hashes con su alcance dicho**: `prompt_hash` es la consigna canónica; `pack_hash` son **los bytes que aporta disensor**, no el prompt efectivo (el contexto de sistema del CLI no está incluido).

### 3. Descubrimiento: A propone, el dueño aprueba, disensor ejecuta

```
A necesita una ronda
  → ¿hay revisores registrados? NO
  → A investiga la máquina y consulta el catálogo (disensor reviewer suggest)
  → CAMINO RÁPIDO: receta del catálogo → se registra con consentimiento de egreso
  → CAMINO LENTO: entrada nueva → disensor la muestra entera y PIDE APROBACIÓN DEL DUEÑO
  → disensor valida, escribe atómicamente ~/.disensor/reviewers.json
  → de acá en más, determinístico
```

**Por qué el camino lento**: un PR puede inyectar instrucciones que induzcan a A a registrar un ejecutable arbitrario. Validar la forma no prueba que un binario sea seguro. Registrar algo que después va a recibir código privado es decisión del dueño.

`reviewer add` valida antes de escribir: **argv estructurado, nunca cadena de shell**; ruta absoluta del ejecutable resuelta y mostrada; **solo placeholders enumerados**, cada uno como argumento completo, rechazando desconocidos o concatenados; **cwd lo fija el runner**, la entrada no lo elige; sin secretos ni comandos de setup en el argv; **`hardening: unverified` forzado** para entradas creadas por A; versión y hash del ejecutable registrados (si cambia, se invalidan smoke, hardening y consentimiento); escritura atómica, rechazando symlinks y reparse points. Al aprobar, el dueño ve ejecutable, argumentos, proveedor y qué material va a salir.

**Consentimiento de egreso, con alcance** (no global de máquina): la detección es **offline primero** (binario y versión), después se muestra el egreso, después se consiente, y **recién entonces** corre el smoke, **con material sintético y cwd fuera del repo**. La autorización queda ligada a repositorio canónico, receta/ejecutable y versión, proveedor y categoría de material; cualquier cambio la invalida. Para un adaptador desconocido, el valor conservador es `unknown / may use network`. Existe `reviewer consent list|revoke`.

**A no tiene que ser Claude Code**: el runbook vive en `disensor guide`; la skill es un empaquetado cómodo del mismo texto.

### 4. Hardening: declarado, con consecuencia

Un PR puede agregar `AGENTS.md` con instrucciones y el revisor lo carga **antes** de leer la consigna. Prohibir lo no verificado dejaría afuera a todo CLI fuera del catálogo, así que el nivel se declara **y cuesta**:

- `hardening: verified` **no es un valor libre**: lo deriva el runner de una receta catalogada exacta, su versión/hash y el resultado de la prueba hostil. Si el archivo se edita a mano o el ejecutable cambia, el runner lo degrada solo.
- `hardening: unverified` tiene costo protocolario: `minimum_hardening` por nivel (A exige `verified`), **selección lexicográfica** al elegir revisor (primero independencia, después hardening, agotando las mejores entradas antes de degradar), `fallback_reason` también para la degradación de hardening, y **residuo `reviewer_hardening_gap`** con atención humana. Sin eso, `unverified` sería el estado universal y el hardening quedaría nominalmente visible pero operacionalmente irrelevante.
- **Hardening no es confinamiento**: neutralizar `AGENTS.md` y plugins no impide que el proceso escriba en el filesystem. Son riesgos distintos y llevan residuos distintos.

**Criterio de aceptación del adaptador Codex**: fijar argv, cwd y configuración concretos, y probar contra un repo hostil con `AGENTS.md`, config de proyecto, skills, plugins y hooks que efectivamente no se cargan. Ninguna bandera sola cubre el contrato; si la prueba no pasa, no se marca `verified`.

### 5. Schema v0.4: el modo degradado declarado, con reglas estructurales

- **`reviewer.independence`**: `cross_family` | `same_family_distinct_model` | `same_model_fresh_context`, con **regla estructural, no string libre**: `cross_family` si y solo si `generator.family != reviewer.family`; `same_family_*` exige igualdad. La identidad real sigue siendo declarada, y eso se dice.
- **`reviewer.fallback_reason`**: **código enumerado** más detalle opcional, prellenado desde `attempts`. La prosa libre se vuelve boilerplate.
- **`reviewer.hardening`**: `verified` | `unverified`, derivado por el runner.
- **Residuos separados y por revisor**: `reviewer_correlation` (uno por revisor degradado, con `reviewer_ref` y `requires_human_attention: true`) y `reviewer_hardening_gap`. Con reglas de unicidad y cobertura.
- **Política de mínimos por nivel**: en nivel A el fallback **bloquea**, no produce una declaración aceptable. El fallback no se activa solo por ausencia de alternativa: tiene que estar permitido por política o decidido por el dueño, o se vuelve el camino por defecto.
- **Consigna específica para self-review**, que pega contra el anclaje.
- **Dispatch por versión** ([#13](https://github.com/NicolasRocchia/disensor/issues/13)): selecciona **JSON Schema y reglas Python juntos**. Hoy `validate_artifact()` carga una forma y llama siempre al mismo `rule_errors()` ([rules.py:212](src/disensor/rules.py)), así que la R4 de v0.3 seguiría rechazando el fallback de v0.4. Recursos inmutables separados para **v0.2, v0.3 y v0.4**; se lee primero el discriminador `schema`; versión ausente o desconocida falla. G9 exige v0.4 solo a declaraciones nuevas: una v0.3 histórica se sigue validando con sus reglas originales.
- **Rollout coordinado**: un CLI 0.8 que emite v0.4 contra una Action 0.7 pineada va a ser rechazado. `init --upgrade` actualiza el pin del workflow o **detecta la incompatibilidad antes** de que se genere el artefacto.
- El paper se versiona en Zenodo junto con la release, con R4 re-enunciado.

### 6. `disensor round`

`disensor round --gate <diff|plan|architecture> --generator-family <familia> [--base --head | --material FILE] [--config] [--directory] --result FILE`

0. **Paso cero**: `review_requirement()`. Para `diff` decide el scope; para `plan` y `architecture` el disparador es de A (barra de impacto), pero `round` los orquesta igual.
1. **Contrato commit-first, explícito**: la ronda de diff revisa **commits ya creados**. Precondición de árbol limpio con flags que no dependen de la config del usuario (`--porcelain=v1 -z --untracked-files=all --ignore-submodules=none`). Si está sucio, `round` para y pide commitear; **nunca stashea solo**. El runbook ordena: implementar → commit → ronda → commits de incorporación → ronda nueva.
2. **El resultado sale por `--result` fuera del repo o por pipe**, nunca por redirección adentro (crearía el archivo antes del chequeo). El **informe va a un directorio temporal privado y único**, no a una ruta compartida; al terminar tiene que ser archivo regular, no vacío, no symlink, y se registra el hash de sus bytes.
3. **Elige revisor** por orden lexicográfico: independencia primero, hardening después. Descarta las entradas de la familia del generador. Si quedan revisores instalados pero ninguno cumple, **no es cadena agotada**: es fallback, permitido o bloqueado según la política.
4. Ejecuta con timeout y sin shell. ENOENT, exit distinto de 0, o exit 0 sin informe nuevo cuentan como fallo y pasan al siguiente escalón.
5. Segundo `git status` **después de todas las escrituras del runner**, esperando el árbol de procesos. Cualquier diferencia aborta. Se documenta qué **no** ve: ignorados, `.git/`, índice, refs, escrituras fuera del repo. Es una observación puntual, no una barrera.
6. Emite un **resultado versionado**: `repository` (con normalización canónica definida y probada para SSH/HTTPS/fork/sin remote), `gate`, `target_tip_oid`, `merge_base_oid`, `head_oid`, revisor declarado, `hardening`, `independence`, ruta y hash del informe, `prompt_hash`, `pack_hash`, e intentos con motivo de caída.
7. El runner **jamás interpreta el informe**.

### 7. `disensor new --round <resultado.json|->`

- Usa los OID del resultado **literalmente**, en vez de resolver `HEAD` al crear la plantilla ([template.py:24](src/disensor/template.py)).
- **Falla si el HEAD actual no coincide con el revisado**: la regla es la frescura del material, no el veredicto. Si A incorporó aunque sea un hallazgo menor, esa ronda ya no cubre lo que se va a mergear.
- **Recomputa el hash del informe** y rechaza si cambió desde que se emitió el resultado.
- Falla si el repositorio no coincide. Prellena `confinement.verified` en **`false`**: el mecanismo no prueba lo que el schema define como verificado.

### 8. Skill de juicio y migración de las 0.7

- La skill pasa a runbook: disparador, commit-first, lectura de exit codes, verificación de hallazgos contra el repo, ronda nueva ante cualquier cambio del material, declaración con `new --round`, gate local, PR.
- **`init --upgrade`** migra **solo contenido byte-idéntico** a una versión conocida; ante divergencia no toca nada. Pero el conflicto es un **camino ejecutable, no un callejón**: exit code propio machine-readable (para que A no siga usando el runbook viejo en silencio), `--upgrade --show` con diff de tres vías (base 0.7 conocida, contenido local, contenido 0.8), y opción explícita de aceptar con backup. Las divergencias benignas (CRLF, `autocrlf`, formateadores) bloquean la mutación pero con diagnóstico claro. Los bloques nuevos llevan marcadores BEGIN/END con versión y hash.

### 9. Tests

- **Equivalencia gate/round** sobre la clasificación en: exento, piso, `required=false`, config no estándar, evidencia mutada, sin compuerta común, rango ausente.
- **El catálogo contra el CLI real** (comando existe, `--help` responde, sin red) y **smoke real por adaptador**: saltable localmente pero **requisito registrado del release**, o se publica un adaptador roto.
- **Prueba hostil de endurecimiento**: repo con `AGENTS.md`, hooks y plugins; el adaptador `verified` no los carga.
- **Reglas estructurales de v0.4**: `cross_family` con familias iguales es inválido; fallback sin residuo de correlación es inválido; una v0.4 renombrada a v0.3 falla por campos extra y por la R4 original; una v0.3 histórica sigue validando con sus reglas.
- `round`: árbol sucio rechazado, informe preexistente rechazado, exit 0 sin informe, orden lexicográfico de selección, fallback declarado, anclaje de OID.
- `new --round`: OID literales, HEAD movido rechazado, hash del informe cambiado rechazado.
- `init --upgrade`: migra lo idéntico, no toca lo divergente, y el conflicto sale por exit code propio.

### 10. Documentación y release

- Sección espejada en ambos README: la ronda orquestada, qué corre solo, qué decide el usuario, dónde vive cada archivo, qué sale de la máquina, el contrato commit-first, y la precisión sobre el piso y `required=false`.
- Migración v0.3 → v0.4 documentada, guía bilingüe actualizada, bump, pin del auto-gate vía `disensor pin`, commits atómicos por pieza.

## Qué NO entra

- **[#7](https://github.com/NicolasRocchia/disensor/issues/7)** (evidencia externa) y la rama de evidencia no vacua del intercambio público: schema siguiente.
- **Rubber Duck de Copilot**: su ronda ocurre dentro del agente; queda como el caso que motiva una entrada futura de "ronda ya ocurrida, informe aportado".
- Cadena cloud por defecto, y cambiar el comportamiento de `required=false` frente al piso (issue aparte).

## Ronda adversarial

- **Compuerta plan: tres pasadas hechas**, todo incorporado. No hay cuarta: los hallazgos pasaron de "el diseño está mal" a "faltan estas especificaciones", y eso se caza mejor sobre código real.
- **Compuerta diff** al terminar, con Codex, corrida con `disensor round` si para entonces funciona: si el runner no aguanta su propia ronda, no está terminado.
- Declaración nivel B anclada al head final, gate local verde, PR, merge de Nico, tag y Trusted Publishing.

## Verificación end-to-end

1. Suite completa en verde y `git diff --check` limpio.
2. Repo de prueba: A descubre y propone el revisor real, el dueño aprueba, `pack` produce el paquete con el hash canónico, `round --check` clasifica igual que el gate en los siete escenarios, `round` completo produce informe y resultado anclado, `new --round` genera la declaración con los OID correctos y rechaza un head movido.
3. Repo con 0.7: `init --upgrade` migra lo administrado, reporta conflicto sobre lo editado y coordina el pin del workflow.
4. Máquina sin ningún revisor de otra familia: A registra el fallback, la ronda corre en modo degradado y la declaración lo dice con sus residuos.

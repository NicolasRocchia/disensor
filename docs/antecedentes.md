# Antecedentes

Este documento ubica a disensor respecto de lo que ya existe. No es una sección de trabajo relacionado terminada: es el insumo verificado para escribirla, y está acá porque el claim de novedad del método necesita sostenerse contra literatura concreta y no contra la ausencia de búsqueda.

La idea central del artefacto (conservar explícitamente lo que una evaluación no pudo cerrar) **no es nueva**. Tiene al menos dos tradiciones detrás, una de las cuales fracasó de una forma documentada y muy relevante. Tampoco son nuevas la revisión adversarial multi-agente, la gobernanza externa de coding agents ni la provenance verificable: cada una tiene trabajo publicado en 2026 que se cita abajo. Lo que no encontré es la intersección estrecha, y el capítulo sobre cómo formular el claim de novedad explica cuál es y qué formulaciones quedan descartadas.

## Estado de verificación

Este documento distingue tres niveles, y la distinción es parte del contenido: un resumen de búsqueda producido por un modelo es exactamente el lugar donde aparecen citas plausibles pero inexistentes.

- **Verificado**: URL primaria confirmada.
- **Estándar**: obra suficientemente conocida como para citarse por autor/título/año, sin URL confirmada acá. Verificar el identificador exacto antes de publicar.
- **No confirmado**: apareció en búsquedas pero sin fuente primaria. **No citar** sin verificación propia. Ver la última sección.

## La tradición: conservar lo que no se cerró

### Residual doubt y defeaters (safety assurance)

El antecedente conceptual más cercano no viene de GitHub ni de IA, sino de la ingeniería de sistemas críticos. En Assurance 2.0, Bloomfield y Rushby distinguen tres perspectivas de confianza: positiva, negativa y **residual doubt**. Un *defeater* es una objeción que podría invalidar un argumento de assurance; si no puede eliminarse, puede quedar registrado explícitamente como duda residual, pero la decisión de tolerarlo tiene que ser consciente y quedar documentada. La herramienta CLARISSA soporta defeaters y dudas residuales. (Estándar.)

Esa estructura es isomorfa a la del evento de revisión que define disensor: una objeción se investiga y termina resuelta, refutada, aceptada o escalada; lo que no desapareció queda declarado.

El punto interesante es que el problema **sigue abierto en 2026 dentro de un campo que lleva décadas pensándolo**:

| Trabajo | Aporte | Estado |
|---|---|---|
| [Defeater Cards: Characterizing and Managing Safety Assurance Case Defeaters](https://arxiv.org/abs/2606.11462) (jun 2026) | Los defeaters siguen siendo ad hoc, inconsistentes, difíciles de revisar y sin estándar de documentación. Propone convertirlos en un artefacto estructurado, trazable, auditable y reutilizable. | Verificado |
| [A Taxonomy of Real-World Defeaters in Safety Assurance Cases](https://arxiv.org/abs/2502.00238) (2025) | Taxonomía empírica de defeaters reales. | Verificado |
| [CoDefeater: Using LLMs To Find Defeaters in Assurance Cases](https://arxiv.org/abs/2407.13717) (2024) | Automatiza el hallazgo de defeaters con LLMs. | Verificado |

Es una línea de investigación activa, no un paper suelto, y su diagnóstico de 2026 (ad hoc, sin estándar de documentación, difícil de auditar) es casi la especificación del problema que ataca el artefacto de residuo. Diferencia de dominio: hablan de assurance cases de sistemas críticos, no de code review cotidiano ni de agentes.

Los assurance cases, además, nunca se volvieron práctica normal fuera de safety-critical. Los estudios con practitioners reportan beneficios reconocidos pero tres obstáculos recurrentes: falta de tooling, mala integración con el proceso existente y falta de gente con experiencia. (Estándar.) Eso es una restricción de diseño directa: el residuo no puede exigir una metodología paralela que el desarrollador tenga que "hacer". Tiene que ocurrir dentro de lo que ya usa (agente, git, PR, CI).

### Design rationale y el capture bottleneck

Desde los años 70 y 80 existen sistemas para guardar el razonamiento detrás de una decisión, no sólo la decisión: IBIS (Kunz y Rittel, 1970), gIBIS (Conklin y Begeman, ACM TOIS, 1988), QOC (MacLean et al., 1991), DRL, PHI. Guardaban qué problema se discutió, qué alternativas hubo, argumentos a favor y en contra, por qué se eligió una y se rechazaron las otras. (Estándar.)

Conceptualmente: *no guardes sólo la decisión final, guardá también el desacuerdo que llevó hasta ella.* Es la misma intuición.

**No prosperó en el software mainstream**, y la razón está documentada. Burge (AI EDAM, 2008), resumiendo más de tres décadas de investigación, concluye que nunca faltó gente convencida de la utilidad, pero seguía sin estar claro que los beneficios compensaran el costo de captura, con poca evaluación empírica y transferencia incierta a la práctica. (Estándar.)

La encuesta de Tang, Babar, Gorton y Han a 81 arquitectos ([WICSA 2005](https://bibtex.github.io/WICSA-2005-TangBGH.html) / [JSS 2006](https://www.sciencedirect.com/science/article/abs/pii/S0164121206001415), verificado: existen los dos papers y el n=81) captura la paradoja: los practicantes reconocen el valor del rationale y lo consultan, pero no lo documentan. Las razones dominantes reportadas son falta de tiempo y presupuesto, y falta de herramientas adecuadas; muy pocos dicen que no sirva.

> **Pendiente antes de citar**: los porcentajes que circulan sobre esta encuesta (60,5 % falta de tiempo, 29,6 % falta de herramientas, 9,9 % no lo considera útil, 74 % olvida sus propias razones, ~80 % no entiende las de otro arquitecto sin rationale) no fueron confirmados contra el PDF en esta búsqueda, y los dos papers no son intercambiables. Verificar cifra por cifra y fijar cuál de las dos versiones se cita.

La forma del fracaso es lo importante, y se conoce como **capture bottleneck**: el costo lo paga quien produce, ahora; el beneficio lo recibe otro, tal vez, en seis meses. El productor tenía que interrumpir el trabajo, abrir otra herramienta, aprender una representación nueva y redactar a mano. La literatura de rationale discute explícitamente ese conflicto entre maximizar el beneficio del consumidor y minimizar el esfuerzo del productor.

La excepción confirma la regla: **DRed**, evolución de IBIS diseñada deliberadamente para bajar el costo de captura, sí consiguió uso industrial sostenido dentro de una multinacional aeroespacial, pese a ser prácticamente un prototipo de investigación. Cuando se investigó por qué algunos diseñadores no lo usaban, las razones fueron compatibilidad de plataforma, falta de tiempo y la percepción de que ciertas tareas no lo justificaban. (Estándar.) Es decir: **cuando la fricción baja lo suficiente y el valor de la decisión es lo bastante grande, el rationale funciona.**

## El presente: 2026

### Revisión adversarial multi-agente

Ya está apareciendo por varios lados, y esto es lo que **descarta a la revisión adversarial cruzada como la contribución original** del método.

| Trabajo | Qué hace | Estado |
|---|---|---|
| [Adversarial Review: Cooperative Code Review through Structured Disagreement](https://openreview.net/forum?id=fOHvpLs6zp) (workshop AI4GOOD, jun 2026) | Protocolo cooperativo con agente principal, revisor y crítico que audita la revisión mediante desacuerdo estructurado antes de editar o commitear. | Verificado |
| [Structured Disagreement for Grounded Agentic Code Review](https://openreview.net/forum?id=h9UPyo3bbp) | Vocabulario casi idéntico. | Verificado (existe; sin leer) |
| [Refute-or-Promote: An Adversarial Stage-Gated Multi-Agent Review Methodology](https://arxiv.org/abs/2604.19049) | Patrón de confiabilidad en inferencia: mandatos adversariales de refutación en cada compuerta de promoción, asimetría de contexto, revisores en frío para reducir cascadas de anclaje, y un **Cross-Model Critic**. Campaña de 31 días sobre 7 targets (librerías de seguridad, estándar ISO C++, compiladores): ~79 % de 171 candidatos descartados antes de disclosure (agregado retrospectivo); 83 % de kill rate prospectivo en el subconjunto de protocolo consolidado (lcms2, wolfSSL, n=30). | Verificado |
| [alecnielsen/adversarial-review](https://github.com/alecnielsen/adversarial-review) | Claude + Codex: revisiones independientes, cross-review, meta-review y síntesis iterativa, guardando artifacts de cada ronda. Máximo de iteraciones configurable, detección de falta de progreso, y circuit breaker ante desacuerdo persistente (5+ iteraciones) o problemas repetidos. | Verificado |

El foco de todos es **conseguir una mejor revisión** mediante agentes que discuten. Ninguno convierte el desacuerdo residual en un artefacto de provenance gobernado por git.

El repositorio de Nielsen es el más cercano al método en la práctica: misma decorrelación Claude/Codex, y un circuit breaker que en espíritu es `escalated_open` (dejar de fingir que hay consenso cuando el desacuerdo persiste). La diferencia no está en el método sino en la finalidad: su loop existe para converger en fixes y salir, y sus artifacts son transcripts y resultados del proceso, no una declaración portable con alcance de git, semántica de rancidez, testigo de integración, evidencia de solo agregar y política de merge. El propio proyecto se presenta como prototipo experimental. Citarlo en trabajo relacionado conviene: reconocerlo deja más nítido qué agrega el artefacto.

### Sobre el sustento empírico de R4

Conviene ser preciso acá, porque es la regla más fácil de sobrevender.

Lo que **sí** está publicado y verificado: Adversarial Review observa en SWE-PRBench un modo de falla de **falso consenso** en la variante ingenua (los agentes convergen sin evidencia suficiente) y concluye que la cooperación confiable requiere desacuerdo estructurado y anclado en evidencia, no consenso. Refute-or-Promote usa un Cross-Model Critic y sus autores sostienen que la revisión cross-family puede detectar **blind spots correlacionados** que la same-family pierde, con una campaña que reporta tasas altas de descarte antes de promover.

Lo que **no** está publicado, y no debe afirmarse: una ablación limpia same-family contra cross-family que permita atribuir causalmente el falso consenso a la familia compartida. El falso consenso de Adversarial Review apoya con fuerza la necesidad de mecanismos contra el consenso superficial, pero no identifica la familia como la causa. Y el cross-family de Refute-or-Promote es fundamento de diseño dentro de una campaña de defect discovery, no un experimento controlado sobre la variable familia.

Formulación defendible: **R4 es un diseño plausible con sustento convergente en la literatura, no una regla empíricamente demostrada.** La decorrelación de familias está bien motivada; la magnitud de su efecto está sin medir, y medirla es trabajo futuro concreto para este proyecto.

### Governance runtimes y contratos de delegación

| Trabajo | Qué hace | Estado |
|---|---|---|
| [Nidus: Externalized Reasoning for AI-Assisted Engineering](https://arxiv.org/abs/2604.05080) (abr 2026) | Governance runtime que mecaniza el V-model: una "living specification" en S-expression es a la vez diseño, conjunto de obligaciones de prueba y autoridad de gobernanza, verificada con Z3 **en cada commit**. Self-hosted: tres familias (Claude, Gemini, Codex) entregaron un sistema de 100.000 líneas bajo obligaciones de prueba. | Verificado |
| [Software Delegation Contracts: Measuring Reviewability in AI Coding-Agent Work](https://arxiv.org/abs/2606.17099) (jun 2026) | 64 corridas de agentes sobre un entorno instrumentado con defectos sembrados, tres condiciones (prompt tipo issue, contrato explícito, contrato con evidence bundle), 192 revisiones ciegas a condición. | Verificado |
| [Trust Without Trusting: A Recomputable Trust Protocol for Autonomous Agents](https://arxiv.org/abs/2605.06738) | Propone que el cumplimiento no dependa de creerle a quien aplica la regla, sino que pueda ser **recomputado por terceros** desde evidencia anclada: convertir "¿aplicó correctamente sus propias reglas?" de afirmación en hecho recomputable. | Verificado (sin leer entero) |

**Nidus es el antecedente más cercano en principio de diseño**, y define lo que este proyecto **no puede reclamar**. Su tesis es literalmente la de disensor: los invariantes de ingeniería no se sostienen como comportamiento aprendido, y el assurance exige enforcement por un mecanismo **externo al proponente**. Más todavía, declara entre sus contribuciones la *governance theater prevention*: que la evidencia de cumplimiento no pueda fabricarse dentro del camino de mutación que gobierna — o sea, ataca deliberadamente una versión del mismo problema de Goodhart que se discute abajo.

Consecuencia directa para el paper: **no escribir nada parecido a "no existen mecanismos externos de gobernanza para coding agents".** Sería falso y verificablemente falso.

La diferencia defendible es más estrecha y más interesante que esa. Nidus mecaniza **obligaciones que deben quedar satisfechas**; disensor convierte en artefacto **lo que sobrevivió sin poder cerrarse**. Dicho brutalmente:

- Nidus pregunta: *¿cumpliste las obligaciones?*
- disensor pregunta: *¿qué objeción sobrevivió aun después de intentar resolverla?*

Ahí sí queda espacio conceptual.

**Software Delegation Contracts** es la referencia empírica más valiosa, con una salvedad de lectura. Su resultado principal es más preciso (y más útil) que la versión que circula resumida: los contratos **no cambiaron los resultados objetivos** (las 64 corridas pasaron los acceptance checks ocultos, con cero violaciones de alcance), pero sí la **revisabilidad**: suficiencia de evidencia mejor en 22 de 30 comparaciones pareadas y peor en ninguna (+0,83 en escala de 5, p < 0,0001, Cliff's δ = 0,66), y menos ambigüedad para el revisor (p = 0,035), a un costo de +13 % de tokens y +38 % de tiempo. Las secciones de riesgo residual y los checklists de revisor aparecieron cuando el contrato las exigía. Su conclusión textual: *delegation contracts buy reviewability rather than correctness*.

Esa frase es la tesis de disensor mejor formulada que en el README: el artefacto no promete que el código esté bien, promete que alguien pueda revisarlo sabiendo dónde mirar. Y el detalle del riesgo residual sostiene la hipótesis de fondo del protocolo: **un agente no conserva espontáneamente aquello que no pudo demostrar; hay que obligarlo.** Es un piloto de un solo autor con tareas chicas: citar como evidencia preliminar, no como establecido.

### Provenance de la cadena de suministro

SLSA está desarrollando su **Source Track** para demostrar propiedades sobre cómo se produjo una revisión de código: quién intervino, qué controles hubo, qué revisión existió. Define como amenaza explícita **modificar código después de la revisión**, y exige como mitigación invalidar aprobaciones cuando cambia la revisión. También reconoce amenazas que no puede resolver: un revisor engañado por código malicioso, o el rubber stamping. **gittuf** (OpenSSF) registra aprobaciones de PR como attestations dentro del repositorio y permite verificar que satisfagan una política. (Estándar; ambos proyectos son públicos y activos.)

Eso está conceptualmente muy cerca de G6 (anti-rancidez) y G7 (testigo de integración), y conviene decirlo explícitamente en lugar de dejar que un revisor lo descubra: la anti-rancidez de disensor es la misma amenaza que SLSA nombra, aplicada a una revisión adversarial en lugar de a una aprobación humana.

## Dónde se ubica disensor

| Sistema | Qué demuestra |
|---|---|
| SLSA / gittuf / in-toto | "Esta revisión o aprobación ocurrió sobre esta revisión del código fuente." |
| Assurance 2.0 / Defeater Cards | "Estas objeciones existieron y estas dudas quedaron sin resolver." |
| IBIS / design rationale | "Se consideraron estas alternativas y estos argumentos, y se decidió esto." |
| Adversarial Review / Refute-or-Promote / adversarial-review | "El desacuerdo estructurado entre agentes produce hallazgos de mayor precisión." |
| Software Delegation Contracts | "El work package del agente puede hacerse revisable exigiendo estructura." |
| Nidus | "Estas obligaciones de ingeniería se verificaron externamente en cada commit." |
| Trust Without Trusting | "El cumplimiento puede recomputarse desde afuera, sin confiar en el operador." |
| **disensor** | **"Ocurrió una revisión adversarial entre familias sobre este estado exacto del código, ésta fue la disposición terminal de cada hallazgo, y esto quedó sin poder cerrarse."** |

La contribución no es ninguno de los componentes por separado. Es la intersección: qué quedó sin resolver después de una revisión adversarial, sobre qué estado exacto del código ocurrió esa revisión, y qué partes de esa historia pueden hacerse exigibles por CI.

### Cómo formular el claim de novedad

Tres formulaciones que **no** se pueden usar, cada una invalidada por trabajo verificado arriba:

- ~~"introduce la revisión de código adversarial con IA"~~ — Adversarial Review, Refute-or-Promote, adversarial-review.
- ~~"introduce gobernanza para coding agents"~~ — Nidus.
- ~~"introduce el desacuerdo estructurado"~~ — Adversarial Review, Structured Disagreement.

La formulación defendible es más estrecha, y el *to our knowledge* no es cortesía sino requisito, porque no se hizo todavía una búsqueda bibliográfica sistemática:

> To our knowledge, prior work separately addresses adversarial multi-agent review, reviewable agent work packages, externally enforced engineering obligations, and recomputable provenance. Disensor explores a narrower intersection: treating unresolved outcomes of cross-family adversarial code review as a versioned, Git-scoped evidence artifact whose freshness and integration coverage can be mechanically enforced at merge time.

Y la tesis del proyecto conviene enunciarla al nivel correcto. No "produce código correcto", ni siquiera "mejora la revisión", sino: **hacer revisable y auditable el estado epistemológico con el que termina una revisión adversarial.** Es la misma separación que Software Delegation Contracts midió y nombró: *reviewability, not correctness*.

## Qué puede verificar el artefacto y qué no

Esta tabla debería estar en el cuerpo del paper y no relegada a limitaciones, porque es lo que impide leer `.residue/` como una certificación de calidad emitida por IA. Divide el artefacto en dos clases de propiedad que hoy conviven mezcladas: **provenance computable** y **contenido declarado**.

| Propiedad | ¿La verifica disensor? | Cómo |
|---|---|---|
| El commit revisado existe | Sí | Objeto de git |
| El commit pertenece al PR | Sí | G5, rango `merge-base..head` |
| El código cambió después de la revisión | Sí | G6, anti-rancidez |
| Alguna revisión vio el árbol integrado completo | Sí | G7, testigo de integración |
| La evidencia previa no fue alterada ni borrada | Sí | G8, solo agregar |
| El artefacto es internamente coherente | Sí | Esquema y reglas R0–R10 |
| Alguien declaró haber revisado ese estado | Sí | Es lo que el artefacto afirma |
| El revisor realmente razonó en profundidad | **No** | Declaración |
| El modelo declarado fue efectivamente quien revisó | **No, hoy** | Declaración; sin attestation criptográfica |
| La refutación es intelectualmente correcta | **No** | Declaración |
| No existen otros riesgos sin declarar | **No** | Fuera del alcance de cualquier artefacto |

Todo lo verificable es **un hecho sobre git**, no una afirmación del agente. Ésa es la propiedad que hace que la columna izquierda sea defendible y la derecha, honesta.

De ahí sale la promesa correcta del artefacto, que es más modesta y mucho más sostenible que la ingenua:

- No: *evidencia de que la revisión fue buena.*
- Sí: *evidencia de que un proceso de revisión determinado ocurrió sobre un estado determinado del código fuente, más una declaración de su remanente sin resolver.*

Lo primero es casi imposible de demostrar desde afuera. Lo segundo contiene una parte mecánicamente verificable.

## Qué advierte la historia

### El capture bottleneck: la oportunidad

El fracaso de design rationale **no fue por falta de interés en conservar las dudas**. La evidencia dice lo contrario: los desarrolladores querían el artefacto cuando les tocaba consumirlo. Lo que fracasó fue la ecuación *beneficio futuro e incierto > costo manual inmediato*.

En 1995, "documentá todas las objeciones que consideraste" implicaba trabajo humano. En 2026, cerrar el evento de revisión que el agente acaba de hacer implica principalmente trabajo de máquina: la información **ya existe** como subproducto de una interacción que ya ocurrió. No se le pide al desarrollador que reconstruya rationale; se estructura lo que acaba de pasar.

Y el beneficio deja de ser diferido, que era la otra mitad del problema: el gate consume el artefacto **ahora** y puede decir "no mergeás porque esa revisión ya no corresponde al código actual". No hay que esperar seis meses a que alguien pregunte por qué se hizo algo.

### Residuo y no cobertura: una elección epistemológica, no de volumen

IBIS intentaba conservar *todo* el razonamiento relevante. Declarar **residuo y no cobertura** es la respuesta directa a ese fracaso, y es cierto que baja el volumen en órdenes de magnitud: cien mil tokens de interacción comprimen a unos pocos hallazgos con estado terminal y una o dos incertidumbres sin cerrar, con mejor relación señal/ruido que un transcript o un grafo de rationale completo.

Pero la compresión es el argumento secundario. El primero es que **invierte la carga semántica del artefacto**.

Un artefacto de cobertura tiende a leerse así:

```
✅ revisamos seguridad
✅ revisamos arquitectura
✅ revisamos tests
✅ revisamos edge cases
```

Formalmente eso no afirma que todo esté bien. Psicológicamente se convierte en eso con una facilidad enorme, y ése es exactamente el fracaso que hay que evitar.

Un artefacto de residuo dice otra cosa: *éstas son precisamente las cosas que el proceso no logró hacer desaparecer.* No prueba que sean las únicas, no prueba que el resto esté bien, y no se presta a transformarse visualmente en un sello de calidad.

- Cobertura pregunta: **¿qué comprobamos?**
- Residuo pregunta: **¿qué seguimos sin poder cerrar?**

La primera dirige la atención del revisor humano hacia lo ya hecho; la segunda, hacia lo que falta. Es una decisión de diseño bastante más profunda que ahorrar tokens.

### El riesgo Nº1: Goodhart

La analogía con design rationale se rompe en un punto, y es el punto que puede matar a disensor.

El análisis del capture bottleneck es correcto pero está incompleto. Sí: el costo de generar evidencia útil baja a casi cero porque la produce el agente. Pero simultáneamente el costo de generar **evidencia cosmética** baja a casi cero, por la misma razón.

Y ahí aparece el problema propiamente moderno. Si CI exige residuo declarado, lo que el agente aprende operacionalmente es:

```
quiero mergear
  → necesito un residue válido
  → produzco JSON que satisfaga el gate
```

No necesariamente:

```
quiero expresar sinceramente mi incertidumbre epistemológica
```

IBIS moría por fricción; disensor puede morir por Goodhart. Un agente al que se le exige declarar residuo bajo pena de no mergear tiene incentivo estructural a declarar un residuo cosmético: verdadero, irrelevante y barato. La literatura de rationale no advierte sobre esto porque ahí el productor era humano y la ceremonia funcionaba, sin querer, como filtro. Nidus ataca explícitamente una versión de este mismo problema con su *governance theater prevention*.

El README ya admite el límite: la máquina detecta el campo vacío y el marcador genérico, no la declaración falsa, y el muestreo humano de PRs cerrados sigue siendo la única defensa real contra el cumplimiento cosmético.

Lo que conviene hacer explícito, y en el cuerpo del paper y no en limitaciones, es **por qué G5, G6 y G7 son una respuesta parcial pero real**: no creen lo que el agente dice sobre el árbol, lo reconstruyen desde git. No verifican el contenido del residuo (nada lo hace), pero sí que la revisión haya ocurrido sobre este árbol, en este par de commits, incluyendo la integración. Un residuo cosmético sigue siendo posible; una revisión inexistente o rancia, no.

### La pregunta de investigación

De todo lo anterior sale la pregunta que probablemente sea la más interesante del proyecto:

> ¿Cómo se hace obligatorio declarar incertidumbre sin convertir la declaración de incertidumbre en otra casilla que el agente aprende a marcar?

Y sale también la dirección de evolución, que no es la obvia. **La evolución natural de disensor no es hacer cada vez más obligatorio el JSON.** Es aumentar la proporción del artefacto que puede verificarse independientemente y reducir la que necesita ser creída — mover filas de la mitad inferior de la tabla de arriba a la superior.

Trust Without Trusting marca el horizonte de esa dirección: *declarado → verificado externamente → recomputable de forma independiente*. Hoy el artefacto mezcla las dos primeras clases sin distinguirlas en su propia estructura; hacer esa distinción explícita en el esquema sería un paso concreto en esa dirección. La attestation criptográfica de qué modelo revisó realmente es otro: es la fila de la tabla que hoy dice "No, hoy" y podría no decirlo.

### La restricción de producto

De los assurance cases y del rationale sale la misma lección, y es una restricción dura: **no inventar una metodología que el desarrollador tenga que "hacer"**. Los obstáculos reportados no fueron conceptuales sino de tooling e integración. El residuo tiene que emitirse dentro del agente, git, el PR y CI, sin sistema paralelo, sin representación nueva que aprender, y sin que nadie interrumpa lo que estaba haciendo. Es exactamente lo que apuntan `disensor init`, la skill y `disensor guide`, y conviene tratar cualquier fricción agregada ahí como riesgo existencial y no como detalle de UX.

## Referencias no confirmadas

Aparecieron en búsqueda pero **sin fuente primaria verificable**. No citar sin confirmación propia:

- **Garda** (governance para coding agents, con lifecycle, gates, revisión independiente y disposición explícita de findings). La única fuente encontrada es un posteo de LinkedIn. Sería, si existe como se describe, el proyecto contemporáneo funcionalmente más cercano; hay que encontrar el repositorio o la documentación.
- **Agent Audits** (acceptance criteria → evidence → review → check → report).
- El uso del término *residual risk* por **Critique** para separar lo que no se pudo verificar de los hallazgos concretos. Conceptualmente sano y muy cercano al vocabulario del artefacto, pero es output de revisión y no artefacto persistido; hace falta la fuente.

Pendientes de lectura completa, no sólo de existencia: Nidus, Trust Without Trusting, Refute-or-Promote y Structured Disagreement for Grounded Agentic Code Review. De los cuatro, **Nidus es el que más puede afectar el claim de novedad** y debería leerse entero antes de publicar.

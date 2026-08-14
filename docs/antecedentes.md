# Antecedentes

Este documento ubica a disensor respecto de lo que ya existe. No es una sección de trabajo relacionado terminada: es el insumo verificado para escribirla, y está acá porque el claim de novedad del método necesita sostenerse contra literatura concreta y no contra la ausencia de búsqueda.

La idea central del artefacto (conservar explícitamente lo que una evaluación no pudo cerrar) **no es nueva**. Tiene al menos dos tradiciones detrás, una de las cuales fracasó de una forma documentada y muy relevante. Lo que no encontré es la composición completa: revisión adversarial entre familias + disposición terminal de cada hallazgo + residuo explícito + provenance exacta de git + anti-rancidez + gate de merge + artefacto portable.

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
| [Refute-or-Promote: An Adversarial Stage-Gated Multi-Agent Review Methodology](https://arxiv.org/abs/2604.19049) | Revisión adversarial con stage gates para descubrimiento de defectos de alta precisión. | Verificado (existe; sin leer) |
| [alecnielsen/adversarial-review](https://github.com/alecnielsen/adversarial-review) | Claude + Codex en loop de debate, con protocolo de desacuerdo: escala a humano tras 3 rondas sin resolver, circuit breaker a las 5. | Verificado |

El foco de todos es **conseguir una mejor revisión** mediante agentes que discuten. Ninguno convierte el desacuerdo residual en un artefacto de provenance gobernado por git. El repositorio de Nielsen es el más cercano al método en la práctica (misma decorrelación Claude/Codex, misma escalación a humano); lo que no tiene es artefacto versionado ni enforcement.

**Hallazgo aprovechable, no competencia**: el paper de Adversarial Review reporta que en SWE-PRBench la variante ingenua expone un modo de falla de **falso consenso**, y que la cooperación confiable requiere desacuerdo estructurado y anclado en evidencia, no consenso. Eso es evidencia publicada a favor de la regla R4 (decorrelación de familias entre generador y revisor) y del requisito de evidencia en las refutaciones verificables. Conviene citarlo como sustento, no como trabajo rival.

### Governance runtimes y contratos de delegación

| Trabajo | Qué hace | Estado |
|---|---|---|
| [Nidus: Externalized Reasoning for AI-Assisted Engineering](https://arxiv.org/abs/2604.05080) (abr 2026) | Governance runtime que mecaniza el V-model: una "living specification" en S-expression es a la vez diseño, conjunto de obligaciones de prueba y autoridad de gobernanza, verificada con Z3 **en cada commit**. Self-hosted: tres familias (Claude, Gemini, Codex) entregaron un sistema de 100.000 líneas bajo obligaciones de prueba. | Verificado |
| [Software Delegation Contracts: Measuring Reviewability in AI Coding-Agent Work](https://arxiv.org/abs/2606.17099) (jun 2026) | 64 corridas de agentes sobre un entorno instrumentado con defectos sembrados, tres condiciones (prompt tipo issue, contrato explícito, contrato con evidence bundle), 192 revisiones ciegas a condición. | Verificado |
| [Trust Without Trusting: A Recomputable Trust Protocol for Autonomous Agents](https://arxiv.org/abs/2605.06738) | Vecino del lado provenance/verificabilidad. | Verificado (existe; sin leer) |

**Nidus es el antecedente más cercano en principio de diseño.** Su tesis es literalmente la de disensor: los invariantes de ingeniería no se sostienen como comportamiento aprendido, y el assurance exige enforcement por un mecanismo **externo al proponente**. La diferencia es qué se conserva: Nidus verifica que las obligaciones de prueba se satisfagan; no conserva lo insatisfecho como entidad de primera clase.

**Software Delegation Contracts** es la referencia empírica más valiosa, con una salvedad de lectura. Su resultado principal es más preciso (y más útil) que la versión que circula resumida: los contratos **no cambiaron los resultados objetivos** (las 64 corridas pasaron los acceptance checks ocultos, con cero violaciones de alcance), pero sí la **revisabilidad**: suficiencia de evidencia mejor en 22 de 30 comparaciones pareadas y peor en ninguna (+0,83 en escala de 5, p < 0,0001, Cliff's δ = 0,66), y menos ambigüedad para el revisor (p = 0,035), a un costo de +13 % de tokens y +38 % de tiempo. Su conclusión textual: *delegation contracts buy reviewability rather than correctness*.

Esa frase es la tesis de disensor mejor formulada que en el README: el artefacto no promete que el código esté bien, promete que alguien pueda revisarlo sabiendo dónde mirar. Es un piloto de un solo autor con tareas chicas: citar como evidencia preliminar, no como establecido.

### Provenance de la cadena de suministro

SLSA está desarrollando su **Source Track** para demostrar propiedades sobre cómo se produjo una revisión de código: quién intervino, qué controles hubo, qué revisión existió. Define como amenaza explícita **modificar código después de la revisión**, y exige como mitigación invalidar aprobaciones cuando cambia la revisión. También reconoce amenazas que no puede resolver: un revisor engañado por código malicioso, o el rubber stamping. **gittuf** (OpenSSF) registra aprobaciones de PR como attestations dentro del repositorio y permite verificar que satisfagan una política. (Estándar; ambos proyectos son públicos y activos.)

Eso está conceptualmente muy cerca de G6 (anti-rancidez) y G7 (testigo de integración), y conviene decirlo explícitamente en lugar de dejar que un revisor lo descubra: la anti-rancidez de disensor es la misma amenaza que SLSA nombra, aplicada a una revisión adversarial en lugar de a una aprobación humana.

## Dónde se ubica disensor

| Sistema | Qué demuestra |
|---|---|
| SLSA / gittuf / in-toto | "Esta revisión o aprobación ocurrió sobre esta revisión del código fuente." |
| Assurance 2.0 / Defeater Cards | "Estas objeciones existieron y estas dudas quedaron sin resolver." |
| IBIS / design rationale | "Se consideraron estas alternativas y estos argumentos, y se decidió esto." |
| Adversarial Review / Refute-or-Promote | "El desacuerdo entre agentes produce mejores hallazgos." |
| Nidus | "Estas obligaciones de prueba se verificaron externamente en cada commit." |
| **disensor** | **"Ocurrió una revisión adversarial entre familias sobre este código exacto, éstos fueron sus hallazgos, ésta fue su disposición terminal, y esto quedó sin poder cerrarse."** |

La contribución no es ninguno de los componentes por separado. Es la composición: residuo explícito + disposición terminal + identidad y familia del revisor + provenance exacta de commit + anti-rancidez + testigo de integración + evidencia de solo agregar + gate de merge, en un artefacto portable y versionado. No encontré un equivalente directo, lo que no autoriza a afirmar que no exista.

## Qué advierte la historia

### El capture bottleneck: la oportunidad

El fracaso de design rationale **no fue por falta de interés en conservar las dudas**. La evidencia dice lo contrario: los desarrolladores querían el artefacto cuando les tocaba consumirlo. Lo que fracasó fue la ecuación *beneficio futuro e incierto > costo manual inmediato*.

En 1995, "documentá todas las objeciones que consideraste" implicaba trabajo humano. En 2026, cerrar el evento de revisión que el agente acaba de hacer implica principalmente trabajo de máquina: la información **ya existe** como subproducto de una interacción que ya ocurrió. No se le pide al desarrollador que reconstruya rationale; se estructura lo que acaba de pasar.

Y el beneficio deja de ser diferido, que era la otra mitad del problema: el gate consume el artefacto **ahora** y puede decir "no mergeás porque esa revisión ya no corresponde al código actual". No hay que esperar seis meses a que alguien pregunte por qué se hizo algo.

Segunda diferencia con IBIS, deliberada: IBIS intentaba conservar *todo* el razonamiento relevante. Declarar **residuo y no cobertura** es la respuesta directa a ese fracaso. Cien mil tokens de interacción comprimen a unos pocos hallazgos con estado terminal y una o dos incertidumbres sin cerrar. El volumen es órdenes de magnitud menor y la relación señal/ruido, mucho mejor que la de un transcript o un grafo de rationale completo.

Y hay una razón más fuerte que el tamaño para preferir residuo a cobertura: cambia **quién lleva la carga de la prueba**. Un grafo de rationale completo se lee como sello de calidad. Una lista de lo que no se pudo cerrar no se puede leer así ni queriendo.

### El riesgo que la historia no advierte

La analogía con design rationale se rompe en un punto, y es el punto que puede matar a disensor.

Si el costo de producir residuo tiende a cero **porque lo produce el agente**, el costo de producir residuo **falso** también tiende a cero. IBIS moría por fricción; disensor puede morir por Goodhart. Un agente al que se le exige declarar residuo bajo pena de no mergear tiene incentivo estructural a declarar un residuo cosmético: verdadero, irrelevante y barato. La literatura de rationale no advierte sobre esto porque ahí el productor era humano y la ceremonia funcionaba, sin querer, como filtro.

El README ya lo admite: la máquina detecta el campo vacío y el marcador genérico, no la declaración falsa, y el muestreo humano de PRs cerrados sigue siendo la única defensa real contra el cumplimiento cosmético.

Lo que conviene hacer explícito es **por qué G5, G6 y G7 valen más de lo que parecen** frente a esta objeción: no verifican el contenido del residuo (nada lo hace), pero sí que la revisión haya ocurrido sobre este árbol, en este par de commits, incluyendo la integración. Es la única parte de la declaración que no depende de la buena fe del declarante. Un residuo cosmético sigue siendo posible; una revisión inexistente o rancia, no. Ese es el argumento a poner en el paper, porque la objeción es inmediata y previsible.

### La restricción de producto

De los assurance cases y del rationale sale la misma lección, y es una restricción dura: **no inventar una metodología que el desarrollador tenga que "hacer"**. Los obstáculos reportados no fueron conceptuales sino de tooling e integración. El residuo tiene que emitirse dentro del agente, git, el PR y CI, sin sistema paralelo, sin representación nueva que aprender, y sin que nadie interrumpa lo que estaba haciendo. Es exactamente lo que apuntan `disensor init`, la skill y `disensor guide`, y conviene tratar cualquier fricción agregada ahí como riesgo existencial y no como detalle de UX.

## Referencias no confirmadas

Aparecieron en búsqueda pero **sin fuente primaria verificable**. No citar sin confirmación propia:

- **Garda** (governance para coding agents, con lifecycle, gates, revisión independiente y disposición explícita de findings). La única fuente encontrada es un posteo de LinkedIn. Sería, si existe como se describe, el proyecto contemporáneo funcionalmente más cercano; hay que encontrar el repositorio o la documentación.
- **Agent Audits** (acceptance criteria → evidence → review → check → report).
- El uso del término *residual risk* por **Critique** para separar lo que no se pudo verificar de los hallazgos concretos. Conceptualmente sano y muy cercano al vocabulario del artefacto, pero es output de revisión y no artefacto persistido; hace falta la fuente.

Pendientes de lectura completa, no sólo de existencia: Nidus, Trust Without Trusting, Refute-or-Promote y Structured Disagreement for Grounded Agentic Code Review. De los cuatro, **Nidus es el que más puede afectar el claim de novedad** y debería leerse entero antes de publicar.

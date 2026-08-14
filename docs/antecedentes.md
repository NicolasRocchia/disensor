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

## La frontera de assurance

Esta sección debería estar en el cuerpo del paper y no relegada a limitaciones, porque es lo que impide leer `.residue/` como una certificación de calidad emitida por IA.

Lo importante es que **no es una métrica escalar**. La tentación de decir "17 de 24 propiedades verificables = 71 %" lleva directo al Goodhart de la sección anterior: se mejora el ratio agregando propiedades triviales de verificar. Lo que sirve no es el conteo sino el mapa, y el mapa necesita tres columnas: qué estado tiene hoy la propiedad, **cuál es su raíz de confianza**, y cuál es su **techo** — hasta dónde podría llegar, incluso en el mejor caso.

| Propiedad | Estado hoy | Raíz de confianza | Techo |
|---|---|---|---|
| El commit revisado existe y pertenece al PR | Verificable | git (G5) | Verificable |
| El código no cambió después de la revisión | Verificable | git (G6) | Verificable |
| Alguna revisión vio el árbol integrado completo | Verificable | git (G7) | Verificable |
| La evidencia previa no fue alterada | Verificable | git (G8) | Verificable |
| El artefacto es internamente coherente | Verificable | esquema y R0–R10 | Verificable |
| Se invocó al revisor declarado | Declarado | el agente | Attestation de invocación posible |
| El modelo servido era el declarado | Declarado | el proveedor | Parcialmente movible (ver abajo) |
| El revisor razonó en profundidad | Juicio | revisor / humano | No mecanizable |
| La refutación es intelectualmente correcta | Juicio | revisor / humano | No mecanizable plenamente |
| No existen riesgos sin declarar | Mundo abierto | — | **No verificable en principio** |

El progreso del protocolo no se enuncia entonces como "subió a 73 %", sino como una transición nominal: *v0.6 movió esta propiedad de declarada a verificada mecánicamente, con esta raíz de confianza.* Eso es auditable y difícil de maquillar agregando quince propiedades triviales.

De ahí sale la promesa correcta del artefacto, más modesta y mucho más sostenible que la ingenua:

- No: *evidencia de que la revisión fue buena.*
- Sí: *evidencia de que un proceso de revisión determinado ocurrió sobre un estado determinado del código fuente, más una declaración de su remanente sin resolver.*

### Relación con Nidus, ajustada

Nidus **sí** enmarca su progreso como expansión de lo mecánicamente exigible, y afirmar lo contrario sería falso: su conjunto de obligaciones **crece monótonamente**, todo estado del artefacto satisface las obligaciones activas, y las fallas observadas se convierten en obligaciones nuevas mediante mapeos falla → causa raíz → obligación. También declara el límite: la verificación es sólida sólo respecto de las obligaciones actualmente modeladas, y no garantiza propiedades que no fueron modeladas.

Lo que no encontré en Nidus es la clasificación misma: *esta propiedad era declarativa y ahora es verificable; ésta sigue dependiendo de confianza y de quién; ésta es intrínsecamente no verificable.* Nidus expande la superficie exigible y reconoce que es incompleta; no mapea las clases de propiedad ni sus raíces de confianza.

La contribución potencial, entonces, es estrecha y enunciable así: **hacer explícita la frontera entre propiedades declaradas, verificadas y fundamentalmente no verificables, y usar las transiciones nominales entre esas clases como criterio de evolución del protocolo.**

### La salida a la contradicción con "residuo, no cobertura"

Hay una objeción obvia: mover la fila "no existen riesgos sin declarar" hacia arriba obligaría a declarar que corrió SAST, que corrió el fuzzer, que hay 95 % de cobertura — y eso reconstruye el artefacto de cobertura que el proyecto rechazó.

La salida es no intentar nunca mover esa fila. Queda marcada de forma permanente como **afirmación de mundo abierto, no verificable en principio**, y eso es parte de la filosofía del protocolo, no una carencia a resolver.

Lo que sí puede moverse es una propiedad mucho más estrecha, y la distinción es la que salva la coherencia:

> **Verificar que un análisis ocurrió ≠ verificar que el análisis fue exhaustivo.**

```
VERIFICABLE:   Semgrep 1.x corrió con ruleset hash ABC sobre el commit DEF.
NO AFIRMADO:   Semgrep habría detectado toda vulnerabilidad relevante.
```

Con esa separación, disensor puede aceptar la ejecución de análisis como evidencia sin convertirse en un artefacto de cobertura. La contradicción aparece recién si se agregan los checks y se da el salto a "software revisado". Ese salto es precisamente el que el protocolo no debe dar.

## Identidad del modelo revisor: qué es posible hoy

Ésta es la fila más interesante de la tabla, porque es donde se ve que "declarado / verificado" es una dicotomía demasiado pobre: hay varias raíces de confianza distintas, y la diferencia entre ellas importa.

| Trabajo | Qué establece | Estado |
|---|---|---|
| [NanoZK: Layerwise Zero-Knowledge Proofs for Verifiable LLM Inference](https://arxiv.org/abs/2603.18046) (ICLR 2026) | Prueba en conocimiento cero de que un output corresponde a ejecutar los pesos comprometidos en una raíz Merkle pública. Halo2 con IPA, sin trusted setup. A escala GPT-2: 43 s de prueba, 6,9 KB, 23 ms de verificación, 52× sobre EZKL. Parte del problema exacto: las APIs actuales no ofrecen binding criptográfico entre la identidad declarada del modelo y la computación real. | Verificado |
| [Attestable Audits: Verifiable AI Safety Benchmarks Using TEEs](https://arxiv.org/abs/2506.23706) | Dentro de un enclave: carga pesos, calcula su hash, vincula modelo y código, ejecuta, y emite remote attestation. Impide la sustitución silenciosa del modelo por parte del host. | Verificado |
| [KBF: Knowledge Boundary as Fingerprint](https://arxiv.org/abs/2605.29524) | Auditoría black-box de bajo costo sobre 16 endpoints de producción: señala las 155 sustituciones económicamente relevantes sin rechazar ningún control del mismo modelo, y detecta routing mixto con 5–10 % del tráfico sustituido. | Verificado |
| [IRIS: Budgeted Black-Box Auditing of Model Substitution and Routing Dilution](https://arxiv.org/abs/2607.20860) | Auditoría sólo sobre el texto devuelto: detecta sustitución completa y dilución fraccional, y atribuye el backend servido. | Verificado |
| [Auditing Black-Box LLM APIs with a Rank-Based Uniformity Test](https://arxiv.org/abs/2506.06975) (2025) | Antecedente directo de la línea de auditoría black-box. | Verificado |

**El techo actual, y es duro.** La criptografía resuelve la integridad de la inferencia *desde el commitment hacia abajo*: se puede probar que una respuesta salió de los pesos `abc123`. Lo que no resuelve es la semántica de arriba: **quién dice que `abc123` es el modelo comercial X.** Si lo dice el proveedor, se sigue confiando en el proveedor para el binding identidad ↔ pesos; si lo certifica un auditor, se confía en el auditor; si hay un registro, en la autoridad del registro. Para pesos abiertos el problema desaparece, porque cualquiera recomputa el commitment desde los pesos públicos. Para modelos propietarios, hace falta alguna raíz de confianza externa.

> Confirmar contra el PDF de NanoZK la formulación exacta del requisito de un registro público de commitments antes de citarlo textualmente; la estructura del límite está clara, el fraseo no lo verifiqué.

Los TEE reducen mucho la confianza en el proveedor pero introducen la confianza en el fabricante del hardware, y la remote attestation prueba qué binario corre, no que ese binario corresponda al código auditado. El fingerprinting black-box es otra vía y está muy activa, pero es **auditoría de identidad**, no attestation: existe además trabajo sobre spoofing de fingerprints frente a proveedores adversariales. Serviría como `CORROBORATED_BY_FINGERPRINT`; nunca como `VERIFIED_MODEL_IDENTITY`.

### La escala de evidencia

De ahí sale que la propiedad no admite dos estados sino varios, y no como escala de calidad sino como **tipos de evidencia con raíces de confianza distintas**:

| Nivel | Qué afirma | En quién se confía |
|---|---|---|
| `DECLARED` | El actor dice que ocurrió | el agente |
| `RUNNER_ATTESTED` | Un entorno controlado observó la invocación | el runner |
| `PROVIDER_ATTESTED` | El proveedor firmó la identidad servida | el proveedor |
| `HARDWARE_ATTESTED` | Un TEE verificó los pesos cargados | el fabricante del hardware |
| `CRYPTOGRAPHICALLY_BOUND` | Una prueba liga la inferencia a un commitment | la criptografía |
| `INDEPENDENTLY_IDENTIFIED` | El verificador comprueba que el commitment es el modelo nominal | nadie / registro público |

El último nivel es trivial para pesos abiertos y hoy inalcanzable para propietarios sin una autoridad externa.

### Qué implica para la firma del runner

La idea de correr la ronda en CI para que el runner firme **no mueve** "el modelo declarado fue realmente quien revisó" de declarado a verificado. Mueve una propiedad distinta, y conviene nombrarla como lo que es: **provenance de la invocación**, no identidad del modelo.

```
Antes:   DECLARED          el agente dice que un revisor de otra familia revisó.
Con CI:  RUNNER_ATTESTED   un runner firmado llamó al endpoint E pidiendo model_id=M,
                           con request_hash=P y response_hash=R.
Sigue:   PROVIDER_ASSERTED que E haya servido realmente M.
```

Es evidencia real y vale la pena, pero no es lo que parecía prometer.

**Por eso no debería ser el default.** Hoy el gate no necesita claves de API, no corre modelos y no manda código a ningún servicio: trabaja sobre evidencia ya versionada. Perder esa propiedad — que es justamente la que hace la herramienta adoptable en entornos restringidos, los mismos del perfil minimizado — a cambio de poder demostrar que se llamó a un endpoint pidiendo cierto modelo, es mal negocio. La forma correcta es **verificación offline de evidencia por default, ejecución atestiguada como perfil opcional** para organizaciones que quieran pagar ese costo.

La ventaja de modelar la escala desde ahora es que el modelo conceptual no tiene que cambiar cuando el campo avance. Si algún día los proveedores soportan proof-of-inference, el runner guarda `provider_response`, `model_commitment` e `inference_proof`, y disensor los valida. La misma propiedad avanza sin rediseñar el artefacto:

```
v0.5      DECLARED                  "reviewer = <familia>"
   ↓      RUNNER_ATTESTED           "una llamada firmada solicitó <proveedor>/<modelo>"
   ↓      CRYPTOGRAPHICALLY_BOUND   "esta inferencia corresponde al commitment abc123"
   ↓      INDEPENDENTLY_IDENTIFIED  "abc123 está públicamente registrado como <modelo>"
```

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

Y sale también la dirección de evolución, que no es la obvia. **La evolución natural de disensor no es hacer cada vez más obligatorio el JSON.** Es aumentar la parte del artefacto que puede verificarse independientemente y reducir la que necesita ser creída, moviendo propiedades nominales entre las clases de la frontera de assurance.

Trust Without Trusting marca el horizonte: *declarado → verificado externamente → recomputable de forma independiente*. Hoy el artefacto mezcla esas clases sin distinguirlas en su propia estructura, y hacer la distinción explícita en el esquema — registrar no sólo qué se afirma sino con qué raíz de confianza — sería el paso concreto más barato en esa dirección. No requiere criptografía nueva ni cambiar el flujo: requiere admitir en el esquema que no todas las afirmaciones del artefacto tienen el mismo estatus.

### La restricción de producto

De los assurance cases y del rationale sale la misma lección, y es una restricción dura: **no inventar una metodología que el desarrollador tenga que "hacer"**. Los obstáculos reportados no fueron conceptuales sino de tooling e integración. El residuo tiene que emitirse dentro del agente, git, el PR y CI, sin sistema paralelo, sin representación nueva que aprender, y sin que nadie interrumpa lo que estaba haciendo. Es exactamente lo que apuntan `disensor init`, la skill y `disensor guide`, y conviene tratar cualquier fricción agregada ahí como riesgo existencial y no como detalle de UX.

## Direcciones que abre

De contrastar el protocolo contra sus vecinos salen tres direcciones, y el orden de prioridad entre ellas cambió respecto del que traía este documento en su primera versión.

### P1: el assurance de las refutaciones

**Aquí se toma la decisión con consecuencias**: `refuted_verifiable` significa que este hallazgo no requiere modificar el código. Es el estado terminal donde una declaración falsa tiene más efecto y menos resistencia, y es más importante que la identidad del revisor — una identidad perfectamente atestiguada no arregla que un modelo criptográficamente identificado haya producido una refutación equivocada.

**Defecto verificado en la implementación de referencia.** El esquema exige `evidence` para `refuted_verifiable` (`$defs/finding/allOf[2]`), pero `$defs/evidence` no declara `minProperties`, `required` ni `anyOf`, y ninguna regla liga ese estado con `verification.against`. Reproducción, partiendo de `spec/examples/example_2_diff_gate.json` y mutando su hallazgo `h3`:

```json
"final_state": "refuted_verifiable",
"verification": { "against": "none" },
"evidence": {}
```

`disensor validate` responde `VALID`. La lectura literal es: *lo verifiqué contra nada, mi evidencia es nada, por lo tanto el hallazgo es un falso positivo verificable.* Las tres variantes (evidencia vacía sola, `against: none` sola, y ambas) pasan hoy.

Esa contradicción semántica se corrige barato y conviene hacerlo antes que cualquier arquitectura nueva. Son **dos invariantes independientes**, y conviene tratarlos como dos criterios de aceptación separados porque evitan clases distintas de declaración cosmética:

- **A, evidencia material**: `evidence` con al menos una de `text`, `link` o `hash`. Con `anyOf` sobre `required`, no con `minProperties: 1` — si el objeto gana metadata más adelante (`kind`, `source`), un `{"kind": "repository_fact"}` satisfaría la cardinalidad sin aportar evidencia.
- **B, blanco verificable**: `verification.against ∈ {repository, execution}`, excluyendo `none`.

No resuelve Goodhart. Evita que el artefacto se contradiga a sí mismo, que es distinto y es prerrequisito.

El endurecimiento va bajo residue/v0.3 y no retroactivamente sobre v0.2: un artefacto válido bajo un identificador de esquema no debería volverse inválido bajo ese mismo identificador. Para una herramienta construida sobre provenance y reproducibilidad, la disciplina se aplica primero a sí misma. Reproducción, alcance en los cuatro consumidores del contrato y criterios de aceptación en el [issue #5](https://github.com/NicolasRocchia/disensor/issues/5).

**El problema conceptual de fondo es más profundo, y Assurance 2.0 ya tiene la distinción para nombrarlo**: separar *lo medido* de *lo útil*. Que se haya observado algo y que de esa observación se siga la conclusión son dos pasos distintos.

```
MEDIDO:  corrimos el test de concurrencia 100 veces sobre el commit abc123 y pasó.
ÚTIL:    por lo tanto la race condition no existe.
```

Lo primero puede ser mecánicamente verificable hasta el último detalle: qué test, qué commit, qué iteraciones, qué exit code, qué hash del reporte. Lo segundo no se deduce de lo primero — un test que pasa es evidencia de una observación, no refutación de una afirmación universal.

De ahí que una escala unidimensional no alcance. Son **dos dimensiones independientes**:

| Provenance de la evidencia | Fuerza de la inferencia evidencia → refutación |
|---|---|
| `declared` | `interpretive` |
| `artifact_bound` | `empirical` |
| `runner_attested` | `deductive` |
| `recomputable` | `mechanically_checked` |
| `formally_verified` | |

No forman una escala total, y el ejemplo de la race condition es justamente el cruce incómodo: evidencia `runner_attested` con inferencia `empirical`. Alta provenance, inferencia débil.

Eso revela un problema de naming en el contrato actual: **`refuted_verifiable` fusiona dos afirmaciones distintas** — que la evidencia es verificable y que la refutación lo es. No cambiar el nombre hoy, pero sí redefinir formalmente qué significa, y considerar para residue/v1 descomponerlo en lugar de seguir metiendo semántica adentro del enum.

**Cómo avanzar sin romper la propiedad de no ejecutar nada.** disensor no debería empezar a correr tests declarados desde el JSON: dejar que un artefacto diga qué comando ejecutar abre una superficie de seguridad nueva. Pero puede **consumir attestations** producidas por el CI que ya corre. Existe el predicado [Test Result de in-toto](https://github.com/in-toto/attestation/tree/main/spec/predicates) ("a generic schema to express results of any type of tests"), el de Vulnerability, y el bundle de SLSA Source incluye code review para el commit revisado. El circuito sería:

```
evidencia de refutación → attestation de test result del CI
                        → subject SHA == reviewed_head
                        → disensor verifica que ese test pasó sobre ese commit, sin correrlo
```

Eso mueve *"el test pasó"* de declarado a atestiguado, y deja deliberadamente *"por lo tanto el hallazgo es falso"* en empírico o interpretativo. Es la separación honesta.

**Medir antes de vigilar.** El paso inmediato no es bloquear por nivel, sino registrar la clase: qué tipo de evidencia sostiene cada refutación (`repository_fact`, `test_result`, `static_analysis`, `formal_proof`, `external_contract`, `other`) y con qué assurance. Sin datos, cualquier umbral es arbitrario.

### P2: el lazo longitudinal que hoy no existe

Nidus no depende de que el arquitecto se dé cuenta: tiene un **decay detector**, un proceso de fondo que escanea su friction ledger buscando fallas recurrentes agrupadas por tipo de obligación; cuando el conteo supera un umbral configurable en una ventana móvil, genera una obligación candidata, la prueba contra el artefacto actual y la deja abierta para incorporarla. Más la cadena explícita falla → causa raíz → obligación en sus *lessons*.

disensor hoy tiene `desacuerdo → residuo → historia`, y nada más. Falta: *¿qué pasó después? ¿tenía razón? ¿qué aprende el protocolo?*

La respuesta no es copiar Nidus y convertir cada residuo en regla. Hay una versión propia, y la diferencia importa: el motor de Nidus es *falla → restricción*; el de disensor sería **historial de incertidumbre → resultado observado → calibración de qué evidencias merecían confianza → endurecimiento de la frontera**.

El artefacto histórico no se toca — eso rompería G8. Se emite otro, que lo referencia:

```
outcome
  event_ref:    <event_id>
  finding_ref:  h3
  outcome:      refutation_invalidated
  discovered_by: incident
  evidence:     ...
```

Con eso aparece una medición que hoy es imposible. No sólo "4 refutaciones verificables", sino cuántas de ellas se invalidaron después — y, mucho más interesante, **desagregado por clase de evidencia**: qué proporción de las refutaciones basadas en prosa del repositorio terminó invalidada, contra las basadas en un test atestiguado por CI. Ahí la escala de assurance deja de ser filosófica y se vuelve calibrable.

Cuidado con la interpretación, y es una asimetría real: *que no haya aparecido un bug nunca demuestra que la refutación fuera correcta* — sigue siendo mundo abierto. Pero `refutation_invalidated` sí es una observación positiva fuerte. La asimetría no invalida la medición; la limita a una dirección.

Dos cosas más que esto habilita:

- **El aprendizaje no debe forzarse a ser regla.** Un outcome puede producir una regla nueva, un requisito de evidencia más fuerte para cierta clase, un cambio de criticidad, una modificación del brief adversarial, una política organizacional — o simplemente una lección no mecanizable. Obligar a que todo aprendizaje se cristalice en regla es la misma trampa de Goodhart un nivel más arriba.
- **El residuo como índice de incidentes.** Cuando aparece un defecto en producción, se puede preguntar si hubo antes una objeción relacionada. Si la hubo, ese bug no era desconocido: hubo una señal adversarial previa que se descartó. Como dato de proceso es potente, y es un uso del artefacto que no estaba en su diseño original.

Y responde parcialmente a Goodhart, sin eliminarlo. Hoy el agente puede aprender que declarando `refuted_verifiable` con evidencia plausible cierra el hallazgo. Si los outcomes se miden longitudinalmente por modelo, clase de evidencia y clase de hallazgo, aparece una señal externa que el agente **no controla en el momento de producir la declaración**: el outcome futuro funciona como prueba diferida. Imperfecta, porque muchos errores nunca se descubren. Pero cuando uno se descubre, ya no desaparece en el historial.

### P3: identidad del modelo

Baja de prioridad. Sigue siendo interesante para provenance y la sección de arriba mantiene su análisis, pero resuelve una pregunta menos consecuente: saber con exactitud quién se equivocó vale menos que aumentar la fuerza con la que se justifica por qué se cerró un hallazgo.

## Referencias no confirmadas

Aparecieron en búsqueda pero **sin fuente primaria verificable**. No citar sin confirmación propia:

- **Garda** (governance para coding agents, con lifecycle, gates, revisión independiente y disposición explícita de findings). La única fuente encontrada es un posteo de LinkedIn. Sería, si existe como se describe, el proyecto contemporáneo funcionalmente más cercano; hay que encontrar el repositorio o la documentación.
- **Agent Audits** (acceptance criteria → evidence → review → check → report).
- El uso del término *residual risk* por **Critique** para separar lo que no se pudo verificar de los hallazgos concretos. Conceptualmente sano y muy cercano al vocabulario del artefacto, pero es output de revisión y no artefacto persistido; hace falta la fuente.

Pendientes de lectura completa, no sólo de existencia: Nidus, Trust Without Trusting, Refute-or-Promote y Structured Disagreement for Grounded Agentic Code Review. De los cuatro, **Nidus es el que más puede afectar el claim de novedad** y debería leerse entero antes de publicar.

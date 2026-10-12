# chatgpt, profundo, es, antes

```yaml
modelo: chatgpt
modelo_pedido: ChatGPT, modo de investigación con fuentes públicas (modelo no declarado)
cli: interfaz web, sin CLI
modo: profundo
idioma: es
estado: antes
documento: web
capturado_por: Nicolás, pegado en la sesión de Claude Code
fecha_captura: 2026-10-12, antes del merge del PR #118 (15:15Z); el informe dice haber tomado la versión publicada 0.12.1 y las incidencias públicas al 12/10
pregunta: distinta de la fija. La consigna fue revisar disensor usando solo fuentes públicas, sin conversaciones previas ni la máquina del autor.
nota: modo profundo, no superficial; está acá como el otro extremo del "antes", porque leyó las mismas fuentes que Google AI Mode y devolvió los seis estados, R0 a R13 y G1 a G9 correctos. Es un extracto: las secciones que describen qué hace y cómo es el artefacto (1, 3 y 4.1 del informe original); se omiten la evaluación, la adopción, los problemas y las prioridades. El texto es el de ChatGPT tal cual, con sus guiones largos.
```

## Respuesta

1. Qué hace concretamente

Disensor tiene cuatro partes que conviene entender por separado:

Parte | Función
Ejecución de la revisión | disensor round prepara el material, ejecuta un revisor registrado y captura su respuesta.
Declaración de la revisión | Un archivo JSON registra participantes, código revisado, hallazgos, decisiones, evidencias y residuo.
Validación y control del PR | validate comprueba el artefacto; gate lo contrasta con el cambio y la política del repositorio.
Lectura posterior | report produce un informe HTML para consultar decisiones, deuda y verificaciones pendientes.

La ejecución del revisor es opcional: también puede registrarse una revisión realizada por otro procedimiento. El gate no necesita ejecutar un modelo para evaluar una declaración existente. Eso permite separar el costo y la variabilidad de la revisión con IA del control mecánico que se aplica al registro.
El concepto central es la declaración de residuo. "Residuo" tiene un significado más amplio que "bugs pendientes": incluye objeciones escaladas, refutaciones del generador, comprobaciones que no pudieron ejecutarse y limitaciones del propio revisor. Una refutación respaldada por evidencia puede cerrar un hallazgo y permanecer en el residuo para que otra persona pueda examinarla.

3. Cómo funciona el proceso

El método propone separar generación, revisión adversarial, verificación de los hallazgos y decisión humana. La revisión puede aplicarse a un plan, un diff o una decisión de arquitectura.

Cada hallazgo debe terminar con una disposición explícita:

Estado | Significado
incorporated | Se incorporó una modificación a partir del hallazgo.
debt_recorded | Se reconoce el problema y se registra como deuda.
owner_decision | El responsable tomó una decisión o aceptó un riesgo.
refuted_verifiable | Se rechaza el hallazgo con evidencia verificable.
refuted_interpretive | Se rechaza por interpretación o juicio.
escalated_open | Se transfiere sin una decisión final.

En una revisión de diff, declarar un hallazgo como incorporado exige registrar la verificación de la corrección. Las refutaciones interpretativas requieren atención humana. Estas reglas organizan el cierre del evento, aunque algunos asuntos sigan pendientes.
El resultado favorable del gate significa que el registro cumple el contrato aplicado. Para interpretar correctamente ese resultado hay que mantener separadas la coherencia del registro y la calidad real de la revisión.

4.1. Distingue estructura, coherencia y correspondencia con Git

La documentación vigente distingue el esquema JSON, 14 reglas del artefacto —R0 a R13— y 9 controles del gate —G1 a G9—. Esa separación permite que un archivo tenga una estructura válida y aun así sea rechazado por contradicciones internas o por no corresponder al PR.
Es una buena separación de responsabilidades. Validar que existe una lista de hallazgos es un problema; comprobar que sus conteos y referencias coinciden es otro; determinar si justifican el cambio actual requiere además consultar Git.

4.6. Tiene dos implementaciones y una reproducción externa documentada

Hay un validador Python y un port TypeScript. El 31 de agosto, Kenne Ives informó públicamente que, desde un clon limpio de v0.9.4, verificó los archivos fijados por hash y obtuvo conformidad sobre 89 vectores y 28 casos de ordinalidad, sin divergencias entre veredictos y etiquetas de reglas.
Es una señal técnica relevante: alguien ajeno pudo repetir un resultado concreto.
El alcance es acotado. Las implementaciones y los casos procedían del proyecto; esto no prueba que el contrato cubra todos los errores posibles ni que la revisión con IA mejore el software. El mensaje está alojado en una lista pública de W3C y documenta esa reproducción, no una certificación institucional.

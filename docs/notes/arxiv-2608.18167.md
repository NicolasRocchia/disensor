# Nota de lectura: arXiv 2608.18167, Adversarial Review

Insumo para el segundo paper. Lo que va entre comillas es texto del paper,
leído del PDF de la versión v1 (16 de agosto de 2026); lo demás es lectura
propia, y cada tramo dice cuál de las dos cosas es. La nota no repite las
cifras del paper más allá de lo que hace falta para el contraste: para citar
un número hay que ir al paper.

## Ficha

- Título: *Adversarial Review: Structured Disagreement for Grounded Agentic Code Review*.
- Autores: Eric S. Qiu (Cornell University) y Joyce Gill (Stanford University), marcados como contribución equivalente.
- Identificador: arXiv:2608.18167v1 [cs.AI], 16 de agosto de 2026. <https://arxiv.org/abs/2608.18167>
- Estado de publicación: el PDF lleva el pie de la plantilla de ICML 2026 ("Proceedings of the 43rd International Conference on Machine Learning, Seoul, South Korea. PMLR 306, 2026"). No se verificó nada más allá de arXiv: ni la página de arXiv ni OpenReview eran accesibles desde el entorno en que se escribió esta nota, así que la ficha sale del PDF y no de los metadatos del índice. Antes de citarlo en el paper, confirmar venue y versión vigente.
- Relación con las dos entradas de OpenReview que figuran en [antecedentes.md](../antecedentes.md) (fOHvpLs6zp y h9UPyo3bbp): los títulos son casi idénticos y es probable que sean versiones del mismo trabajo, pero la correspondencia no se verificó.

## Abstract (verbatim)

> Early multi-agent LLM systems often used role-separated teams, yet scaling agent count yields diminishing returns on repository-level coding tasks. Recent alternatives treat agents as passive tools (subagents), yet this removes the benefits of agent interaction entirely. We study whether a subagent paradigm can support a middle ground: minimal agentic cooperation without the overhead of large multi-agent teams. We introduce Adversarial Review (AR), a minimal cooperative code-review protocol in which a main coding agent works with a reviewer and a critic agent. The reviewer evaluates code, while the critic audits the review through structured disagreement before the main agent edits. On LiveCodeBench, AR achieves the highest pass rate among tested methods, outperforming a five-agent baseline while using only three agents. On SWE-PRBench, naive AR exposes a false-consensus failure mode, where agents converge on agreement without sufficient evidence, but a single prompt iteration that adds disagreement explicitly achieves the highest F1 among tested methods. On SWE-bench Verified, AR also shows improvements over the baselines on repository-level coding tasks. Together, AR demonstrates that cooperative code review does not require many agents or complex communication structures: it requires that disagreement be minimal, structured, and evidence-grounded.

## Qué hace AR, según el texto

- **Tres roles, un modelo.** Un agente principal que edita, un revisor R y un crítico C. "The reviewer evaluates code, while the critic audits the review through structured disagreement before the main agent edits." En los experimentos los tres roles corren sobre el mismo modelo: "We use Claude Sonnet 4.5 Medium Reasoning for all subsequent agent and subagent calls for all benchmarks."
- **Dos lazos.** El artefacto queda congelado mientras R y C discuten; edita solo el agente principal, y después. De la figura 1: "the inner loop exchanges review text only, while artifact edits occur only in the outer loop."
- **Tres contribuciones declaradas.** Que un lazo revisor-crítico mínimo mejora la codificación agéntica dentro del paradigma de agente principal con subagentes; que "agents can optimize for agreement rather than correctness"; y que "structured disagreement can reliably fix false consensus".
- **Evaluación.** LiveCodeBench (pass rate; AR supera a una baseline de cinco agentes usando tres), SWE-PRBench (F1 contra los comentarios humanos de 100 PR reales, con un juez LLM) y SWE-bench Verified (pass@1, con el protocolo expresado como un SKILL.md que sigue Claude Code).
- **Falso consenso.** En SWE-PRBench el AR ingenuo queda último entre los métodos comparados. Dos casos de estudio: R propone hallazgos flojos y C los confirma; C levanta una objeción real y cede ante una réplica segura de R que no cita código. "Both failures have the same structure: the agents reach agreement, but the agreement is not supported by enough evidence. We call this failure mode false consensus." Y: "False consensus is especially concerning because it can look like independent validation: two agents appear to agree, but the agreement may only reflect conversational pressure to converge." El paper lo califica de estructural: nace de cómo interactúan los agentes, no de la calidad individual de cada uno.
- **La corrección.** Una sola iteración de prompt, "AR with text constraint": C ya no elige entre AGREE y DISAGREE sino entre AGREE, DISAGREE EVIDENCE con cita de código, y DISAGREE CONCERN con una objeción epistémica que no puede señalar código; R tiene que responder con código del diff, para confirmar o para descartar. Con eso AR pasa de último a primero en el subconjunto comparado. "So the protocol must include explicit pushback. Without pushback, what looks like “structured disagreement” becomes false agreement."
- **Límites que declaran.** "Our claims about agent cooperation are empirical, not formal." Y que la evaluación depende de los benchmarks y del diseño del juez.

## Puntos de contraste con disensor

Lectura propia, salvo donde se cita.

1. **Orquestación contra artefacto.** AR dice quién habla con quién y cuándo, y se mide por pass rate y F1. disensor no orquesta ni corre modelos: define y valida el artefacto con el que termina cualquier ciclo, y lo aplica como gate en CI. No compiten por el mismo lugar del flujo.
2. **Falso consenso: dos palancas distintas.** AR lo ataca dentro del protocolo, con la forma de la respuesta del crítico. disensor lo ataca desde afuera: la declaración lista residuo y no cobertura, el árbitro humano es obligatorio (R0) y generador y revisor tienen que ser de familias distintas (R4). Cuidado con una tentación: el paper **no** dice nada sobre familias de modelo (todo corre sobre un modelo), así que no sirve como sustento empírico de R4. Lo que sí aporta es una observación verificada de que dos agentes que deben acordar tienden a acordar, que es el problema que R4 intenta acotar por otra vía. [antecedentes.md](../antecedentes.md) ya lo dice en "Sobre el sustento empírico de R4", y esta lectura lo confirma.
3. **Dónde queda el desacuerdo.** En AR el desacuerdo es un paso del protocolo y termina cuando la revisión converge; el paper dice que la restricción textual "turns disagreement into an auditable object", auditable dentro de la conversación. En disensor el desacuerdo no es un paso: es lo que queda registrado, versionado con el commit, cuando el ciclo no cierra solo.
4. **Complementarios, y en qué punto exacto.** Un ciclo AR puede terminar en una declaración de residuo. La bisagra es DISAGREE CONCERN: una objeción que no puede señalar código que la contradiga es, en el vocabulario de disensor, lo que termina en `refuted_interpretive` o en `escalated_open`, es decir, en residuo que exige atención humana. Esto es lectura propia; el paper no propone ningún artefacto persistido ni habla de CI.
5. **Una frase del paper que le sirve al segundo paper.** "multi-agent oversight should not be judged only by whether agents converge. It should be judged by whether the path to convergence preserves dissent, evidence, and accountability." La declaración de residuo es, precisamente, el registro de ese camino.
6. **Vocabulario.** AR ocupa "adversarial review" y "structured disagreement". "Residue declaration", "declaración de residuo" y "desacuerdo controlado" siguen libres, y nadie los busca todavía: el README y el sitio los rodean con el vocabulario de búsqueda sin reemplazarlos.

## Dónde se cita hoy

- `README.md`, sección "How this relates to other approaches", subsección "Relation to Adversarial Review (arXiv 2608.18167)".
- `README.es.md`, sección "Cómo se relaciona con otros enfoques", subsección "Relación con Adversarial Review (arXiv 2608.18167)".
- El sitio, en `/method/` y `/es/method/`, con el mismo texto.

## BibTeX

```bibtex
@misc{qiu2026adversarialreview,
  title         = {Adversarial Review: Structured Disagreement for Grounded Agentic Code Review},
  author        = {Qiu, Eric S. and Gill, Joyce},
  year          = {2026},
  month         = aug,
  eprint        = {2608.18167},
  archivePrefix = {arXiv},
  primaryClass  = {cs.AI},
  url           = {https://arxiv.org/abs/2608.18167},
  note          = {Version 1, 16 August 2026}
}
```

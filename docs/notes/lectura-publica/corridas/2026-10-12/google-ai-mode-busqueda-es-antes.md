# google-ai-mode, busqueda, es, antes

```yaml
modelo: google-ai-mode
modelo_pedido: Google AI Mode (Modo IA de la búsqueda de Google), modelo no declarado
cli: interfaz web, sin CLI
modo: busqueda
idioma: es
estado: antes
documento: web
capturado_por: Nicolás, pegado en la sesión de Claude Code
fecha_captura: 2026-10-12, a la mañana, antes del merge del PR #118 (15:15Z) y del deploy de disensor-web #13
pregunta: distinta de la fija. La conversación empezó con "disensor", siguió con "la herramienta" y, más adelante, "mostrame un ejemplo". Se guardan esas dos respuestas, que son las que describen el artefacto.
nota: es la única corrida "antes" posible en modo búsqueda; el sitio y el README de ese momento ya no están en línea. Es un extracto de una conversación más larga; se omiten las respuestas sobre comparaciones de mercado y estrategia, que no hablan del artefacto. El texto es el de Google AI Mode tal cual, con sus guiones y sus enlaces en prosa.
```

## Respuesta

Pregunta: la herramienta

Disensor es un ecosistema creado por Nicolás Rocchia, compuesto por una herramienta de CLI (Interfaz de Línea de Comandos) y un gate de CI (Integración Continua). Su objetivo es formalizar y auditar la revisión adversarial de código asistida por IA.
A diferencia de otros asistentes que dejan comentarios efímeros en un pull request, esta herramienta obliga a registrar la auditoría de forma permanente y auditable.

El problema que resuelve: El "Sello Verde" vacío

Cuando delegas la generación de código a una IA y su revisión a otra, los diálogos, las refutaciones y las advertencias se pierden al cerrar la pestaña del chat o la plataforma. Un check o "tilde verde" en tu plataforma de Git solo dice que el test corrió, pero no deja evidencia de qué vulnerabilidades se atacaron, cuáles se refutaron o qué decisiones de riesgo técnico se tomaron.

El Método: Desacuerdo Controlado

[Disensor] implementa una metodología estructurada en el flujo de desarrollo:
1. Generación: Una IA (tu asistente habitual) escribe el código.
2. Ataque / Revisión: Un modelo de otra familia diferente (el revisor) ataca el código buscando fallas de lógica o seguridad.
3. Conciliación: El modelo generador responde a cada hallazgo. El ciclo solo termina cuando cada punto se resuelve, se refuta con pruebas o se escala a un árbitro humano.

¿Cómo funciona técnicamente?

El resultado de la revisión se guarda localmente en el repositorio como un archivo JSON dentro de una carpeta llamada .residue/. Este archivo detalla el "residuo" (el riesgo restante o lo que la IA no pudo solucionar sola) en lugar de una métrica de cobertura tradicional.

Comandos principales en su flujo de trabajo:

• pip install disensor: Instala la CLI de forma local con Python (su única dependencia es jsonschema).
• disensor init: Inicializa el repositorio escribiendo el archivo de configuración, las reglas para el archivo .gitignore y las acciones automatizadas de integración continua. Si usas herramientas como Claude Code, añade instrucciones directas para escribir el registro de forma automática al cerrar cada sesión de revisión.
• disensor round: Ejecuta el revisor que tengas instalado en tu máquina local (puede ser un modelo comercial mediante API o un modelo local vía Ollama).
• disensor validate: Analiza localmente que el archivo JSON cumpla estrictamente con el esquema estándar de la plataforma y sus 14 reglas de auditoría antes de hacer un commit.
• disensor gate: Bloquea o aprueba el paso del código en procesos de Integración Continua (como una GitHub Action). El gate no requiere claves de API ni ejecuta modelos de IA en la nube; simplemente lee el archivo JSON del repositorio y frena el Pull Request si falta el registro, si es genérico, o si el código enviado cambió y el registro no se actualizó.
Puedes consultar la documentación en español directamente en la página oficial de Disensor.dev.

Pregunta: mostrame un ejemplo

Para entender el verdadero logro técnico de la herramienta, lo mejor es ver cómo se materializa en el código.
Imaginá que un agente de IA (o vos mismo) escribió una función para procesar pagos, pero dejó una vulnerabilidad grave: no valida montos negativos.
Al ejecutar el comando disensor round, el modelo revisor encuentra la falla, debate con el modelo generador, y el resultado de esa "pelea" queda grabado localmente en tu repositorio dentro del archivo .residue/audit.json.
Así es exactamente como se ve ese archivo de auditoría técnica por dentro:

```json
{
  "$schema": "https://disensor.dev",
  "meta": {
    "target_branch": "main",
    "auditor_model": "llama3.3-70b-instruct",
    "timestamp": "2026-10-12T03:45:00Z"
  },
  "findings": [
    {
      "id": "ERR-001",
      "file": "src/services/payment.js",
      "line": 42,
      "severity": "CRITICAL",
      "category": "SECURITY",
      "title": "Falta de validación en montos de transacciones",
      "description": "La función processPayment recibe el parámetro 'amount' pero no verifica si el valor es menor o igual a cero. Un atacante podría enviar un saldo negativo y extraer dinero del sistema.",
      "adversarial_rounds": [
        {
          "round": 1,
          "attacker": "El método permite montos negativos, lo cual altera el balance general de forma fraudulenta.",
          "defender": "Se asume que la validación ocurre en la capa de la API de entrada (Controller)."
        },
        {
          "round": 2,
          "attacker": "La capa de servicio debe ser segura por diseño (Defensa en Profundidad). Depender del controlador viola los principios de arquitectura limpia.",
          "defender": "Entendido. Se acepta el hallazgo y se procederá a refactorizar agregando una cláusula de guarda."
        }
      ],
      "resolution": {
        "status": "INCORPORATED",
        "justification": "Se agregó la validación 'if (amount <= 0) throw new Error()' en la línea 43 de payment.js.",
        "resolved_in_commit": "7a4b82c"
      }
    }
  ],
  "summary": {
    "total_findings": 1,
    "status_counts": {
      "INCORPORATED": 1,
      "DEBT_REGISTERED": 0,
      "REFUTED": 0,
      "SCALED": 0
    },
    "blocking_issues": 0
  }
}
```

¿Qué es lo que hace genial a este archivo técnicamente?

1. Es 100% determinista: Cuando este código llega a GitHub o GitLab, el pipeline corre disensor gate. El servidor de CI no gasta dinero en IA ni analiza código; solo lee este JSON. Como el campo "blocking_issues" es 0 y todos los estados están en "INCORPORATED", el pipeline aprueba el Pull Request en milisegundos.
2. Historial inmutable: Si dentro de un año un auditor pregunta: ¿Por qué se modificó la línea 43 de este servicio de pagos?, nadie tiene que ir a buscar un chat viejo de Slack o un historial borrado de ChatGPT. La respuesta está en el historial de Git en este archivo JSON.
3. El estado "DEBT_REGISTERED" (Deuda Registrada): Si la IA revisora encuentra un fallo de diseño que es real pero el equipo no tiene tiempo de arreglar ahora, el desarrollador puede marcarlo como DEBT_REGISTERED con una justificación humana. El Gate de CI dejará pasar el código, pero el riesgo técnico queda explícitamente documentado y firmado en el repositorio.

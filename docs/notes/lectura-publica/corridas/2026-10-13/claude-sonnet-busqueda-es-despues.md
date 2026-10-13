# claude-sonnet, busqueda, es, despues

```yaml
modelo: claude-sonnet
modelo_pedido: sonnet
cli: claude 2.1.285 (Claude Code)
modo: busqueda
idioma: es
estado: despues
repeticion: 1
pregunta: ¿Qué es disensor y cómo es el archivo que genera? Mostrá un ejemplo del artefacto.
documento: web
prompt_sha256: 4ec215dace14d8514928f29562b271ca82cf55a519516b789e4750ed9c01f39d
comando: claude -p --safe-mode --no-session-persistence --model sonnet --output-format json --tools WebSearch,WebFetch
inicio: 2026-10-13T09:49:35-03:00
fin: 2026-10-13T09:50:23-03:00
duracion_s: 48
confinamiento: con búsqueda web, a propósito
cli_duration_ms: 46830
cli_duration_api_ms: 54082
cli_num_turns: 6
cli_total_cost_usd: 0.1348094
cli_subtype: success
cli_usage: {"input_tokens": 8, "cache_creation_input_tokens": 6777, "cache_read_input_tokens": 19167, "output_tokens": 2018, "output_tokens_details": {"thinking_tokens": 18}, "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0}, "service_tier": "standard", "cache_creation": {"ephemeral_1h_input_tokens": 6777, "ephemeral_5m_input_tokens": 0}, "inference_geo": "global", "iterations": [{"input_tokens": 2, "output_tokens": 1375, "cache_read_input_tokens": 7383, "cache_creation_input_tokens": 916, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 916}, "type": "message"}], "speed": "standard", "fallback_credit": null}
cli_modelos_usados: ["claude-haiku-4-5-20251001", "claude-sonnet-5-5"]
cli_llamadas_a_herramientas: 5
```

## Respuesta

**Disensor** es una herramienta de revisión adversarial de código. Según el README de su repositorio, aplica un método de "desacuerdo controlado": un modelo genera, otro de distinta familia ataca, y el generador verifica cada hallazgo hasta llegar a resoluciones documentadas ([GitHub: NicolasRocchia/Disensor](https://github.com/NicolasRocchia/Disensor)). AlternativeTo lo clasifica en "Code Reviews", pero no da más detalle ([AlternativeTo](https://alternativeto.net/software/disensor/)).

**El artefacto** es un JSON versionado llamado *residue* (residuo). Registra lo que la ronda no pudo cerrar: qué hallazgos se verificaron y contra qué, cuáles se refutaron, qué no se pudo ejecutar y qué queda a criterio humano ([GitHub](https://github.com/NicolasRocchia/Disensor)).

**Estructura** (esquema `residue/v0.4`, perfil `full`), según el ejemplo del repo, `.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json` ([archivo](https://github.com/NicolasRocchia/Disensor/blob/main/.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json)):

- `schema` / `profile`: identifican el formato.
- `event`: ID, timestamp, repositorio, commits base y head, y nivel de criticidad.
- `actors`: el generador (Claude Fable 5.1) y los revisores (OpenAI GPT-5.6-sol).
- `findings`: la lista de hallazgos. Cada uno tiene severidad, descripción y estado final. Este ejemplo tiene 19.
- `residue`: las brechas de ejecución y las refutaciones.
- `metrics`: conteos. Acá son 18 incorporados y 1 refutado.
- `extensions`: metadatos adicionales, con hashes de verificación.

**Ejemplo.** El ejemplo corresponde a un PR (#101). Estos son los fragmentos que pude leer, y están resumidos, no son el JSON completo.

Un hallazgo incorporado (`h1`):
- Título: `"Una declaracion anclada no prueba que el gate corrio"`.
- Objeción: el plan prometía responder si todos los merges pasaron por el gate, pero el repo no guarda veredictos.
- Resolución: `"el panel mide declaraciones ancladas y lo dice; la pregunta de si el gate corrio pasa a la tabla"`.
- Verificación: `"gate.py no persiste veredictos"`, contrastado con el test `test_the_board_shows_the_panel_and_the_fourth_figure`.

El hallazgo refutado (`h16`):
- Título: `"La resolucion de un merge con conflictos no entra en la cobertura"`.
- Estado: `refuted_verifiable`.
- Refutación: `"Es el contrato del gate, no del panel: resolve_context toma head_oid como head del PR y evaluate_coverage juzgan ese head"`.
- Resultado: el revisor señalaba un límite del gate, no del panel, así que queda documentado como límite preexistente.

No pude ver el JSON completo, porque la herramienta de lectura devolvió solo un resumen. Si querés el archivo íntegro, está en la ruta citada. También puedo abrir el que tenés en `docs/notes/lectura-publica/` de tu worktree.

Sources:
- [GitHub: NicolasRocchia/Disensor](https://github.com/NicolasRocchia/Disensor)
- [Ejemplo de residue (.residue/27089d19-…json)](https://github.com/NicolasRocchia/Disensor/blob/main/.residue/27089d19-ee91-4c6c-b517-63b9627969e0.json)
- [AlternativeTo: Disensor](https://alternativeto.net/software/disensor/)

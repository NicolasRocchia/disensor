"""Render de la declaracion de residuo como comentario de PR (Markdown).

Principio de la seccion 9 del protocolo: la declaracion lista residuo, no
cobertura. El comentario dirige el escrutinio del revisor humano hacia lo que
el ciclo no pudo cerrar, en lugar de leerse como sello de calidad.
"""
from __future__ import annotations

MARCADOR = "<!-- residuo-gate -->"

NOMBRE_CLASE = {
    "escalado_sin_decision": "Escalado sin decision",
    "refutacion_del_principal": "Refutacion del modelo principal",
    "gap_de_ejecucion": "Gap de ejecucion",
}

NOMBRE_ESTADO = {
    "incorporado": "incorporados",
    "deuda_registrada": "deuda registrada",
    "decision_del_dueno": "decision del dueno",
    "refutado_verificable": "refutados con evidencia",
    "refutado_interpretativo": "refutados por criterio",
    "escalado_abierto": "escalados abiertos",
}


def _linea_item(item: dict, perfil: str) -> str:
    clase = NOMBRE_CLASE[item["clase"]]
    atencion = " **(requiere atencion humana)**" if item.get("requiere_atencion_humana") else ""
    ref = f" (hallazgo {item['ref_hallazgo']})" if item.get("ref_hallazgo") else ""
    detalle = ""
    if perfil == "completo" and item.get("descripcion"):
        detalle = f": {item['descripcion']}"
    elif item["clase"] == "refutacion_del_principal" and item.get("tipo_refutacion"):
        detalle = f" ({item['tipo_refutacion']})"
    elif item["clase"] == "gap_de_ejecucion" and item.get("motivo_gap"):
        detalle = f" ({item['motivo_gap'].replace('_', ' ')})"
    evidencia = item.get("evidencia", {})
    enlace = f" [evidencia]({evidencia['enlace']})" if evidencia.get("enlace") else ""
    aceptacion = ""
    if item.get("aceptacion_referente"):
        ar = item["aceptacion_referente"]
        aceptacion = f" Aceptado por escrito por {ar['referente']} ({ar['registro']})."
    return f"- **{clase}**{ref}{detalle}{atencion}{enlace}{aceptacion}"


def _resumen_conteos(a: dict) -> str:
    c = a["metricas"]["conteos"]
    v = c["validos"]
    fp = c["falsos_positivos"]
    partes = []
    if v["incorporado"]:
        partes.append(f"{v['incorporado']} incorporados")
    if v["deuda_registrada"]:
        partes.append(f"{v['deuda_registrada']} a deuda registrada")
    if v["decision_del_dueno"]:
        partes.append(f"{v['decision_del_dueno']} con decision del dueno")
    if fp["refutado_verificable"]:
        partes.append(f"{fp['refutado_verificable']} refutados con evidencia")
    if fp["refutado_interpretativo"]:
        partes.append(f"{fp['refutado_interpretativo']} refutados por criterio")
    if c["escalados_abiertos"]:
        partes.append(f"{c['escalados_abiertos']} escalados abiertos")
    detalle = ", ".join(partes) if partes else "sin hallazgos"
    return f"{c['total_hallazgos']} hallazgos: {detalle}."


def render_artefacto(a: dict) -> str:
    ev = a["evento"]
    ac = a["actores"]
    lineas = []
    revisores = ", ".join(f"{r['modelo']} ({r['familia']})" for r in ac["revisores"])
    confinamientos = ", ".join(
        f"{r['confinamiento']['modo'].replace('_', ' ')}"
        + (" verificado" if r["confinamiento"]["verificado"] else " SIN VERIFICAR")
        for r in ac["revisores"]
    )
    lineas.append(
        f"### Evento `{a['evento']['id_evento'][:8]}` "
        f"(compuerta {ev['compuerta']}, Nivel {ev['nivel_criticidad']}, commit `{ev['commit_cabeza'][:7]}`)"
    )
    lineas.append("")
    lineas.append(
        f"Generador {ac['generador']['modelo']} ({ac['generador']['familia']}); "
        f"revisor {revisores}; confinamiento: {confinamientos}. "
        f"{_resumen_conteos(a)}"
    )
    if ev["ruta_abreviada"].get("usada"):
        lineas.append(f"Ruta abreviada usada. Justificacion: {ev['ruta_abreviada'].get('justificacion', '')}")
    lineas.append("")
    residuo = a["residuo"]
    if residuo.get("ausencia_declarada"):
        lineas.append(f"**Sin residuo.** Declaracion expresa: {residuo['declaracion']}")
    else:
        lineas.append("**Residuo declarado** (lo que el ciclo no pudo cerrar por si mismo):")
        for item in residuo["items"]:
            lineas.append(_linea_item(item, a["perfil"]))
    return "\n".join(lineas)


def render_comentario(validos: list[dict], errores_por_archivo: dict[str, list[str]],
                      errores_gate: list[str]) -> str:
    """Comentario completo del PR, con marcador para actualizarlo en el lugar."""
    lineas = [MARCADOR, "## Declaracion de residuo", ""]
    if errores_gate or errores_por_archivo:
        lineas.append("**El gate fallo.** El PR no declara residuo en forma valida:")
        for msg in errores_gate:
            lineas.append(f"- {msg}")
        for archivo, errs in errores_por_archivo.items():
            for msg in errs:
                lineas.append(f"- `{archivo}`: {msg}")
        lineas.append("")
    for a in validos:
        lineas.append(render_artefacto(a))
        lineas.append("")
    lineas.append("---")
    lineas.append(
        "Esta declaracion lista residuo, no cobertura: dirige el escrutinio del revisor humano "
        "hacia lo que quedo abierto en lugar de leerse como sello de calidad. "
        "La maquina valida forma y coherencia; que el residuo declarado sea el residuo real "
        "se controla por muestreo humano, no por este gate."
    )
    return "\n".join(lineas)

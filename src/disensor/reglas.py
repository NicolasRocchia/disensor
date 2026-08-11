"""Reglas de validacion del artefacto de residuo (esquema v0.1).

Dos capas, en el espiritu de la seccion 12.2 del protocolo:
  1. JSON Schema: forma y campos condicionales.
  2. Reglas estructurales R0 a R10: coherencia que un schema no expresa.

Limite honesto, declarado en el protocolo: la maquina detecta el campo vacio
y el marcador generico, no la declaracion falsa. El muestreo humano sigue
siendo la unica defensa real contra el cumplimiento cosmetico.
"""
from __future__ import annotations

import json
from importlib import resources

from jsonschema import Draft202012Validator

MARCADORES_GENERICOS = {
    "n/a", "na", "ninguno", "ninguna", "todo resuelto", "aplicado",
    "ok", "sin residuo", "-", "no aplica",
}

ESTADOS_A_RESIDUO = {"escalado_abierto", "refutado_verificable", "refutado_interpretativo"}

CLASE_ESPERADA = {
    "escalado_abierto": "escalado_sin_decision",
    "refutado_verificable": "refutacion_del_principal",
    "refutado_interpretativo": "refutacion_del_principal",
}

CAMPOS_TEXTO_PROHIBIDOS_MINIMIZADO = {"titulo", "descripcion", "ubicacion"}


def cargar_schema() -> dict:
    """Carga el schema empaquetado con la distribucion."""
    with resources.files("disensor").joinpath("residuo.schema.json").open(encoding="utf-8") as f:
        return json.load(f)


def errores_schema(artefacto: dict, schema: dict) -> list[str]:
    validador = Draft202012Validator(schema)
    return [
        f"[schema] {'/'.join(str(p) for p in err.path) or '(raiz)'}: {err.message}"
        for err in sorted(validador.iter_errors(artefacto), key=lambda x: list(x.path))
    ]


def errores_reglas(a: dict) -> list[str]:
    """Reglas estructurales sobre un artefacto ya valido contra el schema."""
    e: list[str] = []

    def error(regla: str, msg: str) -> None:
        e.append(f"[{regla}] {msg}")

    perfil = a["perfil"]
    hallazgos = a.get("hallazgos", [])
    residuo = a["residuo"]
    items = residuo.get("items", [])
    por_id = {h["id"]: h for h in hallazgos}
    compuerta = a["evento"]["compuerta"]
    nivel = a["evento"]["nivel_criticidad"]

    # R0: sin arbitro humano el evento no cumple el protocolo (seccion 6).
    if not a["actores"]["arbitro_humano"]["presente"]:
        error("R0", "evento sin arbitro humano presente")

    # R10: en perfil completo, la lista de hallazgos es obligatoria.
    if perfil == "completo" and not hallazgos:
        error("R10", "perfil completo sin lista de hallazgos")

    # R1: todo hallazgo cuyo estado integra el residuo tiene su item, y todo
    # item con referencia apunta a un hallazgo existente del estado correcto.
    if hallazgos:
        refs = {i.get("ref_hallazgo") for i in items if i.get("ref_hallazgo")}
        for h in hallazgos:
            if h["estado_final"] in ESTADOS_A_RESIDUO and h["id"] not in refs:
                error("R1", f"hallazgo {h['id']} ({h['estado_final']}) sin item de residuo")
        for i in items:
            ref = i.get("ref_hallazgo")
            if ref:
                if ref not in por_id:
                    error("R1", f"item {i['id']} referencia hallazgo inexistente {ref}")
                else:
                    est = por_id[ref]["estado_final"]
                    if est in CLASE_ESPERADA and i["clase"] != CLASE_ESPERADA[est]:
                        error("R1", f"item {i['id']} clase {i['clase']} no corresponde al estado {est} de {ref}")

    # R2: sin marcadores genericos en las declaraciones de texto.
    textos = []
    if residuo.get("ausencia_declarada"):
        textos.append(("residuo.declaracion", residuo.get("declaracion", "")))
    for i in items:
        if "descripcion" in i:
            textos.append((f"residuo.items[{i['id']}].descripcion", i["descripcion"]))
    for donde, t in textos:
        if t.strip().lower() in MARCADORES_GENERICOS:
            error("R2", f"marcador generico en {donde}: '{t}'")

    # R2 bis: marcadores de plantilla sin completar, en cualquier campo.
    # Sin esto, una plantilla de perfil minimizado validaria de fabrica.
    def buscar_plantilla(valor, ruta: str) -> None:
        if isinstance(valor, str) and valor.startswith("COMPLETAR"):
            error("R2", f"marcador de plantilla sin completar en {ruta}")
        elif isinstance(valor, dict):
            for k, v in valor.items():
                buscar_plantilla(v, f"{ruta}.{k}")
        elif isinstance(valor, list):
            for n, v in enumerate(valor):
                buscar_plantilla(v, f"{ruta}[{n}]")

    buscar_plantilla(a, "artefacto")

    # R3: ruta abreviada incompatible con los cinco casos protegidos (3.2).
    ra = a["evento"]["ruta_abreviada"]
    if ra.get("usada") and ra.get("casos_protegidos_tocados"):
        error("R3", "ruta abreviada usada sobre un cambio que toca casos protegidos de 3.2")

    # R4: decorrelacion: ningun revisor modelo comparte familia con el generador.
    fam_gen = a["actores"]["generador"]["familia"]
    for r in a["actores"]["revisores"]:
        if r["familia"] == fam_gen:
            error("R4", f"revisor {r['id_revisor']} comparte familia ({fam_gen}) con el generador: sin decorrelacion")

    # R5: Nivel A + gap de ejecucion exige aceptacion escrita de un referente (seccion 7).
    if nivel == "A":
        for i in items:
            if i["clase"] == "gap_de_ejecucion" and "aceptacion_referente" not in i:
                error("R5", f"item {i['id']}: gap de ejecucion en Nivel A sin aceptacion de referente (bloquea el merge)")

    # R6: conteos coherentes con la lista de hallazgos (si esta presente).
    if hallazgos:
        c = a["metricas"]["conteos"]

        def conteo(est: str) -> int:
            return sum(1 for h in hallazgos if h["estado_final"] == est)

        esperado = {
            ("validos", "incorporado"): conteo("incorporado"),
            ("validos", "deuda_registrada"): conteo("deuda_registrada"),
            ("validos", "decision_del_dueno"): conteo("decision_del_dueno"),
            ("falsos_positivos", "refutado_verificable"): conteo("refutado_verificable"),
            ("falsos_positivos", "refutado_interpretativo"): conteo("refutado_interpretativo"),
        }
        for (grupo, campo), v in esperado.items():
            if c[grupo][campo] != v:
                error("R6", f"conteo {grupo}.{campo}={c[grupo][campo]} pero la lista tiene {v}")
        if c["escalados_abiertos"] != conteo("escalado_abierto"):
            error("R6", f"escalados_abiertos={c['escalados_abiertos']} pero la lista tiene {conteo('escalado_abierto')}")
        if c["total_hallazgos"] != len(hallazgos):
            error("R6", f"total_hallazgos={c['total_hallazgos']} pero la lista tiene {len(hallazgos)}")

    # R7: en compuerta diff, todo incorporado cierra con la correccion verificada.
    if compuerta == "diff":
        for h in hallazgos:
            if h["estado_final"] == "incorporado":
                v = h.get("verificacion_de_la_correccion")
                if not v:
                    error("R7", f"hallazgo {h['id']} incorporado en compuerta diff sin verificacion de la correccion")
                elif v["tipo"] == "pendiente_en_compuerta_diff":
                    error("R7", f"hallazgo {h['id']}: la verificacion de la correccion no puede quedar pendiente en la propia compuerta diff")

    # R8: refutacion interpretativa siempre pide atencion humana (seccion 6).
    for i in items:
        if i.get("tipo_refutacion") == "interpretativa" and not i.get("requiere_atencion_humana"):
            error("R8", f"item {i['id']}: refutacion interpretativa con requiere_atencion_humana=false")

    # R9: perfil minimizado no admite texto libre.
    if perfil == "minimizado":
        for h in hallazgos:
            for campo in CAMPOS_TEXTO_PROHIBIDOS_MINIMIZADO & h.keys():
                error("R9", f"hallazgo {h['id']}: campo '{campo}' prohibido en perfil minimizado")
            ev = h.get("evidencia", {})
            if "texto" in ev or "enlace" in ev:
                error("R9", f"hallazgo {h['id']}: evidencia con texto o enlace en perfil minimizado (solo hash)")
        for i in items:
            if "descripcion" in i:
                error("R9", f"item {i['id']}: descripcion prohibida en perfil minimizado")
            ev = i.get("evidencia", {})
            if "texto" in ev or "enlace" in ev:
                error("R9", f"item {i['id']}: evidencia con texto o enlace en perfil minimizado (solo hash)")
        if a["evento"]["repositorio"].startswith("http"):
            error("R9", "perfil minimizado con URL de repositorio en claro (usar hash o identificador opaco)")

    return e


def validar_artefacto(artefacto: dict, schema: dict | None = None) -> list[str]:
    """Valida un artefacto completo. Devuelve la lista de errores (vacia si es valido).

    Si el schema falla, las reglas estructurales no se evaluan: operarian
    sobre una forma que no esta garantizada.
    """
    schema = schema or cargar_schema()
    errores = errores_schema(artefacto, schema)
    if errores:
        return errores
    return errores_reglas(artefacto)

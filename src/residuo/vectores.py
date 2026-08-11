"""Vectores de conformidad del esquema v0.1.

Los vectores son la fuente de verdad compartida entre implementaciones del
validador (Python de referencia, TypeScript del plano de evidencia, y las que
vengan). Cada vector es un artefacto mas el veredicto esperado: valido o no,
y el conjunto de etiquetas de regla que deben dispararse ("schema" para
errores de forma, "R0" a "R10" para reglas estructurales).

Se comparan etiquetas, no mensajes: los mensajes son libres por
implementacion; las etiquetas no pueden divergir.

Uso: python -m residuo.vectores <directorio_destino>
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from .reglas import validar_artefacto

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLOS = RAIZ / "spec" / "ejemplos"


def _cargar(nombre: str) -> dict:
    with open(EJEMPLOS / nombre, encoding="utf-8") as f:
        return json.load(f)


def _etiquetas(errores: list[str]) -> list[str]:
    tags = set()
    for e in errores:
        if e.startswith("[") and "]" in e:
            tags.add(e[1:e.index("]")])
    return sorted(tags)


def casos() -> list[tuple[str, dict, bool, set[str]]]:
    """(nombre, artefacto, valido_esperado, reglas_que_deben_aparecer)."""
    plan = _cargar("ejemplo_1_compuerta_plan.json")
    diff = _cargar("ejemplo_2_compuerta_diff.json")
    mini = _cargar("ejemplo_3_perfil_minimizado.json")
    lista: list[tuple[str, dict, bool, set[str]]] = []

    # Validos
    lista.append(("valido_compuerta_plan", copy.deepcopy(plan), True, set()))
    lista.append(("valido_compuerta_diff", copy.deepcopy(diff), True, set()))
    lista.append(("valido_perfil_minimizado", copy.deepcopy(mini), True, set()))

    m = copy.deepcopy(diff)
    m["evento"]["nivel_criticidad"] = "A"
    for i in m["residuo"]["items"]:
        if i["clase"] == "gap_de_ejecucion":
            i["aceptacion_referente"] = {
                "referente": "referente-tecnico-01",
                "fecha": "2026-07-15T19:00:00-03:00",
                "registro": "actas/2026-07-15-aceptacion-gap.md",
            }
    lista.append(("valido_nivel_a_gap_con_referente", m, True, set()))

    m = copy.deepcopy(mini)
    m["hallazgos"] = []
    m["residuo"] = {
        "ausencia_declarada": True,
        "declaracion": "El ciclo corrio completo sobre el diff y no quedo nada sin resolver: "
                       "todo hallazgo se incorporo y sus correcciones pasaron pruebas especificas.",
    }
    m["metricas"]["conteos"] = {
        "total_hallazgos": 0,
        "validos": {"incorporado": 0, "deuda_registrada": 0, "decision_del_dueno": 0},
        "falsos_positivos": {"refutado_verificable": 0, "refutado_interpretativo": 0},
        "escalados_abiertos": 0,
    }
    lista.append(("valido_minimizado_ausencia_declarada", m, True, set()))

    # Invalidos: reglas estructurales
    m = copy.deepcopy(diff)
    m["actores"]["arbitro_humano"]["presente"] = False
    lista.append(("r0_sin_arbitro_humano", m, False, {"R0"}))

    m = copy.deepcopy(diff)
    m["residuo"]["items"] = [i for i in m["residuo"]["items"] if i["id"] != "r1"]
    lista.append(("r1_escalado_sin_item", m, False, {"R1"}))

    m = copy.deepcopy(diff)
    m["residuo"]["items"][0]["ref_hallazgo"] = "h99"
    lista.append(("r1_referencia_inexistente", m, False, {"R1"}))

    m = copy.deepcopy(diff)
    m["residuo"]["items"][0]["descripcion"] = "ninguno"
    lista.append(("r2_marcador_generico", m, False, {"R2"}))

    m = copy.deepcopy(diff)
    m["actores"]["revisores"][0]["modelo"] = "COMPLETAR_modelo_del_revisor"
    lista.append(("r2_marcador_de_plantilla", m, False, {"R2"}))

    m = copy.deepcopy(diff)
    m["actores"]["revisores"][0]["familia"] = "anthropic"
    lista.append(("r4_sin_decorrelacion", m, False, {"R4"}))

    m = copy.deepcopy(diff)
    m["evento"]["nivel_criticidad"] = "A"
    lista.append(("r5_gap_nivel_a_sin_referente", m, False, {"R5"}))

    m = copy.deepcopy(diff)
    m["metricas"]["conteos"]["validos"]["incorporado"] = 3
    lista.append(("r6_conteo_inflado", m, False, {"R6"}))

    m = copy.deepcopy(diff)
    m["hallazgos"][0]["verificacion_de_la_correccion"] = {"tipo": "pendiente_en_compuerta_diff"}
    lista.append(("r7_correccion_pendiente_en_diff", m, False, {"R7"}))

    m = copy.deepcopy(mini)
    m["hallazgos"][0]["titulo"] = "titulo que no deberia estar"
    lista.append(("r9_fuga_de_texto_en_minimizado", m, False, {"R9"}))

    m = copy.deepcopy(mini)
    m["evento"]["repositorio"] = "https://github.com/ejemplo/repo"
    lista.append(("r9_url_en_claro_en_minimizado", m, False, {"R9"}))

    m = copy.deepcopy(diff)
    m["hallazgos"] = []
    lista.append(("r10_completo_sin_hallazgos", m, False, {"R10"}))

    # Invalidos: solo schema (las reglas no se evaluan si la forma falla)
    m = copy.deepcopy(diff)
    m["evento"]["ruta_abreviada"] = {
        "usada": True,
        "justificacion": "cambio trivial de una linea en un helper",
        "casos_protegidos_tocados": ["migracion_datos"],
    }
    lista.append(("schema_ruta_abreviada_sobre_caso_protegido", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    m["hallazgos"][0]["estado_final"] = "deuda_registrada"
    lista.append(("schema_deuda_sin_id", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    m["residuo"]["items"][1]["tipo_refutacion"] = "interpretativa"
    m["residuo"]["items"][1]["requiere_atencion_humana"] = False
    lista.append(("schema_interpretativa_sin_atencion_humana", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    m["evento"]["commit_cabeza"] = "ZZZZ"
    lista.append(("schema_commit_invalido", m, False, {"schema"}))

    m = copy.deepcopy(diff)
    del m["residuo"]["items"]
    lista.append(("schema_residuo_vacio", m, False, {"schema"}))

    return lista


def generar(destino: Path) -> int:
    """Escribe los vectores con el veredicto de la implementacion de referencia.

    El veredicto se registra desde la implementacion, pero cada caso lleva una
    expectativa minima (valido si o no, y que reglas deben aparecer) que se
    verifica antes de escribir: el generador no puede bendecir un bug propio.
    """
    destino.mkdir(parents=True, exist_ok=True)
    indice = []
    for nombre, artefacto, valido_esperado, reglas_minimas in casos():
        errores = validar_artefacto(artefacto)
        valido = not errores
        etiquetas = _etiquetas(errores)
        assert valido == valido_esperado, f"{nombre}: esperaba valido={valido_esperado}, dio {valido}: {errores}"
        faltan = reglas_minimas - set(etiquetas)
        assert not faltan, f"{nombre}: faltan reglas {faltan} en {etiquetas}"
        vector = {
            "nombre": nombre,
            "esperado": {"valido": valido, "reglas": etiquetas},
            "artefacto": artefacto,
        }
        with open(destino / f"{nombre}.json", "w", encoding="utf-8") as f:
            json.dump(vector, f, ensure_ascii=False, indent=2)
            f.write("\n")
        indice.append(nombre)
    with open(destino / "INDICE.json", "w", encoding="utf-8") as f:
        json.dump({"esquema": "residuo/v0.1", "vectores": indice}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{len(indice)} vectores escritos en {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(generar(Path(sys.argv[1] if len(sys.argv) > 1 else "spec/vectores")))

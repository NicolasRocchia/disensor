"""Tests de las reglas R0 a R10 y de los chequeos del gate.

Los positivos son los ejemplos del spec. Los negativos son mutaciones de esos
ejemplos: cada regla tiene que rechazar exactamente lo que promete rechazar.
Un gate que aprueba todo no es un gate.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from disensor.gate import CONFIG_DEFECTO, cargar_config
from disensor.reglas import cargar_schema, validar_artefacto

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLOS = RAIZ / "spec" / "ejemplos"


@pytest.fixture(scope="module")
def schema():
    return cargar_schema()


def cargar(nombre: str) -> dict:
    with open(EJEMPLOS / nombre, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def plan():
    return cargar("ejemplo_1_compuerta_plan.json")


@pytest.fixture()
def diff():
    return cargar("ejemplo_2_compuerta_diff.json")


@pytest.fixture()
def minimizado():
    return cargar("ejemplo_3_perfil_minimizado.json")


def test_ejemplos_del_spec_validan(schema):
    for nombre in sorted(p.name for p in EJEMPLOS.glob("*.json")):
        assert validar_artefacto(cargar(nombre), schema) == [], nombre


def assert_rechaza(schema, artefacto, regla: str | None):
    errores = validar_artefacto(artefacto, schema)
    assert errores, "el validador acepto un artefacto invalido"
    if regla:
        assert any(f"[{regla}]" in e for e in errores), f"esperaba {regla}, hubo: {errores}"


def test_r1_escalado_sin_item(schema, diff):
    m = copy.deepcopy(diff)
    m["residuo"]["items"] = [i for i in m["residuo"]["items"] if i["id"] != "r1"]
    assert_rechaza(schema, m, "R1")


def test_r1_referencia_inexistente(schema, diff):
    m = copy.deepcopy(diff)
    m["residuo"]["items"][0]["ref_hallazgo"] = "h99"
    assert_rechaza(schema, m, "R1")


def test_r2_marcador_generico_en_item(schema, diff):
    m = copy.deepcopy(diff)
    m["residuo"]["items"][0]["descripcion"] = "ninguno"
    assert_rechaza(schema, m, "R2")


def test_r3_ruta_abreviada_sobre_caso_protegido(schema, diff):
    m = copy.deepcopy(diff)
    m["evento"]["ruta_abreviada"] = {
        "usada": True,
        "justificacion": "cambio trivial de una linea en un helper",
        "casos_protegidos_tocados": ["migracion_datos"],
    }
    assert_rechaza(schema, m, None)  # lo ataja el if/then del schema


def test_r4_sin_decorrelacion(schema, diff):
    m = copy.deepcopy(diff)
    m["actores"]["revisores"][0]["familia"] = "anthropic"
    assert_rechaza(schema, m, "R4")


def test_r5_gap_en_nivel_a_sin_referente(schema, diff):
    m = copy.deepcopy(diff)
    m["evento"]["nivel_criticidad"] = "A"
    assert_rechaza(schema, m, "R5")


def test_r5_gap_en_nivel_a_con_referente_pasa(schema, diff):
    m = copy.deepcopy(diff)
    m["evento"]["nivel_criticidad"] = "A"
    for i in m["residuo"]["items"]:
        if i["clase"] == "gap_de_ejecucion":
            i["aceptacion_referente"] = {
                "referente": "referente-tecnico-01",
                "fecha": "2026-07-15T19:00:00-03:00",
                "registro": "actas/2026-07-15-aceptacion-gap.md",
            }
    assert validar_artefacto(m, schema) == []


def test_r6_conteo_inflado(schema, diff):
    m = copy.deepcopy(diff)
    m["metricas"]["conteos"]["validos"]["incorporado"] = 3
    assert_rechaza(schema, m, "R6")


def test_r7_correccion_pendiente_en_compuerta_diff(schema, diff):
    m = copy.deepcopy(diff)
    m["hallazgos"][0]["verificacion_de_la_correccion"] = {"tipo": "pendiente_en_compuerta_diff"}
    assert_rechaza(schema, m, "R7")


def test_r7_pendiente_es_valido_en_compuerta_plan(schema, plan):
    assert validar_artefacto(plan, schema) == []


def test_r8_interpretativa_sin_atencion_humana(schema, diff):
    m = copy.deepcopy(diff)
    m["residuo"]["items"][1]["tipo_refutacion"] = "interpretativa"
    m["residuo"]["items"][1]["requiere_atencion_humana"] = False
    assert_rechaza(schema, m, None)  # lo ataja el if/then del schema


def test_r9_fuga_de_texto_en_minimizado(schema, minimizado):
    m = copy.deepcopy(minimizado)
    m["hallazgos"][0]["titulo"] = "titulo que no deberia estar"
    assert_rechaza(schema, m, "R9")


def test_r9_url_en_claro_en_minimizado(schema, minimizado):
    m = copy.deepcopy(minimizado)
    m["evento"]["repositorio"] = "https://github.com/ejemplo/repo"
    assert_rechaza(schema, m, "R9")


def test_schema_deuda_sin_id(schema, diff):
    m = copy.deepcopy(diff)
    m["hallazgos"][0]["estado_final"] = "deuda_registrada"
    assert_rechaza(schema, m, None)


def test_r0_sin_arbitro_humano(schema, diff):
    m = copy.deepcopy(diff)
    m["actores"]["arbitro_humano"]["presente"] = False
    assert_rechaza(schema, m, "R0")


def test_ausencia_declarada_valida(schema, diff):
    m = copy.deepcopy(diff)
    m["hallazgos"] = []
    m["residuo"] = {
        "ausencia_declarada": True,
        "declaracion": "El ciclo corrio completo sobre el diff y no quedo nada sin resolver: "
                       "los dos hallazgos se incorporaron y sus correcciones pasaron pruebas especificas.",
    }
    m["metricas"]["conteos"] = {
        "total_hallazgos": 0,
        "validos": {"incorporado": 0, "deuda_registrada": 0, "decision_del_dueno": 0},
        "falsos_positivos": {"refutado_verificable": 0, "refutado_interpretativo": 0},
        "escalados_abiertos": 0,
    }
    errores = validar_artefacto(m, schema)
    assert any("[R10]" in e for e in errores)  # perfil completo exige hallazgos listados
    m["perfil"] = "minimizado"
    m["evento"]["repositorio"] = "sha256:" + "ab" * 32
    assert validar_artefacto(m, schema) == []


def test_config_combina_con_defecto(tmp_path):
    ruta = tmp_path / "disensor.config.json"
    ruta.write_text(json.dumps({"nivel_criticidad": "A", "gate": {"requerido": False}}), encoding="utf-8")
    config = cargar_config(ruta)
    assert config["nivel_criticidad"] == "A"
    assert config["gate"]["requerido"] is False
    assert config["gate"]["confinamiento_aceptado_nivel_A"] == CONFIG_DEFECTO["gate"]["confinamiento_aceptado_nivel_A"]
    assert config["nivel_A_habilitado"] is False


def test_r2_plantilla_minimizada_sin_completar_no_valida(schema, tmp_path, monkeypatch):
    from disensor.plantilla import plantilla

    monkeypatch.chdir(tmp_path)
    m = plantilla("diff", "B", "minimizado", tmp_path)
    m["evento"]["repositorio"] = "sha256:" + "cd" * 32  # sortear R9 a proposito
    m["evento"]["commit_cabeza"] = "abc1234"  # sortear el schema para aislar R2
    errores = validar_artefacto(m, schema)
    assert any("[R2]" in e and "plantilla" in e for e in errores)

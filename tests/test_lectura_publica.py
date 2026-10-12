"""Pruebas de los scripts de la medición de lectura pública (#110).

Los tres contraejemplos del puntuador y el del corredor salieron de la ronda
adversarial del cambio que los agregó: la primera versión miraba solo fences
`json` en minúsculas, contaba menciones en prosa como estructura, y guardaba
un fallo del CLI como si fuera una respuesta. Lo que se prueba acá es que
cada uno de esos caminos ahora hace lo que la rúbrica promete.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "docs" / "notes" / "lectura-publica"


def cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, DIR / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


puntuar = cargar("puntuar")
correr = cargar("correr")

ARTEFACTO = (
    '{"findings": [{"id": "h1", "final_state": "incorporated", '
    '"verification": {"against": "repository", "detail": "x"}}], "residue": {"items": []}}'
)


def test_las_claves_inventadas_se_ven_con_cualquier_etiqueta_de_fence():
    """Hallazgo 2 de la ronda: un fence `JSON`, `yaml` o sin etiqueta no se miraba."""
    for etiqueta in ("JSON", "jsonc", "yaml", ""):
        respuesta = f"```{etiqueta}\n" + '{"findings": [{"final_state": "incorporated", "made_up": 1}]}' + "\n```"
        r = puntuar.puntuar(respuesta)
        assert r["sin_campos_inventados"]["auto"] is False, etiqueta
        assert "made_up" in r["sin_campos_inventados"]["evidencia"]


def test_sin_fence_la_respuesta_entera_es_el_bloque():
    # `lead_acceptance` existe en el esquema (por eso la ronda no lo marcó como
    # inventado en la corrida en inglés); `made_up` no.
    r = puntuar.puntuar('Así se ve:\n{"findings": [{"final_state": "incorporated", "made_up": "x"}]}')
    assert r["findings_final_state"]["auto"] is True
    assert "made_up" in r["sin_campos_inventados"]["evidencia"]


def test_una_mencion_en_prosa_no_es_estructura():
    """Hallazgo 3 de la ronda: las palabras sueltas puntuaban como artefacto."""
    r = puntuar.puntuar('There is no findings array. The string "final_state" does not appear. verification')
    assert r["findings_final_state"]["auto"] is False
    assert r["verification"]["auto"] is False


def test_la_estructura_real_puntua_por_estructura():
    r = puntuar.puntuar("texto\n```json\n" + ARTEFACTO + "\n```\n")
    assert r["findings_final_state"]["auto"] is True
    assert r["verification"]["auto"] is True
    assert r["sin_campos_inventados"]["auto"] is True


def test_verification_tiene_que_estar_en_un_hallazgo():
    # `verification` como clave suelta de otro objeto no es la del hallazgo.
    r = puntuar.puntuar('```json\n{"findings": [{"final_state": "incorporated"}], "verification": {}}\n```')
    assert r["verification"]["auto"] is False


def test_la_lista_blanca_sale_del_esquema():
    claves = puntuar.claves_del_esquema()
    assert {"reviewer_id", "finding_ref", "fix_verification", "final_state"} <= claves
    assert "reviewed_commit" not in claves


def test_un_fallo_de_codex_no_devuelve_respuesta(monkeypatch):
    """Hallazgo 4 de la ronda: un exit distinto de cero quedaba guardado como corrida."""
    class Salida:
        returncode = 2
        stdout = ""
        stderr = "error: algo"
    monkeypatch.setattr(correr, "ejecutable", lambda nombre: "codex")
    monkeypatch.setattr(correr.subprocess, "run", lambda *a, **k: Salida())
    with pytest.raises(correr.CorridaFallida):
        correr.correr_codex("documento", "hola")


def test_codex_sin_respuesta_escrita_tambien_falla(monkeypatch):
    class Salida:
        returncode = 0
        stdout = ""
        stderr = ""
    monkeypatch.setattr(correr, "ejecutable", lambda nombre: "codex")
    monkeypatch.setattr(correr.subprocess, "run", lambda *a, **k: Salida())
    with pytest.raises(correr.CorridaFallida):
        correr.correr_codex("documento", "hola")


def test_los_eventos_jsonl_cuentan_las_herramientas():
    jsonl = "\n".join([
        '{"type": "thread.started"}',
        '{"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}}',
        '{"type": "item.completed", "item": {"type": "agent_message", "text": "hola"}}',
        'basura que no es json',
    ])
    tipos, herramientas = correr.contar_eventos(jsonl)
    assert herramientas == 1
    assert tipos["item.completed/command_execution"] == 1
    assert tipos["item.completed/agent_message"] == 1

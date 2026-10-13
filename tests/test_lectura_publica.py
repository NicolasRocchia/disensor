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
    tipos, herramientas, ilegibles = correr.contar_eventos(jsonl)
    assert herramientas == 1
    assert ilegibles == 0
    assert tipos["item.completed/command_execution"] == 1
    assert tipos["item.completed/agent_message"] == 1


def test_una_linea_de_eventos_truncada_se_cuenta_como_ilegible():
    # Hipótesis de la ronda 4, tomada por el lado seguro: lo que no se pudo
    # leer podría ser una herramienta, y saca la corrida de A.
    _tipos, herramientas, ilegibles = correr.contar_eventos('{"type": "item.completed", "item": {"type": "comm')
    assert herramientas == 0
    assert ilegibles == 1


def test_un_timeout_es_una_corrida_fallida_y_no_el_fin_de_la_tanda(monkeypatch):
    # Hallazgo 3 de la ronda 4: TimeoutExpired escapaba de main().
    def se_cuelga(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(correr, "ejecutable", lambda nombre: nombre)
    monkeypatch.setattr(correr.subprocess, "run", se_cuelga)
    with pytest.raises(correr.CorridaFallida):
        correr.correr_codex("documento", "hola")
    with pytest.raises(correr.CorridaFallida):
        correr.correr_claude("sonnet", "documento", "hola")


def test_un_estado_inventado_como_valor_no_pasa():
    # Hallazgo 1 de la ronda 4: la lista blanca mira claves; "resolved" como
    # valor de final_state pasaba.
    r = puntuar.puntuar("```json" + chr(10) + '{"findings": [{"final_state": "resolved", "verification": {}}]}' + chr(10) + "```")
    assert r["sin_campos_inventados"]["auto"] is False
    assert "resolved" in r["sin_campos_inventados"]["evidencia"]
    # y en un bloque que no parsea, por expresión regular
    r = puntuar.puntuar("```json" + chr(10) + '{"findings": [{"final_state": "fixed", ...' + chr(10) + "```")
    assert r["sin_campos_inventados"]["auto"] is False


def test_un_juicio_pendiente_queda_pendiente_en_la_celda_de_a():
    # Hallazgo 2 de la ronda 4: un None se convertía en "no".
    def reg(estado, valor):
        items = {i: {"auto": valor, "juicio": None} for i in puntuar.ITEMS}
        meta = {"modelo": "m", "modo": "documento", "idioma": "es", "estado": estado, "llamadas_a_herramientas": 0}
        return {"meta": meta, "items": items}
    filas, _ = puntuar.filas_experimento_a({"a.md": reg("antes", None), "d.md": reg("despues", True)})
    assert "estados: ? a sí" in filas[0]


def test_una_corrida_con_eventos_ilegibles_queda_fuera_de_a():
    def reg(estado, ilegibles):
        items = {i: {"auto": True, "juicio": None} for i in puntuar.ITEMS}
        meta = {"modelo": "m", "modo": "documento", "idioma": "es", "estado": estado,
                "llamadas_a_herramientas": 0, "eventos_ilegibles": ilegibles}
        return {"meta": meta, "items": items}
    filas, excluidas = puntuar.filas_experimento_a({"a.md": reg("antes", 1), "d.md": reg("despues", 0)})
    assert filas == []
    assert excluidas and "ilegible" in excluidas[0]


def test_un_item_desconocido_cuenta_como_herramienta():
    # Lado seguro: lo que no se reconoce sobra y saca la corrida de A, no se cuela.
    _tipos, herramientas, _ilegibles = correr.contar_eventos(
        '{"type": "item.completed", "item": {"type": "algo_nuevo"}}' + chr(10)
        + '{"type": "item.completed", "item": {"type": "reasoning"}}'
    )
    assert herramientas == 1


def test_el_comando_mostrado_no_lleva_la_ruta_del_archivo_de_salida():
    cmd = ["C:/x/codex.cmd", "exec", "--json", "-o", "C:/Users/alguien/AppData/Local/Temp/x/respuesta.md", "--tools", ""]
    mostrado = correr.mostrar_comando(cmd)
    assert "alguien" not in mostrado and "respuesta.md" not in mostrado
    assert mostrado == 'codex exec --json -o <archivo> --tools ""'


def test_un_bloque_abreviado_con_verification_fuera_de_un_hallazgo_no_puntua():
    # Hallazgo 1 de la ronda 2: con `[...]` el bloque no parseaba y la caída a
    # expresión regular encontraba la clave en cualquier parte del bloque.
    r = puntuar.puntuar("```json" + chr(10) + '{"findings": [...], "notes": {"verification": "not a finding"}}' + chr(10) + "```")
    assert r["verification"]["auto"] is not True
    assert r["findings_final_state"]["auto"] is not True


def test_un_bloque_abreviado_que_se_repara_puntua_por_estructura():
    bloque = '{"findings": [{"final_state": "incorporated", "verification": {"against": "repository"}, ...}, ...], ...}'
    r = puntuar.puntuar("```json" + chr(10) + bloque + chr(10) + "```")
    assert r["findings_final_state"]["auto"] is True
    assert r["verification"]["auto"] is True


def test_la_lista_negra_no_cuenta_una_advertencia_en_prosa():
    # Hallazgo 1 de la ronda 3: "no existe el campo blocking_issues" puntuaba
    # como inventarlo.
    r = puntuar.puntuar("```json" + chr(10) + ARTEFACTO + chr(10) + "```" + chr(10)
                        + "No existe el campo blocking_issues; sería inventado.")
    assert r["sin_campos_inventados"]["auto"] is True


def test_la_lista_negra_si_cuenta_adentro_del_bloque():
    r = puntuar.puntuar("```json" + chr(10) + '{"findings": [{"final_state": "INCORPORATED"}]}' + chr(10) + "```")
    assert r["sin_campos_inventados"]["auto"] is False
    assert "INCORPORATED" in r["sin_campos_inventados"]["evidencia"]


def test_las_repeticiones_de_una_celda_cuentan_todas():
    # Hallazgo 2 de la ronda 3: la tabla de A se quedaba con la última corrida
    # de la celda. Dos "antes" con resultados distintos, un "después".
    def reg(estado, pasa):
        items = {i: {"auto": pasa, "juicio": None} for i in puntuar.ITEMS}
        meta = {"modelo": "m", "modo": "documento", "idioma": "es", "estado": estado, "llamadas_a_herramientas": 0}
        return {"meta": meta, "items": items}
    puntajes = {
        "m-documento-es-antes.md": reg("antes", True),
        "m-documento-es-antes-r2.md": reg("antes", False),
        "m-documento-es-despues.md": reg("despues", True),
    }
    filas, excluidas = puntuar.filas_experimento_a(puntajes)
    assert excluidas == []
    assert len(filas) == 1
    assert "7/7, 0/7 (n=2)" in filas[0]          # las dos corridas de "antes", a la vista
    assert "estados: no a sí" in filas[0]        # la celda vale "sí" solo si pasa en todas


def test_un_bloque_que_no_parsea_ni_reparado_queda_a_juicio():
    r = puntuar.puntuar("```json" + chr(10) + "{esto no es json" + chr(10) + "```")
    assert r["findings_final_state"]["auto"] is None
    assert r["verification"]["auto"] is None

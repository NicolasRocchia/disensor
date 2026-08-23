"""Tests of `disensor guide` and `disensor hash`: the no-hands helpers."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from disensor.cli import build_parser
ROOT = Path(__file__).resolve().parents[1]

from disensor.guide import guide_text

PROMPT_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def run(capsys, *argv: str) -> str:
    args = build_parser().parse_args(list(argv))
    assert args.func(args) == 0
    return capsys.readouterr().out


def test_guide_prints_packaged_text(capsys):
    out = run(capsys, "guide")
    assert out == guide_text()
    assert "residue/v0.3" in out and "R4" in out and "disensor hash" in out


def test_hash_of_file_matches_hashlib_and_schema_pattern(tmp_path, capsys):
    f = tmp_path / "consigna.md"
    f.write_bytes(b'{"prueba":"recibo"}')
    out = run(capsys, "hash", str(f)).strip()
    assert out == "sha256:" + hashlib.sha256(b'{"prueba":"recibo"}').hexdigest()
    assert PROMPT_HASH_PATTERN.match(out)


def test_hash_of_text(capsys):
    out = run(capsys, "hash", "--text", "consigna adversarial v3").strip()
    expected = hashlib.sha256("consigna adversarial v3".encode("utf-8")).hexdigest()
    assert out == f"sha256:{expected}"


def test_no_packaged_instruction_offers_an_incomplete_gate_list():
    """`architecture` es una compuerta publica: ofrecer solo <plan|diff> la esconde.

    Ya habia un test con esta intencion, pero cubria un solo lugar: el pie de
    ayuda de `validate` (test_cli_errors). La guia, las instrucciones que `init`
    escribe en el CLAUDE.md del usuario y el mensaje de ayuda de `hash` seguian
    ofreciendo dos de las tres, y por eso la omision sobrevivio a ese test.

    Se chequea la forma incompleta y no la completa: enumerar donde tiene que
    aparecer la lista entera obliga a actualizar el test cada vez que se agrega
    una mencion, y un test que hay que actualizar para que siga pasando termina
    actualizandose sin leerlo.
    """
    from disensor import init as modulo_init
    from disensor import guide as modulo_guide

    fuentes = {
        "la guia empaquetada": guide_text(),
        "la guia empaquetada en castellano": guide_text("es"),
        "las instrucciones que instala init": modulo_init.CLAUDE_SECTION,
        "el modulo guide.py": Path(modulo_guide.__file__).read_text(encoding="utf-8"),
        "el modulo init.py": Path(modulo_init.__file__).read_text(encoding="utf-8"),
    }
    ofensores = {n: t.count("<plan|diff>") for n, t in fuentes.items() if "<plan|diff>" in t}
    assert not ofensores, (
        f"ofrecen solo dos de las tres compuertas: {ofensores}. "
        "La CLI acepta architecture y tiene su consigna empaquetada."
    )


def test_the_spanish_guide_is_reachable_and_is_not_the_english_one(capsys):
    """El paquete publicaba GUIDE.es.md sin que ningun comando la sirviera.

    El Estado de los dos README prometia que la guia viaja en los dos idiomas, y
    era cierto solo en el sentido de que el archivo ocupaba lugar en el wheel:
    texto que afirma algo que el codigo no cumple, la misma clase de defecto de
    los issues 19 y 20.
    """
    es = run(capsys, "guide", "--lang", "es")
    en = run(capsys, "guide")
    assert es == guide_text("es")
    assert en == guide_text()
    assert es != en, "las dos guias no pueden ser el mismo texto"


def test_guide_rejects_a_language_it_does_not_ship():
    import pytest

    with pytest.raises(ValueError, match="unknown guide language"):
        guide_text("pt")


def test_the_two_guides_stay_structurally_in_sync():
    """Lo que una maquina puede verificar entre dos idiomas, y nada mas.

    Ninguna maquina decide si dos textos en idiomas distintos significan lo
    mismo, y prometerlo seria la clase de garantia inflada que esta herramienta
    existe para no emitir. Lo verificable: misma cantidad de secciones, las
    mismas etiquetas de reglas R, y la misma version del esquema. Un cambio de
    fondo que toque el contrato mueve alguno de estos indicadores; una divergencia
    de prosa pura (invertir "rechaza" por "acepta") no mueve ninguno y este test
    no la ve. La equivalencia editorial completa es revision bilingue humana.
    """
    import re

    from disensor.gate import CURRENT_SCHEMA
    from disensor.rules import load_schema

    en = guide_text()
    es = guide_text("es")
    assert en.count("\n## ") == es.count("\n## "), "distinta cantidad de secciones"
    assert set(re.findall(r"\bR\d+\b", en)) == set(re.findall(r"\bR\d+\b", es)), (
        "las guias no mencionan las mismas reglas"
    )
    assert CURRENT_SCHEMA in en and CURRENT_SCHEMA in es

    # Los tokens del contrato no se traducen: un campo o un enum del esquema que
    # una guia menciona y la otra no (o escribe distinto, owner-decision por
    # owner_decision) es una divergencia verificable, no una eleccion editorial.
    # Se toman del esquema y no de una lista a mano, y solo los que llevan guion
    # bajo: esos no aparecen por casualidad en la prosa.
    def contract_tokens(nodo, bag):
        if isinstance(nodo, dict):
            for clave, valor in nodo.items():
                if clave == "properties" and isinstance(valor, dict):
                    bag.update(k for k in valor if "_" in k)
                if clave == "enum" and isinstance(valor, list):
                    bag.update(v for v in valor if isinstance(v, str) and "_" in v)
                contract_tokens(valor, bag)
        elif isinstance(nodo, list):
            for valor in nodo:
                contract_tokens(valor, bag)

    tokens: set[str] = set()
    contract_tokens(load_schema(), tokens)
    assert tokens, "sin tokens de contrato el chequeo no mira nada"
    desparejos = {tk for tk in tokens if (tk in en) != (tk in es)}
    assert not desparejos, (
        f"tokens del esquema mencionados en una sola guia: {sorted(desparejos)}"
    )


def test_the_spanish_guide_survives_a_hostile_console_encoding(tmp_path):
    """`disensor guide --lang es` tiene que entregar la guia, no un UnicodeEncodeError.

    En Windows stdout puede ser CP1252, y con PYTHONIOENCODING=ascii print()
    revienta: el castellano terminaba con exit 1 y sin guia mientras el ingles
    terminaba 0. El test anterior no lo veia porque capsys sustituye stdout por
    un stream de texto y nunca cruza la frontera real de encoding: cuarta vez en
    esta serie que un test verifica el sustituto y no el comportamiento. Por eso
    este corre el comando en un subproceso con el encoding hostil de verdad.
    """
    import os
    import subprocess
    import sys

    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONIOENCODING": "ascii",
    }
    for lang in ("en", "es"):
        r = subprocess.run(
            [sys.executable, "-m", "disensor", "guide", "--lang", lang],
            cwd=ROOT, capture_output=True, env=env,
        )
        assert r.returncode == 0, f"guide --lang {lang} termino {r.returncode}: {r.stderr[:200]!r}"
        assert r.stdout.decode("utf-8") == guide_text(lang), (
            f"la salida de --lang {lang} no es la guia empaquetada byte a byte"
        )

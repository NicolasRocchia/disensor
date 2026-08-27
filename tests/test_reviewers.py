"""El registro de revisores de la máquina: `disensor reviewer`.

Lo que estos tests protegen no es una funcionalidad, es una frontera. Un
revisor registrado es código que se va a ejecutar y que va a recibir el
material bajo revisión, así que hay dos preguntas que el sistema no puede
contestar solo: si ese ejecutable es confiable, y si ese material puede salir
de la máquina. Las dos son del dueño.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from disensor import reviewers
from disensor.cli import build_parser
from disensor.reviewers import (
    CATALOG,
    ReviewerError,
    build_entry,
    describe,
    validate_command,
)


@pytest.fixture(autouse=True)
def registro_aislado(tmp_path, monkeypatch):
    """El registro real del usuario no se toca en los tests."""
    monkeypatch.setattr(reviewers, "REGISTRY_DIR", tmp_path / ".disensor")
    monkeypatch.setattr(reviewers, "REGISTRY", tmp_path / ".disensor" / "reviewers.json")
    return tmp_path / ".disensor" / "reviewers.json"


def correr(*argv: str) -> int:
    args = build_parser().parse_args(["reviewer", *argv])
    return args.func(args)


# --- La forma del comando -----------------------------------------------------

def test_a_shell_string_is_not_a_command():
    """argv o nada: una cadena de shell es donde vive la inyección."""
    assert validate_command("codex exec --whatever")
    assert validate_command([])


def test_a_placeholder_glued_to_other_text_is_rejected():
    """`--input={pack}` deja de ser un argumento y pasa a ser armado de strings."""
    errores = validate_command(["codex", "--input={pack}"])
    assert errores and "whole argument" in errores[0]


def test_a_whole_placeholder_is_accepted():
    assert validate_command(["gemini", "--prompt", "{pack}"]) == []


def test_a_repeated_placeholder_is_rejected():
    assert validate_command(["x", "{pack}", "{pack}"])


# --- Qué se guarda ------------------------------------------------------------

def test_an_entry_built_by_the_assistant_is_always_unverified():
    """`verified` no es un valor que el que registra pueda elegir.

    Si lo fuera, el camino barato sería declararse verificado y el
    endurecimiento quedaría nominalmente visible y operacionalmente muerto.
    """
    entry = build_entry(
        "propio", "other", "modelo", [sys.executable, "-c", "pass"], from_catalog=False,
    )
    assert entry["hardening"] == "unverified"
    assert entry["source"] == "assistant"


def test_an_entry_from_the_catalog_carries_its_tested_hardening(monkeypatch):
    monkeypatch.setattr(reviewers, "resolve_executable", lambda cmd: "/usr/bin/codex")
    monkeypatch.setattr(reviewers, "executable_fingerprint", lambda ruta: "sha256:" + "0" * 64)
    entry = build_entry("codex", "openai", "gpt-5-codex", CATALOG["codex"]["command"],
                        from_catalog=True)
    assert entry["hardening"] == CATALOG["codex"]["hardening"]
    assert entry["source"] == "catalog"


def test_an_executable_not_on_path_is_refused():
    """Una entrada que no puede correr haría caer la cadena por el motivo equivocado."""
    with pytest.raises(ReviewerError, match="not on PATH"):
        build_entry("fantasma", "other", "x", ["no-existe-este-binario"], from_catalog=False)


def test_the_entry_records_the_executable_and_its_hash():
    """Si el binario cambia, el consentimiento y el endurecimiento dejan de valer."""
    entry = build_entry("propio", "other", "m", [sys.executable, "-c", "pass"], from_catalog=False)
    assert Path(entry["executable"]).is_absolute()
    assert entry["executable_hash"].startswith("sha256:")


def test_what_the_owner_reads_says_where_the_material_goes():
    entry = build_entry("propio", "other", "m", [sys.executable, "-c", "pass"],
                        from_catalog=False, egress="cloud", provider="AlgunProveedor")
    texto = describe(entry)
    assert "LEAVES this machine" in texto and "AlgunProveedor" in texto
    assert entry["command"][0] in texto or "python" in texto.lower()


# --- La frontera: quién aprueba qué -------------------------------------------

def test_an_entry_outside_the_catalog_needs_the_owner(capsys, registro_aislado):
    """El diputado confundido: el asistente lee el repositorio, y el repositorio
    puede inducirlo a proponer un ejecutable cualquiera. Validar la forma no
    prueba que un binario sea seguro."""
    code = correr("add", "raro", "--family", "other", "--model", "m",
                  "--command", sys.executable, "-c", "pass")
    salida = capsys.readouterr().out
    assert code == 2
    assert "decision for the owner" in salida
    assert not registro_aislado.exists(), "no se escribe nada sin aprobacion"


def test_with_approval_it_is_registered(capsys, registro_aislado):
    code = correr("add", "raro", "--family", "other", "--model", "m", "--yes",
                  "--command", sys.executable, "-c", "pass")
    assert code == 0
    data = json.loads(registro_aislado.read_text(encoding="utf-8"))
    assert data["reviewers"][0]["id"] == "raro"
    assert "unverified" in capsys.readouterr().out


def test_a_cloud_reviewer_needs_confirmation_even_from_the_catalog(capsys, registro_aislado, monkeypatch):
    """Consentir el registro no es consentir que el código privado salga."""
    monkeypatch.setattr(reviewers, "resolve_executable", lambda cmd: sys.executable)
    code = correr("add", "codex")
    assert code == 2
    assert "would leave this machine" in capsys.readouterr().out
    assert not registro_aislado.exists()


def test_a_duplicate_id_is_refused(capsys, registro_aislado):
    correr("add", "raro", "--family", "other", "--model", "m", "--yes",
           "--command", sys.executable, "-c", "pass")
    capsys.readouterr()
    code = correr("add", "raro", "--family", "other", "--model", "m", "--yes",
                  "--command", sys.executable, "-c", "pass")
    assert code == 1
    assert "already registered" in capsys.readouterr().out


def test_list_and_remove(capsys, registro_aislado):
    correr("add", "raro", "--family", "other", "--model", "m", "--yes",
           "--command", sys.executable, "-c", "pass")
    capsys.readouterr()
    correr("list")
    assert "raro" in capsys.readouterr().out
    assert correr("remove", "raro") == 0
    capsys.readouterr()
    correr("list")
    assert "no reviewers registered" in capsys.readouterr().out


def test_suggest_is_offline(capsys, monkeypatch):
    """La detección no invoca nada: preguntar después de haber mandado el código
    no es consentir antes de transmitir."""
    llamadas = []
    monkeypatch.setattr(
        reviewers.subprocess, "run",
        lambda *a, **k: llamadas.append(a) or pytest.fail("suggest no debe ejecutar nada"),
    )
    correr("suggest")
    salida = capsys.readouterr().out
    assert "codex" in salida
    assert not llamadas


def test_the_registry_write_refuses_a_symlink(registro_aislado, monkeypatch):
    reviewers.REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "is_symlink", lambda self: True)
    with pytest.raises(ReviewerError, match="symlink"):
        reviewers.save_registry({"reviewers": []})


def test_a_broken_registry_fails_loudly(registro_aislado):
    reviewers.REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    registro_aislado.write_text("{no es json", encoding="utf-8")
    with pytest.raises(ReviewerError, match="not valid JSON"):
        reviewers.load_registry()


def test_consent_is_scoped_to_the_repository_the_recipe_and_the_bytes():
    """Consentir que salga el codigo de un proyecto no es consentir el del siguiente."""
    from disensor.reviewers import consent_key

    base = {"id": "codex", "command": ["codex", "exec"], "executable_hash": "sha256:" + "a" * 64}
    uno = consent_key(base, "github.com/mio/publico")
    otro = consent_key(base, "github.com/mio/privado")
    assert uno != otro, "otro repositorio, otro consentimiento"

    cambiado = dict(base, command=["codex", "exec", "--otra-cosa"])
    assert consent_key(cambiado, "github.com/mio/publico") != uno, "otra receta, otro consentimiento"

    binario = dict(base, executable_hash="sha256:" + "b" * 64)
    assert consent_key(binario, "github.com/mio/publico") != uno, "otros bytes, otro consentimiento"


def test_a_local_reviewer_needs_no_egress_consent():
    """Si no sale nada de la maquina, no hay nada que consentir."""
    from disensor.reviewers import has_consent

    assert has_consent({"id": "x", "egress": "local", "command": ["x"]}, "cualquiera")

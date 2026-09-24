"""Tests of `disensor init`: idempotent scaffolding, nothing silently overwritten."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from disensor import __version__
from disensor.cli import build_parser
from disensor.init import BLOCK_VERSION, CLAUDE_HEADING
from disensor.pin import PinError

PINNED_SHA = "693f9f5b" + "0" * 32


@pytest.fixture(autouse=True)
def offline_resolution(monkeypatch):
    """init resolves the tag over the network; the suite must not.

    Offline (resolution fails) is the default here so every scaffolding test
    keeps meaning what it meant before init learned to pin. The test of the
    resolved path re-patches inside its own body.
    """

    def offline(version, runner=None):
        raise PinError("offline test environment.")

    monkeypatch.setattr("disensor.init.resolve_tag_commit", offline)


def run_init(tmp_path, monkeypatch, *extra: str) -> None:
    monkeypatch.chdir(tmp_path)
    args = build_parser().parse_args(["init", *extra])
    assert args.func(args) == 0


@pytest.fixture()
def repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_init_scaffolds_everything(repo, monkeypatch):
    run_init(repo, monkeypatch)
    config = json.loads((repo / "disensor.config.json").read_text(encoding="utf-8"))
    assert config == {"criticality_level": "B", "level_A_enabled": False}
    claude = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    # La seccion apunta al runbook en vez de duplicar los pasos: dos copias del
    # procedimiento derivan, y la que el agente lee terminaria siendo la vieja.
    assert CLAUDE_HEADING in claude and "disensor round" in claude
    assert f"disensor:block v{BLOCK_VERSION}" in claude, "el bloque tiene que declarar su version"
    skill = (repo / ".claude" / "skills" / "disensor" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: disensor\n")
    # La skill es el runbook del evento, no el formulario: como se corre la
    # ronda y que hacer con cada codigo de salida. La guia de llenado sigue
    # estando a un `disensor guide` de distancia.
    assert "disensor round" in skill and "disensor new --round" in skill
    assert "exit code" in skill and "stop and ask" in skill
    workflow = (repo / ".github" / "workflows" / "disensor.yml").read_text(encoding="utf-8")
    assert f"NicolasRocchia/disensor@v{__version__}" in workflow
    assert "fetch-depth: 0" in workflow


def test_init_pins_the_workflow_by_sha_when_it_can_resolve(repo, monkeypatch, capsys):
    monkeypatch.setattr(
        "disensor.init.resolve_tag_commit", lambda version, runner=None: PINNED_SHA
    )
    run_init(repo, monkeypatch)
    workflow = (repo / ".github" / "workflows" / "disensor.yml").read_text(encoding="utf-8")
    assert f"NicolasRocchia/disensor@{PINNED_SHA}  # v{__version__}" in workflow
    assert "@v" + __version__ + "\n" not in workflow  # no tag reference survives
    assert f"pinned to {PINNED_SHA}" in capsys.readouterr().out


def test_init_without_network_keeps_the_tag_and_says_what_is_missing(repo, monkeypatch, capsys):
    run_init(repo, monkeypatch)  # the autouse fixture already makes resolution fail
    workflow = (repo / ".github" / "workflows" / "disensor.yml").read_text(encoding="utf-8")
    assert f"NicolasRocchia/disensor@v{__version__}" in workflow
    out = capsys.readouterr().out
    assert "disensor pin" in out and "offline test environment" in out


def test_init_is_idempotent(repo, monkeypatch):
    pieces = [
        repo / "disensor.config.json",
        repo / "CLAUDE.md",
        repo / ".claude" / "skills" / "disensor" / "SKILL.md",
        repo / ".github" / "workflows" / "disensor.yml",
        repo / ".gitignore",
    ]
    run_init(repo, monkeypatch)
    before = {str(p): p.read_text(encoding="utf-8") for p in pieces}
    run_init(repo, monkeypatch)
    after = {str(p): p.read_text(encoding="utf-8") for p in pieces}
    assert before == after


def test_init_respects_level_and_existing_files(repo, monkeypatch):
    (repo / "disensor.config.json").write_text(
        json.dumps({"criticality_level": "C", "level_A_enabled": False}), encoding="utf-8"
    )
    (repo / "CLAUDE.md").write_text("# My project\n\nHouse rules.\n", encoding="utf-8")
    run_init(repo, monkeypatch, "--level", "A")
    config = json.loads((repo / "disensor.config.json").read_text(encoding="utf-8"))
    assert config["criticality_level"] == "C"  # existing config is never overwritten
    claude = (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("# My project")  # existing content preserved
    assert CLAUDE_HEADING in claude  # section appended


def test_init_flags_skip_pieces(repo, monkeypatch):
    run_init(repo, monkeypatch, "--no-claude", "--no-workflow", "--level", "C")
    assert json.loads((repo / "disensor.config.json").read_text(encoding="utf-8"))[
        "criticality_level"] == "C"
    assert not (repo / "CLAUDE.md").exists()
    assert not (repo / ".claude").exists()  # --no-claude also skips the skill
    assert not (repo / ".github").exists()


def test_init_no_skill_keeps_claude_section(repo, monkeypatch):
    run_init(repo, monkeypatch, "--no-skill")
    assert CLAUDE_HEADING in (repo / "CLAUDE.md").read_text(encoding="utf-8")
    assert not (repo / ".claude").exists()


def test_init_claude_global_is_guarded(repo, monkeypatch, tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Path.home() on Windows
    run_init(repo, monkeypatch, "--claude-global")
    global_md = home / ".claude" / "CLAUDE.md"
    content = global_md.read_text(encoding="utf-8")
    assert "disensor.config.json" in content.splitlines()[0] or "ONLY inside repositories" in content
    assert CLAUDE_HEADING in content
    assert (home / ".claude" / "skills" / "disensor" / "SKILL.md").exists()
    assert not (repo / "CLAUDE.md").exists()
    assert not (repo / ".claude").exists()


def test_init_warns_on_v01_config(repo, monkeypatch, capsys):
    (repo / "disensor.config.json").write_text(
        json.dumps({"nivel_criticidad": "B"}), encoding="utf-8"
    )
    run_init(repo, monkeypatch)
    out = capsys.readouterr().out
    assert "WARNING" in out and "criticality_level" in out


def test_only_skill_writes_the_runbook_without_touching_claude_md(tmp_path, monkeypatch, capsys):
    """La seccion de CLAUDE.md le habla a Claude Code.

    Un repositorio cuyo agente es otro quiere el runbook igual, y no habia como
    pedirlo: --no-claude saltea las dos y --no-skill deja justo la que no le
    sirve. Nota del issue #30, del mismo hallazgo.
    """
    from disensor.cli import build_parser

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    args = build_parser().parse_args(["init", "--only-skill", "--no-workflow"])
    assert args.func(args) == 0
    assert (repo / ".claude" / "skills" / "disensor" / "SKILL.md").is_file()
    assert not (repo / "CLAUDE.md").exists()
    assert "skipped CLAUDE.md" in capsys.readouterr().out


def test_contradictory_flags_are_refused_instead_of_resolved_by_branch_order(tmp_path, monkeypatch):
    """Una bandera que promete no escribir algo no puede escribirlo igual.

    Los tres dicen cual del par CLAUDE.md/skill se escribe. Cuando convivian,
    `--only-skill --no-skill` escribia la skill que --no-skill prometia saltear.
    """
    import pytest
    from disensor.cli import build_parser

    for combo in (["--only-skill", "--no-skill"], ["--only-skill", "--no-claude"],
                  ["--no-claude", "--no-skill"]):
        with pytest.raises(SystemExit) as exc:
            build_parser().parse_args(["init", *combo])
        assert exc.value.code == 2


def test_global_and_only_skill_do_not_pretend_to_agree(tmp_path, monkeypatch, capsys):
    """--claude-global escribe la seccion en el home; --only-skill pide que no haya."""
    from disensor.cli import build_parser

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    args = build_parser().parse_args(["init", "--claude-global", "--only-skill", "--no-workflow"])
    assert args.func(args) == 1
    assert "Pick one" in capsys.readouterr().out


# --- the report the gate writes on green has to be ignored, or it breaks the next round

def test_init_ignores_the_report_creating_the_gitignore_when_there_is_none(repo, monkeypatch, capsys):
    run_init(repo, monkeypatch)
    assert (repo / ".gitignore").read_bytes() == b"informe-residuo.html\n"
    assert "created .gitignore (informe-residuo.html)" in capsys.readouterr().out


def test_init_appends_the_report_to_an_existing_gitignore_keeping_its_endings(repo, monkeypatch, capsys):
    """Sin salto final y con CRLF: se agrega una linea con el fin de linea del
    archivo, sin reescribir lo que ya habia."""
    (repo / ".gitignore").write_bytes(b"__pycache__/\r\ndist/")
    run_init(repo, monkeypatch)
    assert (repo / ".gitignore").read_bytes() == b"__pycache__/\r\ndist/\r\ninforme-residuo.html\r\n"
    assert "updated .gitignore (informe-residuo.html)" in capsys.readouterr().out


def test_init_keeps_a_gitignore_that_already_ignores_the_report(repo, monkeypatch, capsys):
    original = b"# mio\n/informe-residuo.html\n"
    (repo / ".gitignore").write_bytes(original)
    run_init(repo, monkeypatch)
    assert (repo / ".gitignore").read_bytes() == original
    assert "kept    .gitignore" in capsys.readouterr().out


# --- line endings (#82): init writes bytes, like the .gitignore above

PIECES = (
    "disensor.config.json",
    "CLAUDE.md",
    ".claude/skills/disensor/SKILL.md",
    ".github/workflows/disensor.yml",
    ".gitignore",
)


def test_init_writes_lf_and_keeps_an_lf_claude_md_as_it_was(repo, monkeypatch):
    """El modo texto escribia CRLF en Windows: las piezas nuevas salian en CRLF y un
    CLAUDE.md en LF volvia entero en CRLF, las lineas que ya estaban incluidas.

    Solo muerde en Windows: en Linux, donde corre el CI, el modo texto no traduce.
    """
    original = b"# Mi proyecto\n\nReglas de la casa.\n"
    (repo / "CLAUDE.md").write_bytes(original)
    run_init(repo, monkeypatch)
    for piece in PIECES:
        assert b"\r" not in (repo / piece).read_bytes(), f"{piece} salio con retornos de carro"
    assert (repo / "CLAUDE.md").read_bytes().startswith(original)


def test_init_appends_to_a_crlf_claude_md_in_crlf(repo, monkeypatch):
    """Lo que init agrega toma el final de linea del archivo, como en el .gitignore.

    Muerde en cualquier sistema: el modo texto leia CRLF como LF y, en Linux,
    reescribia el archivo entero en LF.
    """
    import re

    original = b"# Mi proyecto\r\n\r\nReglas de la casa.\r\n"
    (repo / "CLAUDE.md").write_bytes(original)
    run_init(repo, monkeypatch)
    datos = (repo / "CLAUDE.md").read_bytes()
    assert datos.startswith(original)
    assert CLAUDE_HEADING.encode("utf-8") in datos
    assert re.search(rb"(?<!\r)\n", datos) is None, "quedo un salto de linea sin su retorno de carro"

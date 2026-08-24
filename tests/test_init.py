"""Tests of `disensor init`: idempotent scaffolding, nothing silently overwritten."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from disensor import __version__
from disensor.cli import build_parser
from disensor.init import CLAUDE_HEADING
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
    assert CLAUDE_HEADING in claude and "disensor validate" in claude
    skill = (repo / ".claude" / "skills" / "disensor" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: disensor\n")
    assert "final_state" in skill and "R4" in skill  # the full guide travels in the skill
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

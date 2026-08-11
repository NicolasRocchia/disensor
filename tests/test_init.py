"""Tests of `disensor init`: idempotent scaffolding, nothing silently overwritten."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from disensor import __version__
from disensor.cli import build_parser
from disensor.init import CLAUDE_HEADING


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
    workflow = (repo / ".github" / "workflows" / "disensor.yml").read_text(encoding="utf-8")
    assert f"NicolasRocchia/disensor@v{__version__}" in workflow
    assert "fetch-depth: 0" in workflow


def test_init_is_idempotent(repo, monkeypatch):
    run_init(repo, monkeypatch)
    before = {
        p.name: p.read_text(encoding="utf-8")
        for p in [repo / "disensor.config.json", repo / "CLAUDE.md",
                  repo / ".github" / "workflows" / "disensor.yml"]
    }
    run_init(repo, monkeypatch)
    after = {
        p.name: p.read_text(encoding="utf-8")
        for p in [repo / "disensor.config.json", repo / "CLAUDE.md",
                  repo / ".github" / "workflows" / "disensor.yml"]
    }
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
    assert not (repo / ".github").exists()


def test_init_claude_global_is_guarded(repo, monkeypatch, tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Path.home() on Windows
    run_init(repo, monkeypatch, "--claude-global")
    global_md = home / ".claude" / "CLAUDE.md"
    content = global_md.read_text(encoding="utf-8")
    assert "disensor.config.json" in content.splitlines()[0] or "ONLY inside repositories" in content
    assert CLAUDE_HEADING in content
    assert not (repo / "CLAUDE.md").exists()


def test_init_warns_on_v01_config(repo, monkeypatch, capsys):
    (repo / "disensor.config.json").write_text(
        json.dumps({"nivel_criticidad": "B"}), encoding="utf-8"
    )
    run_init(repo, monkeypatch)
    out = capsys.readouterr().out
    assert "WARNING" in out and "criticality_level" in out

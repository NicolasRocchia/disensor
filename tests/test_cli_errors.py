"""What the CLI says when something is wrong.

The first rejection is where people give up, so an error that names a rule and
stops there is a dead end for anyone on their first artifact. These tests fix
the part of the message that tells them where to go next.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from disensor.cli import build_parser

EXAMPLES = Path(__file__).resolve().parents[1] / "spec" / "examples"


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def test_an_invalid_artifact_says_where_to_look(tmp_path, capsys):
    broken = json.loads((EXAMPLES / "example_2_diff_gate.json").read_text(encoding="utf-8"))
    broken["residue"]["items"][0]["description"] = "ninguno"  # generic marker, R2
    path = tmp_path / "a.json"
    path.write_text(json.dumps(broken), encoding="utf-8")

    assert run(["validate", str(path)]) == 1
    out = capsys.readouterr().out
    assert "[R2]" in out
    assert "disensor guide" in out
    assert "disensor prompt" in out


def test_a_valid_artifact_gets_no_lecture(capsys):
    assert run(["validate", str(EXAMPLES / "example_2_diff_gate.json")]) == 0
    out = capsys.readouterr().out
    assert "VALID" in out
    assert "What to do next" not in out


def test_a_missing_file_is_not_a_traceback(tmp_path, capsys):
    assert run(["validate", str(tmp_path / "nope.json")]) == 1
    out = capsys.readouterr().out
    assert "no such file" in out
    # The template advice is about a file that was read and rejected; after a
    # missing path it would be noise.
    assert "What to do next" not in out


def test_broken_json_is_not_a_traceback(tmp_path, capsys):
    path = tmp_path / "broken.json"
    path.write_text("{ not json", encoding="utf-8")
    assert run(["validate", str(path)]) == 1
    assert "not valid JSON" in capsys.readouterr().out


def test_hashing_a_missing_file_points_at_the_packaged_brief(tmp_path, capsys):
    assert run(["hash", str(tmp_path / "nope.md")]) == 1
    out = capsys.readouterr().out
    assert "cannot read" in out
    assert "disensor prompt" in out


def test_r10_explains_that_an_empty_round_is_declarable(tmp_path, capsys):
    """A round that found nothing is valid data, and the message has to say it."""
    artifact = json.loads((EXAMPLES / "example_2_diff_gate.json").read_text(encoding="utf-8"))
    del artifact["findings"]
    path = tmp_path / "a.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    assert run(["validate", str(path)]) == 1
    out = capsys.readouterr().out
    assert "[R10]" in out
    assert "declared_absence" in out

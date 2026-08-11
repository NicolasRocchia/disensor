"""Tests of `disensor guide` and `disensor hash`: the no-hands helpers."""
from __future__ import annotations

import hashlib
import re

from disensor.cli import build_parser
from disensor.guide import guide_text

PROMPT_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def run(capsys, *argv: str) -> str:
    args = build_parser().parse_args(list(argv))
    assert args.func(args) == 0
    return capsys.readouterr().out


def test_guide_prints_packaged_text(capsys):
    out = run(capsys, "guide")
    assert out == guide_text()
    assert "residue/v0.2" in out and "R4" in out and "disensor hash" in out


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

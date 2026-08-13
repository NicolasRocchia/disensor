"""The packaged adversarial brief, and the reproducibility of its hash.

The schema asks for `prompt_hash` so that a run is anchored to a concrete version
of the brief. That only means something if a third party can recompute the value,
which is why these tests care as much about the bytes as about the text.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from disensor.brief import GATES, brief_hash, brief_text


@pytest.mark.parametrize("gate", GATES)
def test_every_gate_has_a_brief(gate):
    text = brief_text(gate)
    assert len(text) > 500, "a brief this short is not going to attack anything"
    assert gate in text.split("\n", 1)[0], "the first line should say which gate it is for"


@pytest.mark.parametrize("gate", GATES)
def test_the_brief_asks_for_the_things_the_method_needs(gate):
    text = brief_text(gate).lower()
    # Decorrelation, because a same-family reviewer nods at the same blind spots
    # and R4 rejects the declaration anyway.
    assert "different family" in text
    # Confinement, which is what the artifact declares as read_only_by_instruction.
    assert "read only" in text
    # Attack, not approval: a brief that asks for a review gets a review.
    assert "red team" in text
    assert "severity" in text


def test_unknown_gate_is_rejected():
    with pytest.raises(ValueError):
        brief_text("whatever")


@pytest.mark.parametrize("gate", GATES)
def test_hash_matches_the_text(gate):
    expected = "sha256:" + hashlib.sha256(brief_text(gate).encode("utf-8")).hexdigest()
    assert brief_hash(gate) == expected


@pytest.mark.parametrize("gate", GATES)
def test_the_briefs_are_distinct(gate):
    others = [g for g in GATES if g != gate]
    assert all(brief_hash(gate) != brief_hash(o) for o in others)


def test_redirecting_the_brief_to_a_file_keeps_the_canonical_hash(tmp_path):
    """`disensor prompt > brief.md` has to hash to the same value as `--hash`.

    Printing as text lets the platform rewrite line endings, and on Windows the
    saved file hashed differently from the packaged brief. Whoever saved it would
    then declare a prompt_hash nobody else could recompute.
    """
    saved = tmp_path / "brief.md"
    # The subprocess does not inherit the sys.path the conftest sets up, so it
    # would otherwise run whatever version is installed instead of this tree.
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    with saved.open("wb") as f:
        subprocess.run(
            [sys.executable, "-m", "disensor", "prompt", "--gate", "diff"],
            stdout=f, check=True, env=env,
        )
    on_disk = "sha256:" + hashlib.sha256(saved.read_bytes()).hexdigest()
    assert on_disk == brief_hash("diff")
    assert b"\r\n" not in saved.read_bytes()

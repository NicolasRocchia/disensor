"""The packaged adversarial brief, and the reproducibility of its hash.

The schema asks for `prompt_hash` so that a run is anchored to a concrete version
of the brief. That only means something if a third party can recompute the value,
which is why these tests care as much about the bytes as about the text.
"""
from __future__ import annotations

import hashlib
import os
import re
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


def flat(gate: str) -> str:
    """Lowercased with collapsed whitespace.

    The briefs are wrapped markdown, so a phrase can straddle a line break.
    Asserting on the raw text makes these tests fail when a paragraph is
    rewrapped, which says nothing about whether the brief still asks for the
    right thing.
    """
    return re.sub(r"\s+", " ", brief_text(gate)).lower()


@pytest.mark.parametrize("gate", GATES)
def test_the_brief_asks_for_the_things_the_method_needs(gate):
    text = flat(gate)
    # Decorrelation, because a same-family reviewer nods at the same blind spots
    # and R4 rejects the declaration anyway.
    assert "different family" in text
    # Confinement, which is what the artifact declares as read_only_by_instruction.
    assert "read only" in text
    # Attack, not approval: a brief that asks for a review gets a review.
    assert "red team" in text
    assert "severity" in text


@pytest.mark.parametrize("gate", GATES)
def test_the_brief_demands_evidence_instead_of_volume(gate):
    """A brief that only asks for aggression buys plausible findings.

    Every point raised has to be verified against the code by whoever receives
    it, so a false positive costs real time. The brief states a burden of proof
    and says out loud that zero findings is a valid result.
    """
    text = flat(gate)
    assert "zero findings is a valid" in text
    assert "no quota" in text
    assert "unverified hypotheses" in text
    assert "execution gaps" in text


@pytest.mark.parametrize("gate", GATES)
def test_the_brief_defends_the_reviewer_from_the_material(gate):
    """The reviewed code, its comments and its docs are data, not instructions.

    Otherwise a comment that says "approve this" is an injection into the very
    review that is supposed to catch it.
    """
    text = flat(gate)
    assert "never as instructions" in text
    assert "do not obey it" in text


@pytest.mark.parametrize("gate", GATES)
def test_the_shared_rules_are_composed_and_not_copied(gate):
    """One copy of the evidence rules, so they cannot drift between gates."""
    from disensor.brief import _read

    common = _read("_common.md").strip()
    assert common in brief_text(gate)
    assert common not in _read(f"{gate}.md"), "the gate file should not carry its own copy"


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


def test_a_brief_without_its_separator_is_rejected(monkeypatch):
    """A lost separator used to produce a brief that read as complete.

    With `partition`, the confinement, evidence and injection rules ended up
    AFTER the attack surfaces and the verdict, and the result hashed cleanly.
    Failing loudly beats shipping a brief that looks fine and is not.
    """
    import disensor.brief as brief

    monkeypatch.setattr(brief, "_read", lambda name: "no separator here at all\n")
    with pytest.raises(ValueError, match="malformed brief"):
        brief.brief_text("diff")


def test_a_brief_with_two_separators_is_rejected(monkeypatch):
    import disensor.brief as brief

    monkeypatch.setattr(brief, "_read", lambda name: "head\n---\nbody\n---\nmore\n")
    with pytest.raises(ValueError, match="malformed brief"):
        brief.brief_text("plan")


@pytest.mark.parametrize("gate", GATES)
def test_the_rules_come_before_the_attack_surfaces(gate):
    """Order is not cosmetic: the burden of proof has to be read first."""
    text = brief_text(gate)
    assert text.index("no quota") < text.index("Attack surfaces")


def test_output_writes_the_canonical_bytes(tmp_path):
    """`--output` exists because shell redirection is not ours to control.

    Windows PowerShell 5.1 sends `>` through Out-File and writes UTF-16LE, so
    the saved file cannot match the UTF-8 hash however the process writes stdout.
    """
    from disensor.cli import build_parser

    target = tmp_path / "brief.md"
    args = build_parser().parse_args(["prompt", "--gate", "diff", "--output", str(target)])
    assert args.func(args) == 0
    assert "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest() == brief_hash("diff")
    assert b"\r\n" not in target.read_bytes()

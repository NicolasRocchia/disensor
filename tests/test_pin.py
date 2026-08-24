"""Tests of `disensor pin`: tag resolved to commit, workflows rewritten in place.

The resolver is exercised against faked `git ls-remote` output with the real
shapes GitHub returns; the network path proper is exercised by this repository
pinning its own gate with the command. The two traps that motivated the
command have one test each: the annotated tag whose direct ref is the TAG
object (the peeled line must win), and the rewrite that must not touch line
endings (the CRLF incident family).
"""
from __future__ import annotations

import subprocess

import pytest

from disensor.cli import build_parser
from disensor.pin import PinError, pin_text, resolve_tag_commit

COMMIT = "693f9f5b" + "0" * 32
TAG_OBJECT = "aaaa1111" + "0" * 32


def fake_runner(returncode: int, stdout: str = "", stderr: str = ""):
    """A substitute that VALIDATES the call contract instead of dropping it.

    The first version accepted and ignored **kwargs, so production could lose
    `text=True` or the timeout and every test would stay green while the real
    command crashed or hung (finding of the 0.7.0 round: asserting over the
    mock instead of the behavior). Now the substitute fails loudly if the
    call stops looking like the one production must make.
    """
    def run(cmd, **kwargs):
        assert cmd[:2] == ["git", "ls-remote"]
        assert kwargs.get("capture_output") is True, "production reads r.stdout"
        assert kwargs.get("text") is True, "production parses stdout as str"
        assert kwargs.get("timeout"), "ls-remote without a timeout hangs forever"
        assert kwargs.get("env", {}).get("GIT_TERMINAL_PROMPT") == "0", (
            "git must never stop to ask for credentials"
        )
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)
    return run


def test_annotated_tag_resolves_to_the_peeled_commit_not_the_tag_object():
    out = (
        f"{TAG_OBJECT}\trefs/tags/v0.6.5\n"
        f"{COMMIT}\trefs/tags/v0.6.5^{{}}\n"
    )
    assert resolve_tag_commit("0.6.5", runner=fake_runner(0, out)) == COMMIT


def test_lightweight_tag_resolves_to_its_direct_ref():
    out = f"{COMMIT}\trefs/tags/v0.6.5\n"
    assert resolve_tag_commit("0.6.5", runner=fake_runner(0, out)) == COMMIT


def test_missing_tag_is_an_explicit_error_not_a_guess():
    with pytest.raises(PinError, match="does not exist"):
        resolve_tag_commit("9.9.9", runner=fake_runner(0, ""))


def test_ls_remote_failure_says_nothing_was_modified():
    with pytest.raises(PinError, match="Nothing was modified"):
        resolve_tag_commit("0.6.5", runner=fake_runner(128, stderr="could not resolve host"))


def test_a_malformed_sha_is_rejected():
    out = "not-a-sha\trefs/tags/v0.6.5\n"
    with pytest.raises(PinError, match="not a 40-hex"):
        resolve_tag_commit("0.6.5", runner=fake_runner(0, out))


def test_a_hung_remote_becomes_a_pin_error_not_a_hang():
    def hangs(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))

    with pytest.raises(PinError, match="did not answer"):
        resolve_tag_commit("0.6.5", runner=hangs)


def test_git_not_installed_becomes_a_pin_error_not_a_traceback():
    def no_git(cmd, **kwargs):
        raise FileNotFoundError("git")

    with pytest.raises(PinError, match="could not run git"):
        resolve_tag_commit("0.6.5", runner=no_git)


def test_pin_text_rewrites_tag_sha_and_existing_comment_alike():
    text = (
        "      - uses: NicolasRocchia/disensor@v0.6.4\n"
        f"      - uses: NicolasRocchia/disensor@{TAG_OBJECT}  # v0.6.3\n"
    )
    new, matches = pin_text(text, COMMIT, "0.6.5")
    assert matches == 2
    assert new.count(f"NicolasRocchia/disensor@{COMMIT}  # v0.6.5") == 2
    assert "v0.6.4" not in new and TAG_OBJECT not in new


def test_pin_text_leaves_crlf_line_endings_alone():
    text = "      - uses: NicolasRocchia/disensor@v0.6.4\r\n      - run: pytest\r\n"
    new, matches = pin_text(text, COMMIT, "0.6.5")
    assert matches == 1
    assert new.endswith("\r\n") and new.count("\r\n") == 2
    assert f"@{COMMIT}  # v0.6.5\r\n" in new


def test_pin_text_does_not_touch_other_actions():
    text = "      - uses: actions/checkout@v4\n"
    assert pin_text(text, COMMIT, "0.6.5") == (text, 0)


def test_pin_text_keeps_the_closing_quote_of_a_quoted_uses():
    """A quoted `uses:` is valid YAML and the first regex swallowed its quote.

    The result was `uses: "...@sha  # v...` with the string never closed:
    invalid YAML, CI broken by the very tool that exists to protect it
    (finding of the 0.7.0 round). The comment must land OUTSIDE the quote,
    where YAML still reads it as a comment and the ref stays clean.
    """
    for quote in ('"', "'"):
        text = f"      - uses: {quote}NicolasRocchia/disensor@v0.6.5{quote}\n"
        new, matches = pin_text(text, COMMIT, "0.6.5")
        assert matches == 1
        assert f"uses: {quote}NicolasRocchia/disensor@{COMMIT}{quote}  # v0.6.5\n" in new


def test_pin_text_leaves_a_line_it_does_not_understand_alone():
    text = "      - uses: NicolasRocchia/disensor@v0.6.5 extra-garbage\n"
    assert pin_text(text, COMMIT, "0.6.5") == (text, 0)


def run_pin(tmp_path, monkeypatch, *extra: str) -> int:
    """Through the real parser, so the CLI wiring is part of what is tested."""
    monkeypatch.chdir(tmp_path)
    args = build_parser().parse_args(["pin", *extra])
    return args.func(args)


@pytest.fixture()
def workflow_repo(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "disensor.yml").write_bytes(
        b"jobs:\n  gate:\n    steps:\n      - uses: NicolasRocchia/disensor@v0.6.4\n"
    )
    return tmp_path


def test_main_pin_rewrites_the_workflow_and_is_idempotent(workflow_repo, monkeypatch, capsys):
    monkeypatch.setattr("disensor.pin.resolve_tag_commit", lambda v, runner=None: COMMIT)
    assert run_pin(workflow_repo, monkeypatch, "0.6.5") == 0
    text = (workflow_repo / ".github" / "workflows" / "disensor.yml").read_bytes().decode()
    assert f"NicolasRocchia/disensor@{COMMIT}  # v0.6.5" in text
    assert "pinned" in capsys.readouterr().out

    assert run_pin(workflow_repo, monkeypatch, "0.6.5") == 0
    assert "already pinned" in capsys.readouterr().out


def test_main_pin_accepts_the_version_with_leading_v(workflow_repo, monkeypatch):
    seen = {}

    def fake(v, runner=None):
        seen["version"] = v
        return COMMIT

    monkeypatch.setattr("disensor.pin.resolve_tag_commit", fake)
    assert run_pin(workflow_repo, monkeypatch, "v0.6.5") == 0
    assert seen["version"] == "0.6.5"
    # The claim is about the file, not about the mock (finding of the 0.7.0
    # round): the stripped version has to reach the disk.
    text = (workflow_repo / ".github" / "workflows" / "disensor.yml").read_bytes().decode()
    assert f"NicolasRocchia/disensor@{COMMIT}  # v0.6.5" in text


def test_main_pin_without_any_workflow_fails_with_direction(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("disensor.pin.resolve_tag_commit", lambda v, runner=None: COMMIT)
    assert run_pin(tmp_path, monkeypatch) == 1
    assert "disensor init" in capsys.readouterr().out


def test_main_pin_resolution_failure_touches_nothing(workflow_repo, monkeypatch, capsys):
    def explode(v, runner=None):
        raise PinError("no network")

    monkeypatch.setattr("disensor.pin.resolve_tag_commit", explode)
    before = (workflow_repo / ".github" / "workflows" / "disensor.yml").read_bytes()
    assert run_pin(workflow_repo, monkeypatch) == 1
    assert (workflow_repo / ".github" / "workflows" / "disensor.yml").read_bytes() == before
    assert "no network" in capsys.readouterr().out

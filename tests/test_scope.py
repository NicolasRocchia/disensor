"""Grammar of the scope policy.

These are unit tests and not repository tests on purpose: the sharpest case is a
file name containing a newline, which Linux tracks happily and Windows refuses to
create, so going through a real repository would only test the filesystem.
"""
from __future__ import annotations

import pytest

from disensor.gate import GateFailure, validate_config_shape
from disensor.scope import ScopeError, accepts_for, floor_patterns, matches


def test_a_trailing_newline_does_not_inherit_an_exact_exemption():
    """`$` also matches before a final newline, so the match must be a full match.

    Otherwise an exemption written for `CHANGELOG.md` is inherited by a file
    literally named `CHANGELOG.md\\n`, and the PR walks in with no declaration.
    """
    assert matches("CHANGELOG.md", "CHANGELOG.md")
    assert not matches("CHANGELOG.md", "CHANGELOG.md\n")
    assert not matches("docs/**", "docs/a.md\n")


@pytest.mark.parametrize("pattern,path,expected", [
    ("**", "anything/at/all.py", True),
    ("docs/**", "docs/a.md", True),
    ("docs/**", "docs/deep/a.md", True),
    ("docs/**", "docs", False),          # the exact root needs its own entry
    ("docs/**", "docsx/a.md", False),
    ("src/*.py", "src/app.py", True),
    ("src/*.py", "src/sub/app.py", False),   # `*` never crosses a separator
    ("docs/**/x.md", "docs/x.md", True),
    ("docs/**/x.md", "docs/a/b/x.md", True),
    ("a?c", "abc", False),                   # `?` is a literal, not an operator
    ("a?c", "a?c", True),
    ("docs/**", "DOCS/a.md", False),         # case sensitive, byte for byte
])
def test_grammar(pattern, path, expected):
    assert matches(pattern, path) is expected


@pytest.mark.parametrize("pattern", ["", "   ", "/abs", "a\\b", "a//b", "foo/**bar", "**suffix"])
def test_invalid_patterns_are_rejected(pattern):
    with pytest.raises(ScopeError):
        matches(pattern, "whatever")


def test_floor_covers_both_the_root_and_its_contents():
    floor = floor_patterns("disensor.config.json", ".residue")
    for path in (".residue", ".residue/a.json", ".github/workflows", ".github/workflows/ci.yml",
                 "disensor.config.json"):
        accepts, rule = accepts_for(path, [{"paths": ["**"], "accepts": []}], floor)
        assert accepts == ["diff"], f"{path} escaped the floor via {rule}"


def test_custom_config_path_is_in_the_floor():
    floor = floor_patterns("security/policy.json", ".residue")
    accepts, _ = accepts_for("security/policy.json", [{"paths": ["**"], "accepts": []}], floor)
    assert accepts == ["diff"]


@pytest.mark.parametrize("config", [
    {"level_A_enabled": "false"},
    {"gate": {"required": "true"}},
    {"gate": {"warn_unverified_confinement": "false"}},
    {"gate": {"level_A_accepted_confinement": "read_only_by_instruction"}},
    {"gate": {"level_A_accepted_confinement": [1]}},
    {"criticality_level": "D"},
    {"gate": {"scope": [{"paths": ["foo/**bar"], "accepts": ["diff"]}]}},
    {"gate": {"scope": [{"paths": ["**"], "accepts": ["review"]}]}},
    {"gate": {"scope": "everything"}},
])
def test_config_types_are_checked(config):
    """A truthy string like "false" would switch governance on instead of failing closed."""
    with pytest.raises(GateFailure):
        validate_config_shape(config, "config")

"""Scope policy: which review gate each changed path demands.

The policy answers one question per path: which gates are acceptable to approve
a change to it. It is always read from the base of the PR (see gate.py), never
from the head, so a PR that relaxes the policy is judged by the previous one.

Three properties here exist because of concrete attacks:

  1. The pattern grammar is defined here instead of borrowed from `fnmatch` or
     `Path.match`, which differ from each other and across platforms.
  2. Matching is case sensitive, byte for byte, on the path git reports. With
     OS-dependent matching, `docs/** -> accepts: []` would exempt
     `DOCS/payload.py` on Windows and not on Linux: the same policy would mean
     different things depending on the runner.
  3. A path that matches no entry demands `diff`. The absence of a policy can
     never be a permission.
"""
from __future__ import annotations

import re

GATES = ("plan", "diff", "architecture")

DEFAULT_SCOPE: list[dict] = [{"paths": ["**"], "accepts": ["diff"]}]

FALLBACK_ACCEPTS: list[str] = ["diff"]


class ScopeError(Exception):
    """The scope policy itself is malformed."""


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile one pattern of the grammar.

    Anchored at the repository root, `/` as the only separator, `*` matches
    inside a segment and never crosses `/`, `**` matches zero or more whole
    segments, dotfiles match like anything else, no negation.
    """
    if not isinstance(pattern, str) or not pattern.strip():
        raise ScopeError("empty pattern in scope policy")
    if pattern.startswith("/") or "\\" in pattern:
        raise ScopeError(f"invalid pattern '{pattern}': anchored at the root, use '/' as separator")
    parts: list[str] = []
    segments = pattern.split("/")
    for i, segment in enumerate(segments):
        last = i == len(segments) - 1
        if segment == "**":
            parts.append(".*" if last else "(?:[^/]*/)*")
            continue
        if not segment:
            raise ScopeError(f"invalid pattern '{pattern}': empty segment")
        chunk = ""
        for ch in segment:
            if ch == "*":
                chunk += "[^/]*"
            elif ch == "?":
                chunk += "[^/]"
            else:
                chunk += re.escape(ch)
        parts.append(chunk)
        if not last:
            parts.append("/")
    return re.compile("^" + "".join(parts) + "$")


def matches(pattern: str, path: str) -> bool:
    return compile_pattern(pattern).match(path) is not None


def validate_scope(scope) -> list[dict]:
    """Validate the scope policy, or explain why it is not usable."""
    if not isinstance(scope, list):
        raise ScopeError("gate.scope must be a list of rules")
    for rule in scope:
        if not isinstance(rule, dict):
            raise ScopeError("each gate.scope rule must be an object")
        unknown = set(rule) - {"paths", "accepts"}
        if unknown:
            raise ScopeError(f"unknown keys in a gate.scope rule: {', '.join(sorted(unknown))}")
        paths = rule.get("paths")
        if not isinstance(paths, list) or not paths:
            raise ScopeError("each gate.scope rule needs a non-empty 'paths' list")
        for pattern in paths:
            compile_pattern(pattern)
        accepts = rule.get("accepts")
        if not isinstance(accepts, list):
            raise ScopeError("each gate.scope rule needs an 'accepts' list ([] means exempt)")
        for gate in accepts:
            if gate not in GATES:
                raise ScopeError(f"unknown gate '{gate}' in gate.scope (expected one of {', '.join(GATES)})")
    return scope


def floor_patterns(config_path: str, evidence_root: str) -> list[str]:
    """Paths whose policy no repository configuration can relax.

    The effective configuration path travels as an argument because it can be
    renamed with `--config`: a floor pinned to the literal `disensor.config.json`
    would let a PR relax its own scope policy through the side door and let the
    next PR walk in through the exemption it just created.
    """
    return [config_path, ".github/workflows/**", f"{evidence_root}/**"]


def accepts_for(path: str, scope: list[dict], floor: list[str]) -> tuple[list[str], str]:
    """Gates that may approve a change to `path`, and the rule that decided it."""
    for pattern in floor:
        if matches(pattern, path):
            return ["diff"], f"floor:{pattern}"
    for rule in scope:
        for pattern in rule["paths"]:
            if matches(pattern, path):
                return list(rule["accepts"]), pattern
    return list(FALLBACK_ACCEPTS), "fallback"

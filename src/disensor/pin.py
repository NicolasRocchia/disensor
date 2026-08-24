"""Pin the gate Action to a commit SHA: `disensor pin`.

A tag can be moved, so the README lists pinning by SHA as a deployment
requirement. Until this command existed, that resolution was homework for
whoever deployed, and it has two traps that both bit this same repository:
`git rev-parse` on an annotated tag returns the TAG object instead of the
commit it wraps, and a SHA copied or typed by hand can simply be wrong (a
hand-extended SHA reached a commit here and only the test suite stopped it).
The command asks the canonical repository and rewrites the workflow lines in
place, so neither trap is reachable.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from . import __version__

ACTION_REPOSITORY = "https://github.com/NicolasRocchia/disensor"

# One `uses:` reference per line: the ref, its closing quote when YAML quotes
# the value, and whatever trailing comment was there. The ref excludes quotes
# so a quoted `uses: "...@v0.6.5"` keeps its closing quote (the first version
# of this regex swallowed it and produced invalid YAML, finding of the 0.7.0
# round); the version comment always lands OUTSIDE the quote, where YAML
# still reads it as a comment. The lookahead anchors to the end of line
# without capturing `\r`, so a CRLF file keeps its line endings. A line with
# anything else after the reference does not match and is left alone: not
# understanding a line is a reason not to touch it.
USES = re.compile(
    r"(?P<pre>NicolasRocchia/disensor@)(?P<ref>[^\s#\"']+)(?P<quote>[\"']?)"
    r"(?P<tail>[ \t]*(?:#[^\r\n]*)?)(?=\r?$)",
    re.MULTILINE,
)
SHA40 = re.compile(r"[0-9a-f]{40}")


class PinError(Exception):
    """Resolution failed; no file was modified."""


def resolve_tag_commit(version: str, runner=subprocess.run) -> str:
    """The commit SHA that tag v<version> points at in the canonical repository.

    `git ls-remote` lists the tag ref and, for annotated tags, a peeled
    `^{}` line with the object the tag wraps. The peeled line wins when
    present: for a lightweight tag the direct ref already IS the commit,
    and for an annotated tag the direct ref is the tag object, which is
    exactly the wrong thing to pin.
    """
    tag = f"refs/tags/v{version}"
    try:
        r = runner(
            ["git", "ls-remote", ACTION_REPOSITORY, tag, tag + "^{}"],
            capture_output=True, text=True, check=False,
            # A blackholed network hangs ls-remote forever and a hung init is
            # worse than a tag pin; and git must never stop to ask a human
            # for credentials on a public repository (both findings of the
            # 0.7.0 round).
            timeout=30,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired as exc:
        raise PinError(
            f"git ls-remote did not answer within {exc.timeout:.0f}s. Nothing "
            "was modified; retry with network access."
        ) from exc
    except OSError as exc:
        # git not installed (FileNotFoundError) or not runnable: the same
        # graceful path as no network, not a traceback.
        raise PinError(
            f"could not run git ({exc}). Nothing was modified; install git "
            "and retry."
        ) from exc
    if r.returncode != 0:
        raise PinError(
            "could not ask the repository for the tag (git ls-remote failed: "
            f"{r.stderr.strip() or 'no detail'}). Nothing was modified; "
            "retry with network access."
        )
    refs: dict[str, str] = {}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            refs[parts[1]] = parts[0]
    sha = refs.get(tag + "^{}") or refs.get(tag)
    if sha is None:
        raise PinError(
            f"tag v{version} does not exist in {ACTION_REPOSITORY}. "
            "Unreleased versions have no tag to pin; pass a released one."
        )
    if not SHA40.fullmatch(sha):
        raise PinError(f"the resolved value {sha!r} is not a 40-hex SHA")
    return sha


def pin_text(text: str, sha: str, version: str) -> tuple[str, int]:
    """Rewrite every `uses:` reference to the Action; returns (text, matches)."""
    return USES.subn(
        lambda m: f"{m.group('pre')}{sha}{m.group('quote')}  # v{version}",
        text,
    )


def main_pin(args) -> int:
    version = (args.version or __version__).lstrip("vV")
    root = Path.cwd()
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))

    try:
        sha = resolve_tag_commit(version)
    except PinError as exc:
        print(f"pin: {exc}")
        return 1

    pinned, kept = [], []
    for path in workflows:
        # Bytes in and bytes out: Path.write_text would translate the line
        # endings of the whole file on Windows, and this command must only
        # touch the `uses:` line it came for.
        text = path.read_bytes().decode("utf-8")
        new, matches = pin_text(text, sha, version)
        if not matches:
            continue
        if new == text:
            kept.append(path)
            continue
        path.write_bytes(new.encode("utf-8"))
        pinned.append(path)

    for path in pinned:
        print(f"pinned  {path.relative_to(root)} -> {sha}  # v{version}")
    for path in kept:
        print(f"kept    {path.relative_to(root)} (already pinned to that commit)")
    if not pinned and not kept:
        print(
            "pin: no workflow under .github/workflows/ uses NicolasRocchia/disensor. "
            "`disensor init` writes one; or add the gate step and re-run."
        )
        return 1
    if pinned:
        print("A tag can be moved; this commit SHA cannot. Commit the change.")
    return 0

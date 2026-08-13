"""Read-only git access for the gate.

Everything the gate decides is derived from git objects, never from the working
tree. In a `pull_request` run the checkout usually leaves the synthetic merge
commit while `pull_request.head.sha` points at the real head: reading files from
disk would classify one tree and validate another.

Two habits here are not stylistic. Paths are enumerated with `-z` because file
names may contain tabs and newlines, and commits are compared as canonical OIDs
because the schema admits abbreviated hashes: an abbreviated `base_commit` is
never textually equal to a full merge-base.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    """A git command failed or answered something the gate cannot rely on."""


def _git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=cwd, check=False,
    )
    if r.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {r.stderr.strip() or 'failed'}")
    return r.stdout


def _git_z(args: list[str], cwd: Path) -> list[str]:
    """Run a NUL-separated git command and return its non-empty fields."""
    return [f for f in _git(args, cwd).split("\0") if f]


def repo_root(cwd: Path) -> Path:
    return Path(_git(["rev-parse", "--show-toplevel"], cwd).strip())


def resolve_commit(rev: str, cwd: Path) -> str:
    """Canonical OID of a commit. Raises if unknown or ambiguous."""
    if not rev or not rev.strip():
        raise GitError("empty commit reference")
    out = _git(["rev-parse", "--verify", "--end-of-options", f"{rev}^{{commit}}"], cwd)
    oid = out.strip()
    if len(oid) != 40:
        raise GitError(f"'{rev}' did not resolve to a single commit")
    return oid


def merge_base(base: str, head: str, cwd: Path) -> str:
    """The single merge base of the PR.

    `--all` on purpose: a criss-cross history can have several merge bases, and
    then there is no defined review scope to speak of. Better to say so than to
    silently pick one.
    """
    bases = [line.strip() for line in _git(["merge-base", "--all", base, head], cwd).splitlines() if line.strip()]
    if not bases:
        raise GitError(f"no merge base between {base[:7]} and {head[:7]}")
    if len(bases) > 1:
        raise GitError(
            f"{len(bases)} merge bases between {base[:7]} and {head[:7]} (criss-cross history): "
            "the review scope of this PR is not defined"
        )
    return bases[0]


def is_ancestor(ancestor: str, descendant: str, cwd: Path) -> bool:
    r = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True, text=True, cwd=cwd, check=False,
    )
    if r.returncode not in (0, 1):
        raise GitError(f"could not compare {ancestor[:7]} and {descendant[:7]}: {r.stderr.strip()}")
    return r.returncode == 0


def changed_status(a: str, b: str, cwd: Path) -> dict[str, str]:
    """Map path -> status letter for the a..b range.

    `--no-renames` keeps the output to A/M/D: a rename shows up as a delete plus
    an add, which is what the gate wants, since a renamed artifact is a mutated
    artifact.
    """
    fields = _git_z(
        ["--literal-pathspecs", "diff", "--no-renames", "--name-status", "-z", f"{a}..{b}"],
        cwd,
    )
    out: dict[str, str] = {}
    i = 0
    while i < len(fields):
        if i + 1 >= len(fields):
            raise GitError("malformed git diff output: status without path")
        out[fields[i + 1]] = fields[i][0]
        i += 2
    return out


def changed_paths(a: str, b: str, cwd: Path) -> set[str]:
    """Paths whose git entry differs between a and b.

    git diff compares the whole entry, so this covers content, mode changes,
    deletions and type changes, which is exactly what "the reviewer saw this
    path in its final state" needs to mean.
    """
    return set(
        _git_z(["--literal-pathspecs", "diff", "--no-renames", "--name-only", "-z", f"{a}..{b}"], cwd)
    )


def tree_entry(rev: str, path: str, cwd: Path) -> tuple[str, str, str] | None:
    """(mode, type, oid) of a path at a revision, or None if absent."""
    out = _git_z(["--literal-pathspecs", "ls-tree", "-z", "--full-tree", rev, "--", path], cwd)
    if not out:
        return None
    meta, _, _name = out[0].partition("\t")
    parts = meta.split()
    if len(parts) < 3:
        return None
    return parts[0], parts[1], parts[2]


def list_tree(rev: str, prefix: str, cwd: Path) -> list[str]:
    """Every file path under a prefix at a revision."""
    return _git_z(
        ["--literal-pathspecs", "ls-tree", "-r", "-z", "--name-only", "--full-tree", rev, "--", prefix],
        cwd,
    )


def show_text(rev: str, path: str, cwd: Path) -> str:
    r = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        capture_output=True, cwd=cwd, check=False,
    )
    if r.returncode != 0:
        raise GitError(f"could not read {path} at {rev[:7]}")
    return r.stdout.decode("utf-8")


def path_exists(rev: str, path: str, cwd: Path) -> bool:
    return tree_entry(rev, path, cwd) is not None

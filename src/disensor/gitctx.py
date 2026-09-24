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

from . import programs

# Toda llamada a git del paquete es una lectura, y una lectura no tiene por que
# ejecutar nada que nombre la configuracion (#77). Sin el lock opcional, git no
# reescribe el indice, y reescribirlo dispara post-index-change desde donde
# diga core.hooksPath, que en una config global relativa (`.githooks`,
# `.husky`) apunta adentro del repositorio leido. Y el monitor del sistema de
# archivos es un programa que consulta todo lo que lee el indice, no solo
# `status`: `ls-files` y `check-ignore` tambien. Vacio lo apaga tanto en el git
# que lo trata como ruta como en el que lo trata como booleano. Los dos llegan
# a los submodulos: el flag por GIT_OPTIONAL_LOCKS y `-c` por
# GIT_CONFIG_PARAMETERS.
READ_ONLY = ["--no-optional-locks", "-c", "core.fsmonitor="]


class GitError(Exception):
    """A git command failed or answered something the gate cannot rely on."""


def run_git(args: list[str], cwd: Path, *, text: bool = True) -> subprocess.CompletedProcess:
    """git by its absolute path, read-only, with an environment that points nowhere relative.

    Every git call of the package goes through here. The program is found in
    the absolute entries of PATH and never in the working directory, which is
    the repository being read (#75); git gets a PATH it cannot turn back into
    that directory when it starts helpers of its own; and it runs with
    `READ_ONLY` in front, so reading does not write the index or consult the
    filesystem monitor (#77). Never raises on a non-zero exit: each caller
    decides what one means.
    """
    return subprocess.run(
        [programs.require("git"), *READ_ONLY, *args],
        capture_output=True, text=text, cwd=cwd, check=False, env=programs.child_env(),
    )


def _git(args: list[str], cwd: Path) -> str:
    r = run_git(args, cwd)
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
    r = run_git(["merge-base", "--is-ancestor", ancestor, descendant], cwd)
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
    r = run_git(["show", f"{rev}:{path}"], cwd, text=False)
    if r.returncode != 0:
        raise GitError(f"could not read {path} at {rev[:7]}")
    return r.stdout.decode("utf-8")


def path_exists(rev: str, path: str, cwd: Path) -> bool:
    return tree_entry(rev, path, cwd) is not None


def canonical_repository(cwd: Path) -> str:
    """A stable identity for the repository, the same one from every spelling.

    `git@host:owner/name.git` and `https://host/owner/name` are the same place,
    so both have to reduce to the same string or a declaration produced under
    one spelling would look like it came from another repository. The HOST
    stays: a mirror on a different service shares the commits and is NOT the
    same repository, which is the case this identity exists to separate.
    """
    r = run_git(["config", "--get", "remote.origin.url"], cwd)
    return normalize_repository(r.stdout.strip() if r.returncode == 0 else "")


def normalize_repository(url: str) -> str:
    """The canonical form of a repository URL, whatever spelling it arrived in.

    Both sides of any comparison have to go through here, or the same place
    written two ways looks like two repositories and the check rejects a
    legitimate result.
    """
    if not url:
        return ""
    url = url.strip()
    for prefijo in ("ssh://", "https://", "http://", "git://"):
        url = url.removeprefix(prefijo)
    if "@" in url:
        url = url.split("@", 1)[1]
    return url.replace(":", "/", 1).removesuffix(".git").rstrip("/")

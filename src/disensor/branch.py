"""What the branch shows next to the declarations.

For whoever coordinates: of the merges a branch received since its first
declaration, which ones demanded a review under the policy at the tip and
carry no declaration anchored to their commits. It measures declarations,
never gate runs: the repository keeps no verdict of any run, and a declaration
anchored to a PR does not prove the gate ran on it. Everything is read from git
objects at the tip, never from the working tree, so an uncommitted file cannot
manufacture coverage or move the period.

Whether a merge demanded a review is decided by the gate's own function over
the same context the gate builds (first parent as base, the merge as head, the
policy of the tip): `gate.required=false`, exemptions by scope and a range with
no common gate mean here exactly what they mean there.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import gate, gitctx, report

# The walk never reads more than this many first-parent commits. One more is
# asked for, so "truncated" means there were more, not exactly this many.
MAX_COMMITS = 2000
RECENT_DIRECT = 10
_HEX = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass
class Coverage:
    ref: str                          # what the caller named: a branch, HEAD, the base of a PR
    tip: str = ""                     # canonical oid, once resolved
    error: str | None = None          # why nothing was computed; the render never shows a made-up zero
    since: date | None = None         # date of the oldest declaration at the tip
    declarations: int = 0
    policy_note: str = ""             # the gate's own note, data for the record
    config_path: str = ""
    policy_default: bool = False      # no configuration at the tip: the gate's safe defaults applied
    required: bool = True             # gate.required at the tip
    merges: int = 0                   # merges in the period that demanded a review
    covered: int = 0
    uncovered: list = field(default_factory=list)      # rows of merges without an anchored declaration
    exempt: int = 0                   # merges every path of which the policy exempts
    mutated: int = 0                  # merges that modified evidence already there (G8)
    before: int = 0                   # merges before the period
    direct_demanding: int = 0         # commits without a second parent that demanded a review
    direct_with_declaration: int = 0  # of those, the ones that add a declaration
    direct_exempt: int = 0
    direct_recent: list = field(default_factory=list)  # the last RECENT_DIRECT demanding ones
    truncated: bool = False


def branch_coverage(ref: str, evidence_root: str, config_path: str, repo: Path,
                    limit: int = MAX_COMMITS, label: str | None = None) -> Coverage:
    """The coverage of `ref`'s first-parent history, or why it could not be computed."""
    out = Coverage(ref=label or ref)
    try:
        _compute(out, ref, evidence_root, config_path, Path(repo), limit)
    except (gitctx.GitError, gate.GateFailure, OSError, ValueError) as exc:
        out.error = str(exc)
    return out


def _compute(out: Coverage, ref: str, evidence_root: str, config_path: str, repo: Path, limit: int) -> None:
    shallow = gitctx.run_git(["rev-parse", "--is-shallow-repository"], repo)
    if shallow.returncode == 0 and shallow.stdout.strip() == "true":
        raise gitctx.GitError("the clone is shallow, so the history of the branch is incomplete")
    tip = gitctx.resolve_commit(ref, repo)
    out.tip = tip
    declarations, _unreadable = report.read_tree(tip, evidence_root, repo)
    out.declarations = len(declarations)
    dated = [d["date"] for d in declarations if d["date"]]
    if not dated:
        raise ValueError("no dated declaration at the tip of the branch, so there is no period to cover")
    out.since = min(dated).date()
    heads = {d["head"].lower() for d in declarations if _HEX.match(d["head"].lower())}
    config, out.policy_note = gate.load_config_at(tip, config_path, repo)
    out.config_path = config_path
    out.policy_default = not gitctx.path_exists(tip, config_path, repo)
    out.required = bool(config["gate"].get("required", True))
    if config.get("criticality_level") == "A" and not out.required:
        raise ValueError("the policy at the tip declares Level A with gate.required=false, which the gate refuses")
    root = gitctx.repo_root(repo)
    history = _history(tip, repo, limit + 1)
    if len(history) > limit:
        out.truncated = True
        history = history[:limit]
    for oid, parents, when, subject in history:
        if not parents or when is None:
            continue  # a root commit, or a date git could not print: nothing to compare
        first = parents[0]
        is_merge = len(parents) >= 2
        if when.date() < out.since:
            if is_merge:
                out.before += 1
            continue
        status = gitctx.changed_status(first, oid, repo)
        new_paths, mutations, ordinary = gate.classify_changes(status, evidence_root, first, oid, repo)
        ctx = gate.GateContext(
            root=root, evidence_root=evidence_root, config_path=config_path,
            base_oid=first, head_oid=oid, merge_base=first, config=config, policy_note=out.policy_note,
            status=status, new_paths=new_paths, mutations=mutations, ordinary=ordinary,
        )
        requirement = gate.classify_requirement(ctx)
        row = {
            "oid": oid, "date": when, "subject": subject, "demanding": len(requirement.demanding),
            "mutations": len(mutations), "code": requirement.code, "declares": bool(new_paths),
        }
        if is_merge:
            if mutations:
                out.mutated += 1
            if requirement.code == "all_exempt":
                out.exempt += 1
                continue
            out.merges += 1
            if _anchored(parents, heads, repo):
                out.covered += 1
            elif out.required:
                out.uncovered.append(row)
        else:
            if requirement.code == "all_exempt":
                out.direct_exempt += 1
                continue
            out.direct_demanding += 1
            if new_paths:
                out.direct_with_declaration += 1
            if len(out.direct_recent) < RECENT_DIRECT:
                out.direct_recent.append(row)


def _history(tip: str, repo: Path, n: int) -> list[tuple[str, list[str], datetime | None, str]]:
    """The first-parent history from the tip, newest first, at most `n` commits.

    One git call. Records are NUL separated and fields unit separated: a subject
    is free text and may hold anything git accepts, which excludes NUL.
    """
    r = gitctx.run_git(
        ["log", "--first-parent", f"-n{n}", "-z", "--format=%H%x1f%P%x1f%cI%x1f%s", tip], repo, text=False,
    )
    if r.returncode != 0:
        raise gitctx.GitError(f"git log {tip[:7]}: {r.stderr.decode('utf-8', 'replace').strip() or 'failed'}")
    out = []
    for record in r.stdout.decode("utf-8", "replace").split("\0"):
        parts = record.split("\x1f", 3)
        if len(parts) < 4:
            continue
        oid, parents, when, subject = parts
        stamp, _naive = report.parse_created(when)
        out.append((oid, parents.split(), stamp, subject))
    return out


def _anchored(parents: list[str], heads: set[str], repo: Path) -> bool:
    """Whether some declared head is one of the commits the merge brought in.

    The commits of the PR are those reachable from the second parent (and any
    further one) and not from the first. The schema admits abbreviated heads,
    so the comparison is by hexadecimal prefix against canonical oids.
    """
    if not heads:
        return False
    r = gitctx.run_git(["rev-list", *parents[1:], f"^{parents[0]}"], repo)
    if r.returncode != 0:
        raise gitctx.GitError(f"git rev-list: {r.stderr.strip() or 'failed'}")
    commits = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    return any(commit.startswith(head) for commit in commits for head in heads)

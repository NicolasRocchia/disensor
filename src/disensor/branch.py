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

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from . import gate, gitctx, report
from .rules import validate_artifact

# The walk never reads more than this many first-parent commits. One more is
# asked for, so "truncated" means there were more, not exactly this many.
MAX_COMMITS = 2000
RECENT_DIRECT = 10
_HEX = re.compile(r"^[0-9a-f]{7,40}$")
# git's empty tree: what a root commit is diffed against.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@dataclass
class Coverage:
    ref: str                          # what the caller named: a branch, HEAD, the base of a PR
    tip: str = ""                     # canonical oid, once resolved
    error: str | None = None          # why nothing was computed; the render never shows a made-up zero
    since: date | None = None         # committer date of the commit that opened the period, for display
    since_oid: str = ""               # the first-parent commit that introduced the first valid declaration
    declarations: int = 0             # valid artifacts at the tip: the only evidence that covers
    invalid: int = 0                  # files under the evidence directory at the tip that do not validate
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
    artifacts, out.invalid = _valid_declarations(tip, evidence_root, repo)
    out.declarations = len(artifacts)
    if not artifacts:
        raise ValueError("no valid declaration at the tip of the branch, so there is no period to cover")
    by_head = _by_canonical_head(artifacts, repo)
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
    # The period opens at the commit that brought the first valid declaration
    # into the branch, in the order of the branch: what a declaration says
    # about its own date decides nothing here, so a wrong or future
    # `created_at` cannot push merges out of the period.
    opened = _opening_commit(tip, evidence_root, repo, history)
    if opened is None:
        raise ValueError("no commit of the walked history introduces a valid declaration, so the period has no start")
    out.since_oid = opened
    opened_at = next(i for i, entry in enumerate(history) if entry[0] == opened)
    for i, (oid, parents, when, subject) in enumerate(history):
        is_merge = len(parents) >= 2
        if i > opened_at:  # older than the opening commit, in the order of the branch
            if is_merge:
                out.before += 1
            continue
        if when is None:
            continue  # a date git could not print: the row cannot be shown
        if oid == opened:
            out.since = when.date()
        first = parents[0] if parents else EMPTY_TREE
        if is_merge:
            _judge_merge(out, oid, parents, when, subject, by_head, config, evidence_root, config_path, root, repo)
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
            "mutations": len(mutations), "code": requirement.code, "reason": "",
            "declares": any(_valid_at(oid, path, repo) for path in new_paths),
        }
        if requirement.code == "all_exempt":
            out.direct_exempt += 1
            continue
        out.direct_demanding += 1
        if row["declares"]:
            out.direct_with_declaration += 1
        if len(out.direct_recent) < RECENT_DIRECT:
            out.direct_recent.append(row)


def _judge_merge(out: Coverage, oid: str, parents: list[str], when: datetime, subject: str,
                 by_head: dict, config: dict, evidence_root: str, config_path: str, root: Path, repo: Path) -> None:
    """One merge, judged as the gate judged the PR it closed: base is the first
    parent, head is the second, the range is their merge base to the head, and
    a declaration covers the merge only if it is admissible for it (G5), covers
    every demanding path in its final state (G6) and witnessed the integrated
    tree (G7). Anchoring alone is not enough: a plan declaration anchored to a
    PR whose paths accept only a diff review is one the gate rejects, and the
    board would have called it covered.
    """
    if len(parents) > 2:
        # An octopus merge closes several branches at once and the gate judges
        # one PR of one branch: there is no single range to evaluate, and
        # judging only the second parent would leave the others out of G6 and
        # G7 while calling the merge covered. Fail closed, visibly.
        out.merges += 1
        if out.required:
            out.uncovered.append({
                "oid": oid, "date": when, "subject": subject, "demanding": 0, "mutations": 0, "code": "octopus",
                "reason": (f"merge de {len(parents)} padres: el gate juzga un PR de una rama y este panel no "
                           f"evalúa un octopus; se lista como no cubierto"),
                "declares": False,
            })
        return
    head = parents[1]
    try:
        mb = gitctx.merge_base(parents[0], head, repo)
    except gitctx.GitError as exc:
        out.merges += 1
        if out.required:
            out.uncovered.append({"oid": oid, "date": when, "subject": subject, "demanding": 0, "mutations": 0,
                                  "code": "no_merge_base", "reason": str(exc), "declares": False})
        return
    status = gitctx.changed_status(mb, head, repo)
    new_paths, mutations, ordinary = gate.classify_changes(status, evidence_root, mb, head, repo)
    ctx = gate.GateContext(
        root=root, evidence_root=evidence_root, config_path=config_path,
        base_oid=parents[0], head_oid=head, merge_base=mb, config=config, policy_note=out.policy_note,
        status=status, new_paths=new_paths, mutations=mutations, ordinary=ordinary,
    )
    requirement = gate.classify_requirement(ctx)
    if mutations:
        out.mutated += 1
    if requirement.code == "all_exempt":
        out.exempt += 1
        return
    out.merges += 1
    # The candidates are the declarations anchored inside the range; each one
    # then goes through the gate's own admissibility and coverage checks.
    r = gitctx.run_git(["rev-list", head, f"^{mb}"], repo)
    if r.returncode != 0:
        raise gitctx.GitError(f"git rev-list: {r.stderr.strip() or 'failed'}")
    inside = {line.strip() for line in r.stdout.splitlines() if line.strip()}
    candidates = [gate.Artifact(path=name, data=raw)
                  for canonical, entries in by_head.items() if canonical in inside for name, raw in entries]
    for a in candidates:
        gate.check_range_membership(a, mb, head, repo)
    errors, _notes, _demanding = gate.evaluate_coverage(candidates, ordinary, config, evidence_root, config_path)
    if requirement.code == "no_common_gate":
        errors = [requirement.reason] + errors
    if not errors:
        out.covered += 1
    elif out.required:
        out.uncovered.append({
            "oid": oid, "date": when, "subject": subject, "demanding": len(requirement.demanding),
            "mutations": len(mutations), "code": requirement.code, "reason": errors[0],
            "declares": bool(candidates),
        })


def _valid_declarations(tip: str, evidence_root: str, repo: Path) -> tuple[list[tuple[str, dict]], int]:
    """The artifacts at the tip that validate, as (name, raw) pairs, and how many files did not.

    The report reads without validating, on purpose: a file that is not the
    shape of a declaration is listed, and the rest goes on. Coverage is a
    different question. A committed file with a `head_commit` and nothing else
    of a declaration would cover a merge it never reviewed, so only what passes
    the schema and the rules, the same check the gate applies, counts as
    evidence here. The number of files left out travels to the panel.
    """
    depth = len(PurePosixPath(evidence_root).parts) + 1
    valid: list[tuple[str, dict]] = []
    invalid = 0
    for path in gitctx.list_tree(tip, evidence_root, repo):
        pure = PurePosixPath(path)
        if not path.endswith(".json") or len(pure.parts) != depth:
            continue
        try:
            raw = json.loads(gitctx.show_text(tip, path, repo))
        except (gitctx.GitError, UnicodeDecodeError, ValueError):
            invalid += 1
            continue
        if not isinstance(raw, dict) or validate_artifact(raw):
            invalid += 1
            continue
        valid.append((pure.name, raw))
    return valid, invalid


def _opening_commit(tip: str, evidence_root: str, repo: Path, history: list) -> str | None:
    """The oldest first-parent commit, within the walked history, that added a
    file under the evidence directory which validates as a declaration.

    One git call lists the candidates (commits that added something there);
    each is confirmed from the oldest up, so a stray file does not open the
    period. None when no candidate in the walked history qualifies.
    """
    r = gitctx.run_git(
        ["--literal-pathspecs", "log", "--first-parent", "--format=%H", "--diff-filter=A", tip, "--", evidence_root],
        repo,
    )
    if r.returncode != 0:
        raise gitctx.GitError(f"git log {tip[:7]} -- {evidence_root}: {r.stderr.strip() or 'failed'}")
    parents_of = {oid: parents for oid, parents, _, _ in history}
    for oid in reversed([line.strip() for line in r.stdout.splitlines() if line.strip()]):
        if oid not in parents_of:
            continue  # beyond the walked history
        first = parents_of[oid][0] if parents_of[oid] else EMPTY_TREE
        status = gitctx.changed_status(first, oid, repo)
        new_paths, _mutations, _ordinary = gate.classify_changes(status, evidence_root, first, oid, repo)
        if any(_valid_at(oid, path, repo) for path in new_paths):
            return oid
    return None


def _valid_at(rev: str, path: str, repo: Path) -> bool:
    """Whether the file at `path` in `rev` is an artifact that validates."""
    try:
        raw = json.loads(gitctx.show_text(rev, path, repo))
    except (gitctx.GitError, UnicodeDecodeError, ValueError):
        return False
    return isinstance(raw, dict) and not validate_artifact(raw)


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


def _by_canonical_head(artifacts: list[tuple[str, dict]], repo: Path) -> dict[str, list[tuple[str, dict]]]:
    """The valid artifacts keyed by the canonical oid of their declared head.

    The schema admits abbreviated heads. A prefix comparison would let a later
    commit that shares a once-unique prefix cover a merge it never reviewed,
    so each head is resolved by git, the way G5 resolves it; one that git
    cannot resolve, or finds ambiguous, anchors nothing in this repository.
    """
    out: dict[str, list[tuple[str, dict]]] = {}
    for name, raw in artifacts:
        declared = str((raw.get("event") or {}).get("head_commit") or "").lower()
        if not _HEX.match(declared):
            continue
        try:
            out.setdefault(gitctx.resolve_commit(declared, repo), []).append((name, raw))
        except gitctx.GitError:
            continue
    return out

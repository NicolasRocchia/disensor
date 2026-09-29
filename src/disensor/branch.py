"""What the branch shows next to the declarations.

For whoever coordinates: of the merges a branch received since the commit that
brought its first valid declaration, which ones demanded a review under the
policy at the tip and carry no declaration the gate would have admitted. It
measures declarations, never gate runs: the repository keeps no verdict of any
run, and a declaration anchored to a PR does not prove the gate ran on it.
Everything is read from git objects, never from the working tree, so an
uncommitted file cannot manufacture coverage or move the period.

Each merge is judged the way the gate judged the PR it closed, with the gate's
own functions over the same context: first parent as base, second parent as
head, the range from their merge base, the policy of the tip. Whether a review
was demanded comes from `classify_requirement`; each declaration the PR added
goes through `judge_artifact` (G2 to G5, G8) and coverage through
`evaluate_coverage` (G1, G6, G7). The one check left out is G9, the current
schema version: a superseded schema was the one in force when an old merge
happened, and G9 exists to keep new evidence current, not to rewrite what the
history looks like. They are still today's gates: a merge older than one of
them can show up uncovered although the gate of its day approved it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from . import gate, gitctx, report
from .rules import validate_artifact

# The walk never reads more than this many first-parent commits. One more is
# asked for, so "truncated" means there were more, not exactly this many.
MAX_COMMITS = 2000
RECENT_DIRECT = 10
# git's empty tree: what a root commit is diffed against.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@dataclass
class Coverage:
    ref: str                          # what the caller named: a branch, HEAD, the base of a PR
    tip: str = ""                     # canonical oid, once resolved
    error: str | None = None          # why nothing was computed; the render never shows a made-up zero
    since: date | None = None         # committer date of the commit that opened the period, for display
    since_oid: str = ""               # the first-parent commit that introduced the first valid declaration
    declarations: int = 0             # valid artifacts at the tip
    invalid: int = 0                  # files under the evidence directory at the tip that do not validate
    policy_note: str = ""             # the gate's own note, data for the record
    config_path: str = ""
    policy_default: bool = False      # no configuration at the tip: the gate's safe defaults applied
    required: bool = True             # gate.required at the tip
    merges: int = 0                   # merges in the period that demanded a review
    covered: int = 0
    uncovered: list = field(default_factory=list)      # rows of merges without an admissible declaration
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
    blobs: dict[str, str | None] = {}  # blob oid -> event key of a historical artifact, shared across merges
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
        if is_merge:
            _judge_merge(out, oid, parents, when, subject, config, evidence_root, config_path, root, repo, blobs)
            continue
        first = parents[0] if parents else EMPTY_TREE
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
                 config: dict, evidence_root: str, config_path: str, root: Path, repo: Path,
                 blobs: dict[str, str | None]) -> None:
    """One merge, judged as the gate judged the PR it closed.

    Base is the first parent, head the second, the range their merge base to
    the head. The declarations the PR added go through the gate's own
    per-artifact checks (G2 to G5, G8; not G9, see the module docstring) and
    its coverage evaluation (G1, G6, G7); a mutation of evidence already there
    fails the merge as it fails the PR (G8). The first reason travels to the
    row, and a declaration the gate rejects names its own error, which is
    what whoever coordinates needs to read.
    """
    def uncovered(code: str, reason: str, demanding: int = 0, mutations: int = 0, declares: bool = False) -> None:
        out.merges += 1
        if out.required:
            out.uncovered.append({"oid": oid, "date": when, "subject": subject, "demanding": demanding,
                                  "mutations": mutations, "code": code, "reason": reason, "declares": declares})

    if len(parents) > 2:
        # An octopus merge closes several branches at once and the gate judges
        # one PR of one branch: there is no single range to evaluate, and
        # judging only the second parent would leave the others out of G6 and
        # G7 while calling the merge covered. Fail closed, visibly.
        uncovered("octopus", f"merge de {len(parents)} padres: el gate juzga un PR de una rama y este panel no "
                             f"evalúa un octopus; se lista como no cubierto")
        return
    head = parents[1]
    try:
        mb = gitctx.merge_base(parents[0], head, repo)
    except gitctx.GitError as exc:
        uncovered("no_merge_base", str(exc))
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
        uncovered(requirement.code, f"[G8] `{mutations[0]}`: evidence already present at the base of the PR was "
                                    f"modified, deleted or renamed; a declaration is written once",
                  len(requirement.demanding), len(mutations), bool(new_paths))
        return
    if requirement.code == "all_exempt":
        out.exempt += 1
        return
    # Ids taken from the target as it was when the PR merged, its first parent,
    # like the gate reads them from the target tip and not from the merge base:
    # an id recorded on the target after the branch was created is just as
    # taken, and reading only the merge base would let an old branch reuse it.
    historical, unreadable = _historical_ids(parents[0], evidence_root, repo, blobs)
    errors: list[str] = []
    if unreadable:
        errors.append(f"[G8] historical evidence `{unreadable[0]}` cannot be read, so the uniqueness of "
                      f"event ids cannot be guaranteed against it")
    artifacts: list[gate.Artifact] = []
    for path in new_paths:
        try:
            data = json.loads(gitctx.show_text(head, path, repo))
        except (json.JSONDecodeError, gitctx.GitError, UnicodeDecodeError) as exc:
            errors.append(f"`{path}`: invalid JSON ({exc})")
            continue
        schema_errors = validate_artifact(data) if isinstance(data, dict) else ["the artifact is not an object"]
        artifact = gate.Artifact(path=path, data=data if isinstance(data, dict) else {}, errors=schema_errors)
        gate.judge_artifact(artifact, path, config, historical, mb, head, repo, current_schema=False)
        artifacts.append(artifact)
    usable = [a for a in artifacts if a.valid]
    coverage_errors, _notes, _demanding = gate.evaluate_coverage(usable, ordinary, config, evidence_root, config_path)
    if requirement.code == "no_common_gate":
        errors.insert(0, requirement.reason)
    rejected = [a for a in artifacts if not a.valid]
    if coverage_errors and rejected:
        # The PR did bring a declaration and the gate would have refused it:
        # its own error says why better than "no valid declaration" does.
        errors.append(f"`{rejected[0].path}`: {rejected[0].errors[0]}")
    errors.extend(coverage_errors)
    if not errors:
        out.merges += 1
        out.covered += 1
        return
    uncovered(requirement.code, errors[0], len(requirement.demanding), 0, bool(artifacts))


def _historical_ids(rev: str, evidence_root: str, repo: Path, blobs: dict[str, str | None]) -> tuple[set[str], list[str]]:
    """The event ids already recorded under the evidence directory at `rev`, as the gate reads them.

    File stems and declared ids both count, like in the gate. Blob contents
    are cached by blob oid across merges: the same historical files come up
    at every merge base, and reading them once is enough. Files that cannot
    be read are returned apart, because the gate treats them as an error.
    """
    r = gitctx.run_git(["--literal-pathspecs", "ls-tree", "-r", "-z", "--full-tree", rev, "--", evidence_root], repo)
    if r.returncode != 0:
        raise gitctx.GitError(f"git ls-tree {rev[:7]} -- {evidence_root}: {r.stderr.strip() or 'failed'}")
    ids: set[str] = set()
    unreadable: list[str] = []
    for entry in r.stdout.split("\0"):
        if not entry:
            continue
        meta, _, name = entry.partition("\t")
        parts = meta.split()
        if len(parts) < 3 or not name.endswith(".json"):
            continue
        blob = parts[2]
        ids.add(gate.event_key(PurePosixPath(name).stem))
        if blob not in blobs:
            try:
                past = json.loads(gitctx.show_text(rev, name, repo))
                event = past.get("event") if isinstance(past, dict) else None
                past_id = event.get("event_id") if isinstance(event, dict) else None
                blobs[blob] = gate.event_key(past_id) if isinstance(past_id, str) and past_id.strip() else None
            except (json.JSONDecodeError, gitctx.GitError, UnicodeDecodeError):
                blobs[blob] = "?"
        key = blobs[blob]
        if key == "?":
            unreadable.append(name)
        elif key:
            ids.add(key)
    return ids, unreadable


def _valid_declarations(tip: str, evidence_root: str, repo: Path) -> tuple[list[tuple[str, dict]], int]:
    """The artifacts at the tip that validate, as (name, raw) pairs, and how many files did not.

    The report reads without validating, on purpose: a file that is not the
    shape of a declaration is listed, and the rest goes on. Coverage is a
    different question: only what passes the schema and the rules, the same
    check the gate applies, opens the period or counts as evidence here. The
    number of files left out travels to the panel.
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

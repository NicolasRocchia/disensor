"""CI gate: validates the residue declarations a PR adds and applies policy.

Everything the gate decides comes from git objects in the range
`merge_base..head`, never from the working tree and never from the whole tree.
That is the difference between asking "does this repository contain a valid
declaration" and asking "did this PR declare what it is merging", which is the
only question worth a green check.

Per artifact (on top of R0 to R10 of rules.py):
  G2: the artifact level matches the level declared in the repository.
  G3: Level A blocked while governance is not validated (section 3.1).
  G4: confinement policy per level (section 10).
  G5: the reviewed commit belongs to this PR (descendant of the merge base and
      ancestor of the head), and for a diff gate the reviewed base is the merge
      base: a diff review identifies the pair, not a loose head.

Per PR:
  G1: at least one valid declaration added by this PR.
  G6: coverage. Every changed ordinary path is covered by an artifact whose gate
      the scope policy accepts for it and that qualifies for it, meaning the path
      did not change between the reviewed commit and the head.
  G7: integration witness. Coverage alone is satisfiable by a mosaic: two side
      branches reviewed separately and merged without reviewing the integration,
      where each artifact qualifies for its own path and nobody ever saw the
      combined tree. So one artifact must qualify for every changed ordinary path.
  G8: evidence is append-only, and event ids are unique against history.

The honest limit inherited from the protocol has not moved: the machine detects
the empty field and the generic marker, not the false declaration.
"""
from __future__ import annotations

import json
import os
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import gitctx
from .render import MARKER, render_comment
from .rules import load_schema, validate_artifact
from .scope import DEFAULT_SCOPE, ScopeError, accepts_for, floor_patterns, validate_scope

DEFAULT_CONFIG = {
    "criticality_level": "B",
    "level_A_enabled": False,
    "gate": {
        "required": True,
        "level_A_accepted_confinement": ["permissions", "sandbox"],
        "warn_unverified_confinement": True,
        "scope": DEFAULT_SCOPE,
    },
}

V01_CONFIG_KEYS = {"nivel_criticidad", "nivel_A_habilitado"}

KNOWN_CONFIG_KEYS = {"criticality_level", "level_A_enabled", "gate"}
KNOWN_GATE_KEYS = {"required", "level_A_accepted_confinement", "warn_unverified_confinement", "scope"}


class GateFailure(Exception):
    """The gate cannot reach a verdict, so it refuses to give a green check."""


def event_key(raw) -> str:
    """Comparable identity of an event.

    The same UUID has many textual forms (upper case, no dashes, braces, a urn:
    prefix, a trailing space) and the schema declares `format: uuid` without the
    validator asserting it, so comparing raw strings lets a new artifact reuse a
    historical id just by writing it differently.
    """
    text = str(raw).strip()
    # `uuid.UUID` accepts `urn:uuid:` in lower case only, while both the URI
    # scheme and the URN namespace are case insensitive (RFC 3986, RFC 8141), so
    # `URN:UUID:<id>` is the same identity and used to fall through to the
    # fallback with a different key.
    if text[:9].casefold() == "urn:uuid:":
        text = text[9:]
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError, TypeError):
        # Not a UUID at all, which the schema should not allow. Casefolding errs
        # towards collision, and a false collision blocks a PR while a missed one
        # lets an id be reused: between the two, the gate fails closed.
        return text.casefold()


@dataclass
class Artifact:
    path: str
    data: dict
    errors: list[str] = field(default_factory=list)
    changed_after: set[str] = field(default_factory=set)
    in_range: bool = False
    range_reason: str = ""

    @property
    def event(self) -> dict:
        return self.data.get("event", {})

    @property
    def gate(self) -> str:
        return self.event.get("gate", "")

    @property
    def event_id(self) -> str:
        return self.event.get("event_id", "")

    @property
    def valid(self) -> bool:
        return not self.errors

    def qualifies_for(self, path: str) -> bool:
        """The reviewer saw this path in its final state."""
        return self.in_range and path not in self.changed_after


def canonical_repo_path(raw: str, root: Path, label: str) -> str:
    """A repo-relative path that cannot escape the repository.

    `directory: "."` would put the whole repository inside the exempt zone and
    no file would ever count as code, so it is rejected outright.
    """
    if raw is None or not str(raw).strip():
        raise GateFailure(f"{label}: empty path")
    text = str(raw).replace("\\", "/").strip()
    if ":" in text:
        # Drive letters, and git pathspec magic such as `:(top)`, which would make
        # the path mean something other than a plain repository-relative path.
        raise GateFailure(f"{label}: '{raw}' must be a plain repository-relative path")
    pure = PurePosixPath(text)
    if pure.is_absolute():
        raise GateFailure(f"{label}: '{raw}' must be relative to the repository root")
    parts = [p for p in pure.parts if p != "."]
    if any(p == ".." for p in parts):
        raise GateFailure(f"{label}: '{raw}' must not escape the repository")
    if not parts:
        raise GateFailure(
            f"{label}: '{raw}' resolves to the repository root. The evidence directory has to be "
            "a real subdirectory, otherwise every file in the repository falls inside it and "
            "nothing counts as code."
        )
    return "/".join(parts)


def validate_config_shape(config: dict, where: str) -> None:
    old = V01_CONFIG_KEYS & set(config)
    if old:
        raise GateFailure(
            f"{where}: v0.1 Spanish keys found ({', '.join(sorted(old))}). "
            "disensor 0.2 renamed the configuration to English: nivel_criticidad -> "
            "criticality_level, nivel_A_habilitado -> level_A_enabled. "
            "Failing loudly instead of silently applying defaults."
        )
    unknown = set(config) - KNOWN_CONFIG_KEYS
    if unknown:
        raise GateFailure(f"{where}: unknown keys ({', '.join(sorted(unknown))})")
    gate = config.get("gate", {})
    if not isinstance(gate, dict):
        raise GateFailure(f"{where}: 'gate' must be an object")
    unknown_gate = set(gate) - KNOWN_GATE_KEYS
    if unknown_gate:
        raise GateFailure(f"{where}: unknown keys under 'gate' ({', '.join(sorted(unknown_gate))})")
    if "criticality_level" in config and config["criticality_level"] not in ("A", "B", "C"):
        raise GateFailure(f"{where}: criticality_level must be A, B or C")
    # Types are checked one by one and not merely "present": a string
    # `level_A_enabled: "false"` is truthy, so an invalid configuration would
    # switch governance on instead of failing closed, and a string in
    # `level_A_accepted_confinement` turns the `in` check into a substring search.
    for key, kind, kind_name in (
        ("level_A_enabled", bool, "a boolean"),
    ):
        if key in config and not isinstance(config[key], kind):
            raise GateFailure(f"{where}: {key} must be {kind_name}")
    for key, kind, kind_name in (
        ("required", bool, "a boolean"),
        ("warn_unverified_confinement", bool, "a boolean"),
        ("level_A_accepted_confinement", list, "a list"),
    ):
        if key in gate and not isinstance(gate[key], kind):
            raise GateFailure(f"{where}: gate.{key} must be {kind_name}")
    for mode in gate.get("level_A_accepted_confinement", []):
        if not isinstance(mode, str):
            raise GateFailure(f"{where}: gate.level_A_accepted_confinement must hold strings")
    try:
        validate_scope(gate.get("scope", DEFAULT_SCOPE))
    except ScopeError as exc:
        raise GateFailure(f"{where}: {exc}") from exc


def merge_config(raw: dict) -> dict:
    combined = {k: v for k, v in DEFAULT_CONFIG.items() if k != "gate"}
    combined.update({k: v for k, v in raw.items() if k != "gate"})
    gate = dict(DEFAULT_CONFIG["gate"])
    gate.update(raw.get("gate", {}))
    combined["gate"] = gate
    return combined


def load_config_at(rev: str, config_path: str, repo_dir: Path) -> tuple[dict, str]:
    """Policy as of the base of the PR.

    Reading the policy from the base is what makes a PR that changes the policy
    be judged by the previous one. It also dissolves the deadlock of the obvious
    alternative, where the PR that relaxes the configuration is rejected by the
    very rule it is trying to change, leaving no legitimate transition.
    """
    if not gitctx.path_exists(rev, config_path, repo_dir):
        return merge_config({}), (
            f"no {config_path} at the base of the PR: safe defaults apply "
            "(gate required, level B, everything demands a diff review)"
        )
    raw = json.loads(gitctx.show_text(rev, config_path, repo_dir))
    if not isinstance(raw, dict):
        raise GateFailure(f"{config_path} at the base of the PR is not an object")
    validate_config_shape(raw, f"{config_path} (base of the PR)")
    return merge_config(raw), f"policy read from {config_path} at the base of the PR"


def pr_range(base: str | None, head: str | None) -> tuple[str | None, str | None]:
    if base and head:
        return base, head
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and Path(event_path).exists():
        with open(event_path, encoding="utf-8") as f:
            event = json.load(f)
        pr = event.get("pull_request") or {}
        return (
            base or (pr.get("base") or {}).get("sha"),
            head or (pr.get("head") or {}).get("sha"),
        )
    return base, head


def classify_changes(
    status: dict[str, str], evidence_root: str, merge_base: str, head: str, repo_dir: Path,
) -> tuple[list[str], list[str], list[str]]:
    """Split the changed paths into new artifacts, evidence mutations and code.

    Anything added under the evidence directory that is not an immediate regular
    `.json` blob is classified as an ordinary change. Otherwise the evidence
    directory becomes a place to park code where the gate does not look.
    """
    new_artifacts: list[str] = []
    mutations: list[str] = []
    ordinary: list[str] = []
    prefix = evidence_root + "/"
    for path in sorted(status):
        if not path.startswith(prefix):
            ordinary.append(path)
            continue
        if gitctx.path_exists(merge_base, path, repo_dir):
            mutations.append(path)
            continue
        relative = path[len(prefix):]
        entry = gitctx.tree_entry(head, path, repo_dir)
        is_immediate_json = "/" not in relative and relative.endswith(".json")
        is_regular_blob = entry is not None and entry[1] == "blob" and entry[0] in ("100644", "100755")
        if is_immediate_json and is_regular_blob:
            new_artifacts.append(path)
        else:
            ordinary.append(path)
    return new_artifacts, mutations, ordinary


def check_range_membership(a: Artifact, merge_base: str, head: str, repo_dir: Path) -> None:
    """G5, for every gate and not only for diff.

    Without this a plan or an architecture artifact can qualify while pointing at
    a side commit, or at one that has nothing to do with this PR.
    """
    declared = a.event.get("head_commit", "")
    try:
        reviewed_head = gitctx.resolve_commit(declared, repo_dir)
    except gitctx.GitError:
        a.range_reason = f"[G5] reviewed commit {declared} does not resolve in this repository"
        return
    if not gitctx.is_ancestor(merge_base, reviewed_head, repo_dir) or not gitctx.is_ancestor(reviewed_head, head, repo_dir):
        a.range_reason = f"[G5] reviewed commit {declared} is not part of this PR"
        return
    if a.gate == "diff":
        declared_base = a.event.get("base_commit")
        if not declared_base:
            a.range_reason = (
                "[G5] diff gate without base_commit: a diff review identifies the pair "
                "(reviewed base, reviewed head), not a loose head"
            )
            return
        try:
            reviewed_base = gitctx.resolve_commit(declared_base, repo_dir)
        except gitctx.GitError:
            a.range_reason = f"[G5] base_commit {declared_base} does not resolve in this repository"
            return
        if reviewed_base != merge_base:
            a.range_reason = (
                f"[G5] the reviewed base ({declared_base}) is not the base of this PR "
                f"({merge_base[:7]}): the diff that is going to be merged is not the one reviewed"
            )
            return
    a.changed_after = gitctx.changed_paths(reviewed_head, head, repo_dir)
    a.in_range = True


def evaluate_coverage(
    artifacts: list[Artifact], ordinary: list[str], config: dict, evidence_root: str, config_path: str,
) -> tuple[list[str], list[str], list[str]]:
    """G1, G6 and G7: every path covered, and somebody saw the whole final tree."""
    errors: list[str] = []
    notes: list[str] = []
    scope = config["gate"].get("scope", DEFAULT_SCOPE)
    floor = floor_patterns(config_path, evidence_root)
    usable = [a for a in artifacts if a.valid]

    accepts: dict[str, list[str]] = {}
    for path in ordinary:
        allowed, rule = accepts_for(path, scope, floor)
        accepts[path] = allowed
        notes.append(f"`{path}`: {', '.join(allowed) if allowed else 'exempt'} (rule `{rule}`)")

    demanding = [p for p in ordinary if accepts[p]]
    if not demanding:
        # Every changed path is exempt by a policy someone wrote in the base on
        # purpose. Demanding a declaration anyway would contradict the exemption.
        return errors, notes, demanding

    if not usable:
        errors.append(
            "[G1] this PR changes paths that require review and adds no valid residue "
            "declaration. The declaration lists concrete residue or says explicitly that "
            "there was none; an empty field is not a declaration."
        )
        return errors, notes, demanding

    for path in demanding:
        if not any(a.gate in accepts[path] and a.qualifies_for(path) for a in usable):
            stale = [a for a in usable if a.gate in accepts[path] and a.in_range and path in a.changed_after]
            if stale:
                errors.append(
                    f"[G6] `{path}` changed after the review that claims to cover it "
                    f"({', '.join(a.event_id[:8] for a in stale)}): the declaration is stale"
                )
            else:
                errors.append(
                    f"[G6] `{path}` is not covered by any declaration of this PR "
                    f"(accepted gates: {', '.join(accepts[path])})"
                )

    required_gates = set(accepts[demanding[0]])
    for path in demanding[1:]:
        required_gates &= set(accepts[path])
    if not required_gates:
        errors.append(
            "[G7] the changed paths admit no common gate, so no single review can witness "
            "the integrated tree. Split the PR or widen the scope policy."
        )
        return errors, notes, demanding

    witnesses = [
        a for a in usable
        if a.gate in required_gates and a.in_range and not (set(ordinary) & a.changed_after)
    ]
    if not witnesses:
        errors.append(
            "[G7] no declaration saw the final tree of this PR. Coverage path by path is not "
            "enough: two side branches reviewed separately and then merged cover every path "
            "between them while nobody reviewed the integration. One review "
            f"({' or '.join(sorted(required_gates))}) has to reach the head with no changed path "
            "left behind it."
        )
    return errors, notes, demanding


def post_comment(body: str) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    pr = None
    if event_path and Path(event_path).exists():
        with open(event_path, encoding="utf-8") as f:
            pr = (json.load(f).get("pull_request") or {}).get("number")
    if not (token and repo and pr):
        return "no token, repository or PR number: comment not posted"
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "disensor-gate",
    }
    try:
        req = urllib.request.Request(
            f"{api}/repos/{repo}/issues/{pr}/comments?per_page=100", headers=headers
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            comments = json.load(resp)
        existing = next(
            (c for c in comments
             if MARKER in (c.get("body") or "") and (c.get("user") or {}).get("type") == "Bot"),
            None,
        )
        data = json.dumps({"body": body}).encode("utf-8")
        if existing:
            req = urllib.request.Request(
                f"{api}/repos/{repo}/issues/comments/{existing['id']}",
                data=data, headers=headers, method="PATCH",
            )
        else:
            req = urllib.request.Request(
                f"{api}/repos/{repo}/issues/{pr}/comments",
                data=data, headers=headers, method="POST",
            )
        with urllib.request.urlopen(req, timeout=30):
            pass
        return "comment updated" if existing else "comment posted"
    except Exception as exc:  # the comment is best effort; the summary is normative
        return f"could not post the comment: {exc}"


def write_summary(body: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(body + "\n")


def run_gate(directory: Path | str, config_path: Path | str, base: str | None,
             head: str | None, repo_dir: Path, post: bool = True) -> int:
    try:
        return _run_gate(directory, config_path, base, head, repo_dir, post)
    except (GateFailure, gitctx.GitError, ScopeError, json.JSONDecodeError) as exc:
        body = (
            f"{MARKER}\n## Residue declaration\n\n**The gate could not reach a verdict.**\n\n- {exc}\n\n"
            "A compliance control that cannot decide does not pass: it fails."
        )
        write_summary(body)
        print(body)
        print(f"\n[gate] FAILED: {exc}")
        return 1


def _run_gate(directory, config_path, base, head, repo_dir: Path, post: bool) -> int:
    repo_dir = Path(repo_dir)
    root = gitctx.repo_root(repo_dir)
    evidence_root = canonical_repo_path(directory, root, "--directory")
    cfg_path = canonical_repo_path(config_path, root, "--config")

    # Fail closed, unconditionally: the range cannot depend on a policy that is
    # located with the range itself.
    base, head = pr_range(base, head)
    if not base or not head:
        raise GateFailure(
            "the PR range is missing. The gate runs on pull_request events, or with explicit "
            "--base and --head. Without a range there is nothing to decide, and a control that "
            "cannot decide does not pass."
        )
    base_oid = gitctx.resolve_commit(base, repo_dir)
    head_oid = gitctx.resolve_commit(head, repo_dir)
    try:
        mb = gitctx.merge_base(base_oid, head_oid, repo_dir)
    except gitctx.GitError as exc:
        raise GateFailure(f"{exc}. Check out with fetch-depth: 0 so the whole range is available.") from exc

    config, policy_note = load_config_at(mb, cfg_path, repo_dir)
    gate_cfg = config["gate"]

    status = gitctx.changed_status(mb, head_oid, repo_dir)
    new_paths, mutations, ordinary = classify_changes(status, evidence_root, mb, head_oid, repo_dir)

    gate_errors: list[str] = []
    warnings: list[str] = []
    errors_by_file: dict[str, list[str]] = {}

    for path in mutations:
        errors_by_file[path] = [
            "[G8] evidence already present at the base of the PR was modified, deleted or renamed. "
            "A declaration is a record of what happened: it is written once and never rewritten."
        ]

    # The identity of a record is the event_id it declares, not the name of the
    # file. Reading only the file names misses an artifact from before 0.4, when
    # the name did not have to match, whose id a new artifact could reuse.
    historical: set[str] = set()
    for p in gitctx.list_tree(mb, evidence_root, repo_dir):
        if not p.endswith(".json"):
            continue
        historical.add(event_key(Path(p).stem))
        try:
            past = json.loads(gitctx.show_text(mb, p, repo_dir))
        except (json.JSONDecodeError, gitctx.GitError, UnicodeDecodeError) as exc:
            # Not a warning: if a historical artifact cannot be read, its
            # event_id is unknown and a new artifact could reuse it. Warning
            # would make the uncertainty visible while still handing out a green
            # check, which is the failure mode this whole gate exists to avoid.
            gate_errors.append(
                f"[G8] historical evidence `{p}` cannot be read ({exc}), so the uniqueness of "
                "event ids cannot be guaranteed against it"
            )
            continue
        event = past.get("event") if isinstance(past, dict) else None
        past_id = event.get("event_id") if isinstance(event, dict) else None
        if isinstance(past_id, str) and past_id.strip():
            historical.add(event_key(past_id))

    schema = load_schema()
    artifacts: list[Artifact] = []
    for path in new_paths:
        try:
            data = json.loads(gitctx.show_text(head_oid, path, repo_dir))
        except (json.JSONDecodeError, gitctx.GitError) as exc:
            errors_by_file[path] = [f"invalid JSON: {exc}"]
            continue
        artifact = Artifact(path=path, data=data, errors=validate_artifact(data, schema))
        artifacts.append(artifact)
        if artifact.errors:
            errors_by_file[path] = artifact.errors
            continue

        own: list[str] = []
        ev = artifact.event
        # A new artifact has to carry a canonical UUID, full stop. Chasing every
        # equivalent spelling instead (URN prefixes, the `?+`, `?=` and `#`
        # components RFC 8141 ignores, empty or blank ids) is a losing game while
        # the validator does not assert `format: uuid`. Demanding the canonical
        # form closes all of them at once, and `event_key` stays for reading
        # history, which may hold artifacts written before this rule existed.
        if event_key(artifact.event_id) != artifact.event_id:
            own.append(
                f"[G8] event_id '{artifact.event_id}' is not a canonical UUID. Identity has to have "
                "one spelling: otherwise the same event written differently looks like two."
            )
        if Path(path).name != f"{artifact.event_id}.json":
            own.append(f"[G8] the file has to be named `{artifact.event_id}.json`")
        # Checked against history AND against the artifacts this same PR already
        # added: two files in one PR can spell the same id differently and each
        # one, on its own, looks unique.
        if event_key(artifact.event_id) in historical:
            own.append(
                f"[G8] event_id {artifact.event_id[:8]} already exists in the evidence of this "
                "repository or earlier in this PR: reusing it breaks the identity of the record"
            )
        else:
            historical.add(event_key(artifact.event_id))
        if ev.get("criticality_level") != config["criticality_level"]:
            own.append(
                f"[G2] artifact level ({ev.get('criticality_level')}) differs from the one declared "
                f"in the repository ({config['criticality_level']})"
            )
        if ev.get("criticality_level") == "A" and not config.get("level_A_enabled", False):
            own.append(
                "[G3] Level A blocked: data governance (section 10) is not validated in this "
                "repository (level_A_enabled=false). Applying the protocol at Level A in this "
                "situation is not half-compliance: it is a violation."
            )
        for r in artifact.data.get("actors", {}).get("reviewers", []):
            conf = r["confinement"]
            if ev.get("criticality_level") == "A" and conf["mode"] not in gate_cfg["level_A_accepted_confinement"]:
                own.append(
                    f"[G4] reviewer {r['reviewer_id']}: confinement '{conf['mode']}' not admitted in "
                    "Level A (the reviewer only reads, and that is guaranteed with permissions, not "
                    "with the brief)"
                )
            if not conf["verified"] and gate_cfg.get("warn_unverified_confinement", True):
                warnings.append(
                    f"{path}: confinement of reviewer {r['reviewer_id']} without post-run verification"
                )

        check_range_membership(artifact, mb, head_oid, repo_dir)
        if artifact.range_reason:
            own.append(artifact.range_reason)

        if own:
            artifact.errors = own
            errors_by_file[path] = own

    valid = [a for a in artifacts if a.valid]
    required = gate_cfg.get("required", True)

    if required:
        coverage_errors, coverage_notes, _demanding = evaluate_coverage(
            artifacts, ordinary, config, evidence_root, cfg_path
        )
        gate_errors.extend(coverage_errors)
    else:
        coverage_notes = []
        warnings.append(
            "the policy at the base of the PR declares gate.required=false: coverage is not "
            "demanded, but the declarations this PR does add are still validated"
        )

    if gitctx.path_exists(head_oid, cfg_path, repo_dir):
        try:
            head_raw = json.loads(gitctx.show_text(head_oid, cfg_path, repo_dir))
            if not isinstance(head_raw, dict):
                raise GateFailure("the configuration is not an object")
            validate_config_shape(head_raw, f"{cfg_path} (head of the PR)")
            base_raw = (
                json.loads(gitctx.show_text(mb, cfg_path, repo_dir))
                if gitctx.path_exists(mb, cfg_path, repo_dir)
                else None
            )
            if head_raw != base_raw:
                warnings.append(
                    f"this PR changes {cfg_path}. It is judged by the policy at the base; the new "
                    "one governs from the merge onwards."
                )
        except (GateFailure, json.JSONDecodeError, gitctx.GitError, UnicodeDecodeError) as exc:
            # The configuration at the head does not govern this PR, so an
            # unusable one warns and never decides the verdict.
            warnings.append(f"the configuration left at the head is not usable: {exc}")
    else:
        warnings.append(f"this PR leaves the repository without {cfg_path}")

    body = render_comment([a.data for a in valid], errors_by_file, gate_errors)
    body += f"\n\nPolicy: {policy_note}."
    if coverage_notes:
        body += "\n\nScope applied:\n" + "\n".join(f"- {n}" for n in coverage_notes)
    if warnings:
        body += "\n\nWarnings:\n" + "\n".join(f"- {w}" for w in warnings)

    write_summary(body)
    if post:
        print(f"[gate] {post_comment(body)}")

    failed = bool(gate_errors or errors_by_file)
    print(body)
    print(f"\n[gate] {'FAILED' if failed else 'OK'}: {len(valid)} valid artifact(s), "
          f"{len(errors_by_file)} with errors, {len(gate_errors)} global error(s)")
    return 1 if failed else 0


def main_gate(args) -> int:
    return run_gate(
        directory=args.directory,
        config_path=args.config,
        base=args.base,
        head=args.head,
        repo_dir=Path.cwd(),
        post=not args.no_comment,
    )

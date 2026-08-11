"""CI gate: validates the residue declarations of a PR and applies policy.

Gate checks (on top of the per-artifact R0 to R10 of rules.py):
  G1: at least one valid artifact in the PR range, unless the configuration
      declares the gate as not required (typical in Level C).
  G2: the artifact level matches the declared level of the repository
      (section 12.2: criticality level declared in a repo file).
  G3: Level A blocked while governance is not validated
      (section 3.1: Level A does not start until section 10 is validated).
  G4: confinement policy per level (section 10: the reviewer only reads,
      and that is guaranteed with permissions, not with the brief).
  G5: the reviewed commit belongs to the PR range.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from .render import MARKER, render_comment
from .rules import load_schema, validate_artifact

DEFAULT_CONFIG = {
    "criticality_level": "B",
    "level_A_enabled": False,
    "gate": {
        "required": True,
        "level_A_accepted_confinement": ["permissions", "sandbox"],
        "warn_unverified_confinement": True,
    },
}

V01_CONFIG_KEYS = {"nivel_criticidad", "nivel_A_habilitado"}


def load_config(path: Path) -> dict:
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    with path.open(encoding="utf-8") as f:
        config = json.load(f)
    old_keys = V01_CONFIG_KEYS & set(config)
    if old_keys:
        raise SystemExit(
            f"{path}: v0.1 Spanish keys found ({', '.join(sorted(old_keys))}). "
            "disensor 0.2 renamed the configuration to English: nivel_criticidad -> "
            "criticality_level, nivel_A_habilitado -> level_A_enabled, gate.requerido -> "
            "gate.required, gate.confinamiento_aceptado_nivel_A -> gate.level_A_accepted_confinement, "
            "gate.advertir_confinamiento_no_verificado -> gate.warn_unverified_confinement. "
            "Failing loudly instead of silently applying defaults."
        )
    combined = dict(DEFAULT_CONFIG)
    combined.update({k: v for k, v in config.items() if k != "gate"})
    gate = dict(DEFAULT_CONFIG["gate"])
    gate.update(config.get("gate", {}))
    combined["gate"] = gate
    return combined


def pr_range(base: str | None, head: str | None) -> tuple[str | None, str | None]:
    """Base and head of the PR: flags first, then the GitHub event."""
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


def range_commits(base: str, head: str, cwd: Path) -> list[str] | None:
    """Commits of the base..head range, head included.

    Returns None if git cannot resolve the range (shallow clone, unknown
    shas): that is a warning. An empty list is a valid result and means the
    range contains no commits: G5 must still be evaluated, because an empty
    range cannot contain the reviewed commit.
    """
    r = subprocess.run(
        ["git", "rev-list", f"{base}..{head}"],
        capture_output=True, text=True, cwd=cwd, check=False,
    )
    if r.returncode != 0:
        return None
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def pr_number() -> int | None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and Path(event_path).exists():
        with open(event_path, encoding="utf-8") as f:
            event = json.load(f)
        pr = event.get("pull_request") or {}
        return pr.get("number")
    return None


def post_comment(body: str) -> str:
    """Creates or updates the gate comment on the PR. Returns a readable status."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr = pr_number()
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
        existing = next((c for c in comments if MARKER in (c.get("body") or "")), None)
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
    except Exception as exc:  # the gate must not crash on network issues
        return f"could not post the comment: {exc}"


def write_summary(body: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(body + "\n")


def run_gate(directory: Path, config_path: Path, base: str | None,
             head: str | None, repo_dir: Path, post: bool = True) -> int:
    config = load_config(config_path)
    schema = load_schema()
    gate_cfg = config["gate"]

    gate_errors: list[str] = []
    warnings: list[str] = []
    errors_by_file: dict[str, list[str]] = {}
    valid: list[dict] = []

    base, head = pr_range(base, head)
    commits = range_commits(base, head, repo_dir) if (base and head) else None
    if commits is None and base and head:
        warnings.append(
            "could not resolve the commit range (checkout with fetch-depth 0): G5 not evaluated"
        )

    files = sorted(p for p in directory.glob("*.json")) if directory.exists() else []
    for path in files:
        with path.open(encoding="utf-8") as f:
            try:
                artifact = json.load(f)
            except json.JSONDecodeError as exc:
                errors_by_file[path.name] = [f"invalid JSON: {exc}"]
                continue
        errors = validate_artifact(artifact, schema)
        if errors:
            errors_by_file[path.name] = errors
            continue

        ev = artifact["event"]
        own: list[str] = []

        # G2: artifact level against the declared level of the repository.
        if ev["criticality_level"] != config["criticality_level"]:
            own.append(
                f"[G2] artifact level ({ev['criticality_level']}) differs from the one declared "
                f"in the repository ({config['criticality_level']})"
            )

        # G3: Level A blocked until governance is validated (section 3.1).
        if ev["criticality_level"] == "A" and not config.get("level_A_enabled", False):
            own.append(
                "[G3] Level A blocked: data governance (section 10) is not validated "
                "in this repository (level_A_enabled=false). Applying the protocol at Level A "
                "in this situation is not half-compliance: it is a violation."
            )

        # G4: confinement policy per level.
        for r in artifact["actors"]["reviewers"]:
            conf = r["confinement"]
            if ev["criticality_level"] == "A" and conf["mode"] not in gate_cfg["level_A_accepted_confinement"]:
                own.append(
                    f"[G4] reviewer {r['reviewer_id']}: confinement '{conf['mode']}' not admitted in Level A "
                    f"(the reviewer only reads, and that is guaranteed with permissions, not with the brief)"
                )
            if not conf["verified"] and gate_cfg.get("warn_unverified_confinement", True):
                warnings.append(
                    f"{path.name}: confinement of reviewer {r['reviewer_id']} without post-run verification"
                )

        # G5: the reviewed commit belongs to the PR range.
        if commits is not None:
            hc = ev["head_commit"]
            if not any(c.startswith(hc) or hc.startswith(c) for c in commits):
                own.append(
                    f"[G5] reviewed commit {hc} outside the PR range ({base[:7]}..{head[:7]})"
                )

        if own:
            errors_by_file[path.name] = own
        else:
            valid.append(artifact)

    # G1: at least one valid artifact, unless the gate is not required.
    if gate_cfg.get("required", True) and not valid:
        gate_errors.append(
            "[G1] no valid residue artifact for this PR "
            f"(directory '{directory}'). The declaration lists concrete residue or says "
            "explicitly that there was none; an empty field is not a declaration."
        )

    body = render_comment(valid, errors_by_file, gate_errors)
    if warnings:
        body += "\n\nWarnings:\n" + "\n".join(f"- {w}" for w in warnings)

    write_summary(body)
    if post:
        status = post_comment(body)
        print(f"[gate] {status}")

    failed = bool(gate_errors or errors_by_file)
    print(body)
    print(f"\n[gate] {'FAILED' if failed else 'OK'}: {len(valid)} valid artifact(s), "
          f"{len(errors_by_file)} with errors, {len(gate_errors)} global error(s)")
    return 1 if failed else 0


def main_gate(args) -> int:
    return run_gate(
        directory=Path(args.directory),
        config_path=Path(args.config),
        base=args.base,
        head=args.head,
        repo_dir=Path.cwd(),
        post=not args.no_comment,
    )

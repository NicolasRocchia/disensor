"""Scaffolding of a new artifact: `disensor new`.

Generates a template prefilled with what git already knows (repository,
commits, timestamp) and markers that do not pass validation until filled in.
A template that validates while empty would be cosmetic compliance from
the factory.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import uuid
from pathlib import Path
from .rules import CURRENT


def _git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def template(gate: str, level: str, profile: str, cwd: Path) -> dict:
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    remote = _git(["config", "--get", "remote.origin.url"], cwd) or "FILL_IN_repository"
    head = _git(["rev-parse", "HEAD"], cwd) or "FILL_IN"
    base = _git(["merge-base", "HEAD", "origin/main"], cwd) or _git(
        ["merge-base", "HEAD", "origin/master"], cwd
    )
    a: dict = {
        "schema": CURRENT,
        "profile": profile,
        "event": {
            "event_id": str(uuid.uuid4()),
            "created_at": now,
            "repository": remote,
            "head_commit": head,
            "gate": gate,
            "criticality_level": level,
            "abbreviated_path": {"used": False},
        },
        "actors": {
            "generator": {"family": "anthropic", "model": "claude-code"},
            "reviewers": [
                {
                    "reviewer_id": "r1",
                    "family": "openai",
                    "model": "FILL_IN_reviewer_model",
                    # La independencia se declara siempre: el valor que viene es
                    # el que el metodo espera, y si la ronda fue degradada hay
                    # que corregirlo Y agregar su item de residuo. Dejarlo como
                    # viene cuando no fue asi es declarar algo que no paso.
                    "independence": "cross_family",
                    "confinement": {
                        "mode": "read_only_by_instruction",
                        "verified": False,
                        "verification_method": "clean_git_status",
                    },
                }
            ],
            "human_arbiter": {"present": True},
        },
        "findings": [],
        "residue": {
            "declared_absence": True,
            "declaration": "FILL_IN: express declaration of absence, or replace this object with items",
        },
        "metrics": {
            "counts": {
                "total_findings": 0,
                "valid": {"incorporated": 0, "debt_recorded": 0, "owner_decision": 0},
                "false_positives": {"refuted_verifiable": 0, "refuted_interpretive": 0},
                "escalated_open": 0,
            }
        },
    }
    if base:
        a["event"]["base_commit"] = base
    return a


def main_new(args) -> int:
    directory = Path(args.directory)
    directory.mkdir(parents=True, exist_ok=True)
    a = template(args.gate, args.level, args.profile, Path.cwd())
    path = directory / f"{a['event']['event_id']}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Template created: {path}")
    print("Fill in the FILL_IN_ fields and the findings of the event; then: disensor validate", path)
    print("Note: the template does not validate until filled in. That is intentional.")
    return 0

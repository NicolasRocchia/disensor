"""Scaffolding of a new artifact: `disensor new`.

Generates a template prefilled with what git already knows (repository,
commits, timestamp) and markers that do not pass validation until filled in.
A template that validates while empty would be cosmetic compliance from
the factory.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
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
    if getattr(args, "round", None):
        try:
            crudo = sys.stdin.read() if args.round == "-" else Path(args.round).read_text(encoding="utf-8")
            a = from_round(json.loads(crudo), args.gate, args.level, args.profile, Path.cwd())
        except (RoundMismatch, OSError, json.JSONDecodeError) as exc:
            print(f"new: {exc}")
            return 1
    else:
        a = template(args.gate, args.level, args.profile, Path.cwd())
    path = directory / f"{a['event']['event_id']}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Template created: {path}")
    print("Fill in the FILL_IN_ fields and the findings of the event; then: disensor validate", path)
    print("Note: the template does not validate until filled in. That is intentional.")
    return 0


class RoundMismatch(Exception):
    """The result does not describe what is in front of us right now."""


def from_round(resultado: dict, gate: str, level: str, profile: str, cwd: Path) -> dict:
    """Build the template from what the runner observed, anchored to that round.

    The template resolves HEAD and the merge base when it is created, and that
    is wrong the moment anything was incorporated: the reviewer looked at A, a
    finding got fixed, HEAD moved to B, and a declaration built afterwards would
    say B was reviewed. The gate would catch it later by staleness, but by then
    the record already claimed something that did not happen. The anchors come
    from the result, literally, and a moved HEAD is refused here.
    """
    if resultado.get("result_version") != ROUND_RESULT_VERSION:
        raise RoundMismatch(
            f"the result declares {resultado.get('result_version')!r} and this disensor reads "
            f"{ROUND_RESULT_VERSION}"
        )
    anclas = resultado.get("anchors", {})
    observado = resultado.get("observed", {})
    declarado = resultado.get("declared", {})

    if declarado.get("reviewer_id") is None:
        raise RoundMismatch(
            "the result records no reviewer: that round never got an answer, and there is "
            "nothing to declare about it"
        )

    head_actual = _git(["rev-parse", "HEAD"], cwd)
    if anclas.get("head_oid") and head_actual and anclas["head_oid"] != head_actual:
        raise RoundMismatch(
            f"the round reviewed {anclas['head_oid'][:9]} and HEAD is now {head_actual[:9]}. "
            "Whatever moved it was not reviewed: run the round again over what is going to be "
            "merged. The rule is the freshness of the material, not the verdict of the report"
        )

    informe = observado.get("report_path")
    if informe and observado.get("report_hash"):
        ruta = Path(informe)
        if not ruta.exists():
            raise RoundMismatch(f"the report of the round is not at {ruta}")
        actual = "sha256:" + hashlib.sha256(ruta.read_bytes()).hexdigest()
        if actual != observado["report_hash"]:
            raise RoundMismatch(
                "the report changed since the round emitted its result. What is declared has to "
                "be what the reviewer wrote"
            )

    a = template(gate, level, profile, cwd)
    if resultado.get("repository"):
        a["event"]["repository"] = resultado["repository"]
    if anclas.get("head_oid"):
        a["event"]["head_commit"] = anclas["head_oid"]
    if anclas.get("merge_base_oid"):
        a["event"]["base_commit"] = anclas["merge_base_oid"]
    elif "base_commit" in a["event"]:
        del a["event"]["base_commit"]

    revisor = a["actors"]["reviewers"][0]
    revisor["reviewer_id"] = "r1"
    revisor["family"] = declarado["family"]
    revisor["model"] = declarado.get("model") or "FILL_IN_reviewer_model"
    revisor["independence"] = declarado["independence"]
    if declarado.get("hardening"):
        revisor["hardening"] = declarado["hardening"]
    hashes = resultado.get("hashes", {})
    if hashes.get("prompt_hash"):
        revisor["prompt_hash"] = hashes["prompt_hash"]

    # `verified` en false, y no por prudencia decorativa: el esquema define ese
    # campo como la verificacion de que el revisor no modifico el repositorio, y
    # lo que el runner hizo fue mirar `git status` antes y despues. Eso no ve
    # escrituras fuera del arbol, ni ignorados, ni .git/, ni la red. Prellenarlo
    # en true seria declarar mas de lo que se observo.
    revisor["confinement"] = {
        "mode": "read_only_by_instruction",
        "verified": False,
        "verification_method": "clean_git_status",
    }

    razon = _fallback_from(resultado)
    if declarado["independence"] != "cross_family":
        revisor["fallback_reason"] = razon

    items = []
    if declarado["independence"] != "cross_family":
        items.append({
            "id": f"r{len(items) + 1}",
            "class": "reviewer_correlation",
            "reviewer_ref": "r1",
            "requires_human_attention": True,
            "description": FILL_CORRELATION,
        })
    if declarado.get("hardening") == "unverified":
        items.append({
            "id": f"r{len(items) + 1}",
            "class": "reviewer_hardening_gap",
            "reviewer_ref": "r1",
            "requires_human_attention": True,
            "description": FILL_HARDENING,
        })
    if items:
        a["residue"] = {"items": items}

    a["extensions"] = {
        "dev.disensor.round": {
            "pack_hash": hashes.get("pack_hash"),
            "report_hash": observado.get("report_hash"),
            "tree_unchanged": observado.get("tree_unchanged"),
            "attempts": len(observado.get("attempts", [])),
        }
    }
    return a


FILL_CORRELATION = (
    "FILL_IN: the reviewer did not come from another model family, so the errors it shares "
    "with the generator were not covered by this round. Say which ones you consider open."
)
FILL_HARDENING = (
    "FILL_IN: the adapter's hardening is not verified, so the material under review could "
    "have addressed the reviewer before the brief did. Say what you did about it."
)
ROUND_RESULT_VERSION = "disensor/round-result/v1"


def _fallback_from(resultado: dict) -> dict:
    """Why the round settled for less, taken from the attempts when possible."""
    intentos = resultado.get("observed", {}).get("attempts", [])
    fallidos = [i for i in intentos if i.get("outcome") != "ok"]
    if not fallidos:
        return {"code": "no_other_family_available"}
    motivo = fallidos[0].get("outcome")
    codigo = {
        "not_found": "reviewer_unavailable",
        "not_runnable": "reviewer_unavailable",
        "executable_changed": "reviewer_unavailable",
        "timeout": "reviewer_unavailable",
    }.get(motivo, "quota_exhausted")
    return {
        "code": codigo,
        "detail": f"the better reviewers were tried first and failed: {motivo}",
    }

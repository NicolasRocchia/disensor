"""Self-contained HTML report of the residue declarations: `disensor report`.

The report READS; it never validates. The validator already exists twice (the
Python reference and the TypeScript port of the evidence plane) and a third
reading of the rules would drift like the first two would without the shared
vectors. The only check here is one of shape: a file that does not parse, or
that does not carry a `schema` and an `event`, or whose contents are not the
shape of a declaration, goes to a list of unreadable files at the end of the
report, and the rest goes on.

Two things the report cannot do, and says instead of pretending:

- It cannot say that something closed. The artifact has no field for that, so
  a debt recorded a month ago and one recorded yesterday look the same. The
  open view says "declared open on <date>, no later evidence of closure" and
  explains why at the top. Naming the absence is the doctrine of the tool
  applied to itself.
- It cannot recount `metrics.counts`. The numbers shown are the ones each
  declaration declares; that they match the findings read is checked by a
  test, not recomputed by the render.

The HTML is one file: CSS and JS inline, no network, a Content-Security-Policy
that forbids loading anything, system fonts. It is a pure function of the
declarations plus the package version: no generation timestamp travels in it,
the footer names the commit it was read from, and the ages ("N days ago") are
computed by the page when it is opened, which is when they are true.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import webbrowser
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Iterable

from . import __version__, gitctx

DEFAULT_DIRECTORY = ".residue"
DEFAULT_OUT = "informe-residuo.html"
DEFAULT_CONFIG = "disensor.config.json"   # the gate's default; the command reads the policy at the branch tip from it

# Exit codes of `disensor report`, one per outcome.
WRITTEN = 0
EMPTY = 1          # the directory exists but holds no declaration at all
MISSING = 2        # the directory does not exist
NOT_WRITTEN = 3    # the output could not be written, or was refused

# ---------------------------------------------------------------------------
# Vocabulary: the Spanish of the glossary in README.es.md and GUIDE.es.md, the
# terms that are already translated. A test keeps every table equal to the enum
# of the current schema, so a value the schema adds cannot fall through as its
# raw identifier without the suite saying so.
# ---------------------------------------------------------------------------
STATE_NAME = {
    "incorporated": "Incorporado",
    "debt_recorded": "Deuda registrada",
    "owner_decision": "Decisión del dueño",
    "refuted_verifiable": "Refutado verificable",
    "refuted_interpretive": "Refutado interpretativo",
    "escalated_open": "Escalado abierto",
}
# The two states the cycle closes by itself. Everything else stays open in the
# sense of section 9 of the protocol: it rests on somebody's judgement.
CLOSED_STATES = {"incorporated", "refuted_verifiable"}
OPEN_STATES = ["escalated_open", "owner_decision", "debt_recorded", "refuted_interpretive"]

# The open view groups by what each row asks of whoever reads it, not by the
# field it came from: an escalated finding and an escalation item both wait for
# a decision, and a reader deciding what to do next does not care which key of
# the schema holds them. The admission did not change: a residue item enters
# when its declaration marked it for human attention, a finding when its state
# is one the cycle did not close. This is also the order of the page.
QUEUE = [
    ("decision", "Espera una decisión",
     "escalaciones sin decisión y hallazgos escalados: alguien tiene que decidir"),
    ("debt", "Deuda anotada", "hallazgos válidos y diferidos, sin evidencia de pago"),
    ("gap:environment_not_reproducible", "No se pudo ejecutar: entorno no reproducible",
     "huecos de ejecución que piden atención humana"),
    ("gap:third_party_no_test_environment", "No se pudo ejecutar: tercero sin entorno de prueba",
     "huecos de ejecución que piden atención humana"),
    ("gap:other", "No se pudo ejecutar: otro motivo", "huecos de ejecución que piden atención humana"),
    ("gap:unstated", "No se pudo ejecutar: motivo no declarado",
     "huecos sin motivo, o con uno que este informe no conoce"),
    ("reviewer", "Sobre el revisor",
     "el revisor no fue independiente o su endurecimiento no se verificó"),
    ("judgement", "Descansa en un juicio", "refutaciones por juicio, no por prueba"),
    ("accepted", "Riesgo aceptado por el dueño", "no pide acción: queda quién aceptó qué"),
    ("other", "Otro residuo", "una clase que este informe no conoce: se muestra lo que trae"),
]
QUEUE_TITLE = {key: title for key, title, _ in QUEUE}
# The digest and the summary line sum these as one number: a gap is a gap
# whatever its reason, and the reason is what the group title says.
GAP_KEYS = [key for key, _, _ in QUEUE if key.startswith("gap:")]
_ITEM_QUEUE = {
    "escalation_without_decision": "decision",
    "reviewer_correlation": "reviewer",
    "reviewer_hardening_gap": "reviewer",
    "principal_refutation": "judgement",
}
_FINDING_QUEUE = {
    "escalated_open": "decision",
    "debt_recorded": "debt",
    "owner_decision": "accepted",
    "refuted_interpretive": "judgement",
}


def queue_key(row: dict) -> str:
    """The group of the open view a row belongs to (a key of QUEUE)."""
    if row["kind"] == "item":
        if row["class"] == "execution_gap":
            reason = row["gap_reason"]
            return f"gap:{reason}" if reason in GAP_REASON_NAME else "gap:unstated"
        return _ITEM_QUEUE.get(row["class"], "other")
    return _FINDING_QUEUE[row["state"]]

CLASS_NAME = {
    "escalation_without_decision": "Escalado sin decisión",
    "principal_refutation": "Refutación del principal",
    "execution_gap": "Gap de ejecución",
    "reviewer_correlation": "Revisor correlacionado con el generador",
    "reviewer_hardening_gap": "Endurecimiento del revisor sin verificar",
}
GAP_REASON_NAME = {
    "environment_not_reproducible": "entorno no reproducible",
    "third_party_no_test_environment": "tercero sin entorno de prueba",
    "other": "otro motivo",
}
AGAINST_NAME = {
    "repository": "el repositorio",
    "execution": "la ejecución",
    "external_source": "una fuente externa",
    "none": "nada",
}
FIX_TYPE_NAME = {
    "diff_gate": "compuerta de diff",
    "specific_test": "test específico",
    "pending_in_diff_gate": "pendiente en la compuerta de diff",
}
GATE_NAME = {"plan": "plan", "diff": "diff", "architecture": "arquitectura"}
CONFINEMENT_NAME = {
    "permissions": "permisos",
    "sandbox": "sandbox",
    "read_only_by_instruction": "sólo lectura por instrucción",
    "no_confinement": "sin confinamiento",
}
INDEPENDENCE_NAME = {
    "cross_family": "familia distinta",
    "same_family_distinct_model": "misma familia, otro modelo",
    "same_model_fresh_context": "mismo modelo, contexto nuevo",
}
HARDENING_NAME = {"verified": "verificado", "unverified": "sin verificar"}
SEVERITY_LEVEL = {"critical": 4, "major": 3, "minor": 2, "info": 1}
SEVERITY_NAME = {"critical": "crítico", "major": "mayor", "minor": "menor", "info": "info"}

# What an older version could not have declared. Read, never emitted.
VERSION_NOTE = {
    "residue/v0.2": "casi sin ubicaciones; sin independencia ni endurecimiento del revisor",
    "residue/v0.3": "sin independencia ni endurecimiento del revisor",
    "residue/v0.4": "completa",
}
UNKNOWN_VERSION_NOTE = "versión que este informe no conoce: se muestra lo que trae"

# A location is split on commas only when every part looks like a path. It is
# free text in the schema, and the corpus has "README.md, README.es.md" next to
# prose with commas: the map by file is approximate by construction.
_PATH_PART = re.compile(r"^[\w./\\-]+$")
_MARKER = re.compile(r"@@([A-Z_]+)@@")
_SCHEME = re.compile(r"^https?://")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
@dataclass
class Unreadable:
    file: str
    reason: str


def parse_created(raw) -> tuple[datetime | None, bool]:
    """`event.created_at` as an aware datetime (or None), and whether it came naive.

    A value without a zone is taken as UTC. The schema asks for an RFC 3339
    date-time, so a naive value is already outside the contract; reading it as
    local time would make the same corpus order and age differently on a
    workstation in Buenos Aires and on a CI runner, and the report marks it
    instead of guessing.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None, False
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None, False
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc), True
    return parsed, False


def parse_date(raw) -> datetime | None:
    return parse_created(raw)[0]


def group_repository(raw) -> str:
    """The identity used to group declarations, never shown instead of the original.

    The corpus spells the same repository three ways (`github.com/o/r`,
    `https://github.com/o/r.git`, `https://github.com/o/r`), and
    `gitctx.normalize_repository` already collapses them. A minimized profile
    carries a `sha256:` hash instead of a locator, and it goes through as is:
    the normaliser would read its colon as the `git@host:path` separator.
    """
    text = str(raw or "").strip()
    if not text:
        return "(sin repositorio)"
    if text.startswith("sha256:"):
        return text
    return gitctx.normalize_repository(text) or text


def split_location(raw) -> list[str]:
    if not raw:
        return []
    text = str(raw)
    parts = [p.strip() for p in text.split(",")]
    if len(parts) > 1 and all(_PATH_PART.match(p) for p in parts if p):
        return [p for p in parts if p]
    return [text.strip()]


def _sort_key(d: dict) -> tuple[float, str]:
    when = d["date"].timestamp() if d["date"] else float("-inf")
    return (when, d["event_id"])


def normalize(name: str, raw: dict) -> dict:
    """One declaration in the shape the render wants. Raises on a malformed one.

    Everything is read with `.get` and a default, but a value of the wrong
    type (an `event` that is a list, a `findings` that is a string) still
    blows up inside, on purpose: the caller catches that and lists the file as
    unreadable, which is the right place for a file that has the two keys of
    a declaration and nothing else of one.
    """
    ev = raw.get("event") or {}
    actors = raw.get("actors") or {}
    residue = raw.get("residue") or {}
    metrics = raw.get("metrics") or {}
    if not isinstance(ev, dict) or not isinstance(actors, dict) or not isinstance(residue, dict):
        raise TypeError("event, actors and residue have to be objects")
    if not isinstance(metrics, dict):
        raise TypeError("metrics has to be an object")
    generator = actors.get("generator") or {}
    arbiter = actors.get("human_arbiter") or {}
    abbreviated = ev.get("abbreviated_path") or {}
    schema = str(raw.get("schema"))
    profile = str(raw.get("profile") or "full")

    reviewers = []
    for r in actors.get("reviewers") or []:
        conf = r.get("confinement") or {}
        fallback = r.get("fallback_reason") or {}
        reviewers.append({
            "id": str(r.get("reviewer_id") or ""),
            "family": str(r.get("family") or ""),
            "model": str(r.get("model") or ""),
            "independence": r.get("independence"),
            "hardening": r.get("hardening"),
            "confinement": conf.get("mode"),
            "confinement_verified": conf.get("verified"),
            "fallback": fallback.get("code") if isinstance(fallback, dict) else None,
        })

    findings = []
    for f in raw.get("findings") or []:
        verification = f.get("verification") or {}
        fix = f.get("fix_verification") or {}
        evidence = f.get("evidence") or {}
        location = f.get("location")
        findings.append({
            "kind": "finding",
            "id": str(f.get("id") or ""),
            "origin": str(f.get("origin") or ""),
            "severity": str(f.get("severity") or ""),
            "title": f.get("title"),
            "description": f.get("description"),
            "location": str(location) if location else None,
            "files": split_location(location),
            "state": str(f.get("final_state") or ""),
            "against": verification.get("against"),
            "detail": verification.get("detail"),
            "fix_type": fix.get("type"),
            "fix_reference": fix.get("reference"),
            "remedy_adjustment": f.get("remedy_adjustment"),
            "risk_record": f.get("risk_record"),
            "debt_id": f.get("debt_id"),
            "evidence_link": evidence.get("link") if isinstance(evidence, dict) else None,
            "evidence_hash": evidence.get("hash") if isinstance(evidence, dict) else None,
        })

    items = []
    for it in residue.get("items") or []:
        evidence = it.get("evidence") or {}
        acceptance = it.get("lead_acceptance") or {}
        items.append({
            "kind": "item",
            "id": str(it.get("id") or ""),
            "class": str(it.get("class") or ""),
            "gap_reason": it.get("gap_reason"),
            "refutation_type": it.get("refutation_type"),
            "attention": bool(it.get("requires_human_attention")),
            "description": it.get("description"),
            "finding_ref": it.get("finding_ref"),
            "reviewer_ref": it.get("reviewer_ref"),
            "evidence_link": evidence.get("link") if isinstance(evidence, dict) else None,
            "lead": acceptance.get("lead") if isinstance(acceptance, dict) else None,
        })

    counts = metrics.get("counts") or {}
    created = ev.get("created_at")
    when, naive = parse_created(created)
    d = {
        "file": name,
        "event_id": str(ev.get("event_id") or ""),
        "schema": schema,
        "profile": profile,
        "created_at": str(created) if created is not None else "",
        "date": when,
        "naive": naive,
        "repository": str(ev.get("repository") or ""),
        "repository_group": group_repository(ev.get("repository")),
        "gate": str(ev.get("gate") or ""),
        "level": str(ev.get("criticality_level") or ""),
        "head": str(ev.get("head_commit") or ""),
        "base": str(ev.get("base_commit") or "") or None,
        "pr": str(ev["pr"]) if ev.get("pr") not in (None, "") else None,
        "abbreviated": bool(abbreviated.get("used")) if isinstance(abbreviated, dict) else False,
        "abbreviated_justification": abbreviated.get("justification") if isinstance(abbreviated, dict) else None,
        "generator": {
            "family": str(generator.get("family") or ""),
            "model": str(generator.get("model") or ""),
        },
        "reviewers": reviewers,
        "arbiter": bool(arbiter.get("present")),
        "findings": findings,
        "items": items,
        "absence": bool(residue.get("declared_absence")),
        "declaration": residue.get("declaration"),
        "counts": counts if isinstance(counts, dict) else {},
        "extensions": bool(raw.get("extensions")),
    }
    # Back references: the open view and the cases list rows without their
    # declaration, and a row has to say where it came from.
    for f in findings:
        f["decl"] = d
    for it in items:
        it["decl"] = d
    return d


def read_declarations(files: Iterable[tuple[str, str]]) -> tuple[list[dict], list[Unreadable]]:
    """Declarations newest first, and the files that could not be read.

    The admission check is the shape of a declaration, nothing more: valid
    JSON, an object, a `schema` and an `event`. A file that passes that and
    still is not a declaration (an `event` that is a list) fails inside
    `normalize` and lands on the same list: one malformed file must never take
    the report down with it.
    """
    declarations: list[dict] = []
    unreadable: list[Unreadable] = []
    for name, text in files:
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            unreadable.append(Unreadable(name, f"not valid JSON ({exc})"))
            continue
        if not isinstance(raw, dict) or not raw.get("schema") or not raw.get("event"):
            unreadable.append(Unreadable(name, "no schema or event: it does not look like a declaration"))
            continue
        try:
            declarations.append(normalize(name, raw))
        except (TypeError, AttributeError, KeyError, ValueError, IndexError) as exc:
            unreadable.append(Unreadable(
                name, f"does not have the shape of a declaration ({type(exc).__name__}: {exc})",
            ))
    declarations.sort(key=_sort_key, reverse=True)
    return declarations, unreadable


def read_directory(directory: Path) -> tuple[list[dict], list[Unreadable]]:
    """The `*.json` files of a directory, as `disensor report` reads them."""
    pairs: list[tuple[str, str]] = []
    unreadable: list[Unreadable] = []
    for path in sorted(directory.glob("*.json")):
        try:
            pairs.append((path.name, path.read_bytes().decode("utf-8")))
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append(Unreadable(path.name, f"cannot read ({exc})"))
    declarations, more = read_declarations(pairs)
    return declarations, sorted(unreadable + more, key=lambda u: u.file)


def read_tree(rev: str, evidence_root: str, repo: Path) -> tuple[list[dict], list[Unreadable]]:
    """The `*.json` files directly under `evidence_root` at a git revision.

    What the gate hook uses: the same objects the gate just judged, never the
    working tree and never the synthetic merge commit a CI checkout leaves.
    """
    depth = len(PurePosixPath(evidence_root).parts) + 1
    pairs: list[tuple[str, str]] = []
    unreadable: list[Unreadable] = []
    for path in gitctx.list_tree(rev, evidence_root, repo):
        pure = PurePosixPath(path)
        if not path.endswith(".json") or len(pure.parts) != depth:
            continue
        try:
            pairs.append((pure.name, gitctx.show_text(rev, path, repo)))
        except (gitctx.GitError, UnicodeDecodeError) as exc:
            unreadable.append(Unreadable(pure.name, f"cannot read at {rev[:7]} ({exc})"))
    declarations, more = read_declarations(pairs)
    return declarations, sorted(unreadable + more, key=lambda u: u.file)


# ---------------------------------------------------------------------------
# Aggregation: what the views need, computed once. No `now` anywhere.
# ---------------------------------------------------------------------------
@dataclass
class Model:
    declarations: list
    unreadable: list
    repositories: list
    latest: dict | None
    open_groups: list          # [(key, title, note, rows)] one per QUEUE entry, rows oldest first
    open_total: int
    open_from_latest: int
    now_rows: list             # what the latest declaration left open, as written
    cases: list
    counts: dict
    by_file: list
    without_location: int
    minimized: int
    by_day: list
    unit: str                  # day, week, month, year or sparse
    by_week: list              # declarations per week for the board, same shape as by_day
    week_unit: str             # week, unless the span is too wide even for weeks
    health: dict               # what the declarations say of how they were reviewed, per event
    gaps_by_reason: list       # [(key, name, n)] over every execution gap, most frequent first
    gaps_total: int
    gaps_attention: int
    reviewers: list
    versions: list
    first: datetime | None
    last: datetime | None


def _chronological(rows: list) -> list:
    return sorted(rows, key=lambda r: _sort_key(r["decl"]))


# The time series never materialises more than this many buckets. A single
# schema-valid `created_at` in year 9999 (the validator checks no format, and
# the report reads without validating) used to turn a green gate into an
# allocation of millions of day records; the unit grows with the span instead.
MAX_BUCKETS = 400
UNIT_NAME = {"day": "día", "week": "semana", "month": "mes", "year": "año", "sparse": "día"}


def _bucket_start(day: date, unit: str) -> date:
    if unit == "week":
        return day - timedelta(days=day.weekday())
    if unit == "month":
        return day.replace(day=1)
    if unit == "year":
        return day.replace(month=1, day=1)
    return day


def _next_bucket(start: date, unit: str) -> date:
    if unit == "week":
        return start + timedelta(days=7)
    if unit == "month":
        return start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    if unit == "year":
        return start.replace(year=start.year + 1)
    return start + timedelta(days=1)


_UNIT_LENGTH = (("day", 1), ("week", 7), ("month", 28), ("year", 365))


def time_series(dated: list[dict], wanted: str | None = None) -> tuple[str, list[dict]]:
    """Declarations, findings and attention items per bucket of time, bounded.

    The unit is the finest one that keeps the whole span under MAX_BUCKETS
    (day, week, month, year); a span too wide even for years falls back to a
    sparse series of the days that hold declarations, with no empty buckets
    in between, and the panel says the axis is not continuous. `wanted` asks
    for a coarser unit (the board counts declarations per week) and is
    honoured only while it keeps the span under the bound; the caller reads
    the unit that came back.
    """
    if not dated:
        return wanted or "day", []
    days = sorted({d["date"].date() for d in dated})
    span = (days[-1] - days[0]).days + 1
    unit = "sparse"
    for candidate, length in _UNIT_LENGTH:
        if span / length <= MAX_BUCKETS:
            unit = candidate
            break
    if wanted and any(wanted == c and span / n <= MAX_BUCKETS for c, n in _UNIT_LENGTH):
        unit = wanted
    buckets: dict[date, dict] = {}
    for d in dated:
        key = _bucket_start(d["date"].date(), "day" if unit == "sparse" else unit)
        entry = buckets.setdefault(key, {"day": key, "declarations": 0, "findings": 0, "attention": 0})
        entry["declarations"] += 1
        entry["findings"] += len(d["findings"])
        entry["attention"] += sum(1 for it in d["items"] if it["attention"])
    if unit == "sparse":
        return unit, [buckets[k] for k in sorted(buckets)]
    series: list[dict] = []
    cursor = _bucket_start(days[0], unit)
    last = _bucket_start(days[-1], unit)
    while cursor <= last and len(series) <= MAX_BUCKETS:
        series.append(buckets.get(cursor) or {"day": cursor, "declarations": 0, "findings": 0, "attention": 0})
        try:
            cursor = _next_bucket(cursor, unit)
        except ValueError:  # past date.max: nothing after it to draw
            break
    return unit, series


def open_rows(d: dict) -> list:
    """What one declaration left open: its residue items marked for human
    attention and its findings in a state the cycle did not close, in the
    order they were written. A finding one of those items points at
    (`finding_ref`) folds into the item's row, which carries the finding's
    title and state, only when both ask the same thing: the item is then the
    residue record of that finding. In the corpus every escalated finding has
    such an item, and counting both said "8 wait for a decision" where there
    were five decisions to take. An item of another class that points at an
    accepted risk or a debt hides nothing: the schema allows the reference,
    and the risk or the debt is still an open obligation of its own."""
    items = [it for it in d["items"] if it["attention"]]
    folded = set()
    for it in items:
        origin = _referenced_finding(it)
        if origin is not None and origin["state"] in OPEN_STATES and queue_key(origin) == queue_key(it):
            folded.add(origin["id"])
    return items + [f for f in d["findings"] if f["state"] in OPEN_STATES and f["id"] not in folded]


def _referenced_finding(it: dict) -> dict | None:
    if not it["finding_ref"]:
        return None
    return next((f for f in it["decl"]["findings"] if f["id"] == it["finding_ref"]), None)


def open_queue(declarations: list[dict]) -> list[tuple[str, str, str, list]]:
    """The open rows of every declaration, grouped by what they ask (QUEUE)
    and oldest first inside each group. Empty groups stay in the list: the
    render skips them and the digest counts them as zero."""
    buckets: dict[str, list] = {key: [] for key, _, _ in QUEUE}
    for d in declarations:
        for row in open_rows(d):
            buckets[queue_key(row)].append(row)
    return [(key, title, note, _chronological(buckets[key])) for key, title, note in QUEUE]


def _health(declarations: list[dict]) -> dict:
    """What the declarations say of how they were reviewed, counted per event.

    A field an older schema did not have counts as not declared, never as
    failed: the denominator of independence and hardening is the events that
    declare them, and the render says how many do not. These numbers measure
    the protocol, not the people; in a repository of one person they measure
    that person, and the page says so.
    """
    def every(d: dict, pred) -> bool:
        return bool(d["reviewers"]) and all(pred(r) for r in d["reviewers"])

    independence = [d for d in declarations if every(d, lambda r: r["independence"] is not None)]
    hardening = [d for d in declarations if every(d, lambda r: r["hardening"] is not None)]
    return {
        "events": len(declarations),
        "cross_family": sum(1 for d in independence if every(d, lambda r: r["independence"] == "cross_family")),
        "independence_declared": len(independence),
        "hardening_verified": sum(1 for d in hardening if every(d, lambda r: r["hardening"] == "verified")),
        "hardening_declared": len(hardening),
        "confinement_verified": sum(1 for d in declarations if every(d, lambda r: r["confinement_verified"] is True)),
        "arbiter": sum(1 for d in declarations if d["arbiter"]),
        "absence": sum(1 for d in declarations if d["absence"]),
    }


def aggregate(declarations: list[dict], unreadable: list[Unreadable]) -> Model:
    findings = [f for d in declarations for f in d["findings"]]
    latest = declarations[0] if declarations else None

    groups = open_queue(declarations)
    open_total = sum(len(rows) for _, _, _, rows in groups)
    now_rows = open_rows(latest) if latest is not None else []

    cases = sorted(
        (f for f in findings
         if f["state"] == "incorporated" and f["severity"] in ("critical", "major")),
        key=lambda f: (-SEVERITY_LEVEL.get(f["severity"], 0), -_sort_key(f["decl"])[0], f["decl"]["event_id"]),
    )

    # Summed as declared, bucket by bucket; nothing is recounted from the list.
    counts = Counter()
    for d in declarations:
        c = d["counts"]
        counts["total"] += _int(c.get("total_findings"))
        valid = c.get("valid") or {}
        false_positives = c.get("false_positives") or {}
        for key in ("incorporated", "debt_recorded", "owner_decision"):
            counts[key] += _int(valid.get(key) if isinstance(valid, dict) else 0)
        for key in ("refuted_verifiable", "refuted_interpretive"):
            counts[key] += _int(false_positives.get(key) if isinstance(false_positives, dict) else 0)
        counts["escalated_open"] += _int(c.get("escalated_open"))

    by_file = Counter(name for f in findings for name in f["files"])
    top_files = sorted(by_file.items(), key=lambda kv: (-kv[1], kv[0]))[:12]
    without_location = sum(1 for f in findings if not f["location"])
    minimized = sum(1 for d in declarations if d["profile"] == "minimized")

    dated = [d for d in declarations if d["date"]]
    unit, by_day = time_series(dated)
    week_unit, by_week = time_series(dated, "week")

    # Every execution gap, with or without human attention: the board asks
    # what could not be arbitrated by execution, and the reason is what the
    # declaration says it is.
    gap_counter: Counter = Counter()
    gaps_attention = 0
    for d in declarations:
        for it in d["items"]:
            if it["class"] == "execution_gap":
                gap_counter[it["gap_reason"] if it["gap_reason"] in GAP_REASON_NAME else "unstated"] += 1
                gaps_attention += 1 if it["attention"] else 0
    gaps_by_reason = [(key, GAP_REASON_NAME.get(key, "motivo no declarado"), n)
                      for key, n in sorted(gap_counter.items(), key=lambda kv: (-kv[1], kv[0]))]

    reviewers = Counter((r["family"], r["model"]) for d in declarations for r in d["reviewers"])
    reviewer_rows = sorted(reviewers.items(), key=lambda kv: (-kv[1], kv[0]))
    versions = Counter(d["schema"] for d in declarations)
    version_rows = [(schema, n, VERSION_NOTE.get(schema, UNKNOWN_VERSION_NOTE))
                    for schema, n in sorted(versions.items())]

    dates = sorted(d["date"] for d in dated)
    return Model(
        declarations=declarations,
        unreadable=unreadable,
        repositories=sorted({d["repository_group"] for d in declarations}),
        latest=latest,
        open_groups=groups,
        open_total=open_total,
        open_from_latest=len(now_rows),
        now_rows=now_rows,
        cases=cases,
        counts=dict(counts),
        by_file=top_files,
        without_location=without_location,
        minimized=minimized,
        by_day=by_day,
        unit=unit,
        by_week=by_week,
        week_unit=week_unit,
        health=_health(declarations),
        gaps_by_reason=gaps_by_reason,
        gaps_total=sum(gap_counter.values()),
        gaps_attention=gaps_attention,
        reviewers=reviewer_rows,
        versions=version_rows,
        first=dates[0] if dates else None,
        last=dates[-1] if dates else None,
    )


def _int(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


# ---------------------------------------------------------------------------
# Render. Every piece of data goes through `E`; the JS never builds markup.
# ---------------------------------------------------------------------------
def E(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _short(text, limit: int) -> str:
    """Truncated with the full text in `title`, so a long model name never breaks the layout."""
    text = "" if text is None else str(text)
    if len(text) <= limit:
        return E(text)
    return f'<span title="{E(text)}">{E(text[:limit - 1])}…</span>'


def _link(url, text=None) -> str:
    """An anchor only for http(s); anything else is text. Opened on click, never loaded."""
    text = url if text is None else text
    if isinstance(url, str) and _SCHEME.match(url):
        return f'<a href="{E(url)}" rel="noopener">{E(text)}</a>'
    return E(text)


def _fmt_date(d: dict) -> str:
    if d["date"]:
        return d["date"].strftime("%d/%m/%Y")
    return "fecha ilegible"


def _fmt_time(d: dict) -> str:
    return d["date"].strftime("%H:%M") if d["date"] else ""


def _iso(d: dict) -> str:
    return d["date"].isoformat() if d["date"] else ""


def _age_span(d: dict) -> str:
    if not d["date"]:
        return f'<span class="edad" title="{E(d["created_at"])}">fecha ilegible</span>'
    zone = ' title="sin zona horaria: se lee como UTC"' if d["naive"] else ""
    return f'<span class="edad" data-fecha="{E(_iso(d))}"{zone}></span>'


def _meter(severity: str) -> str:
    level = SEVERITY_LEVEL.get(severity, 0)
    segments = "".join(f'<i class="{"on" if i <= level else ""}"></i>' for i in range(1, 5))
    name = SEVERITY_NAME.get(severity, severity)
    return (f'<span class="sev" title="severidad {E(name)}"><span class="seg">{segments}</span>'
            f'<b>{E(name)}</b></span>')


def _decl_ref(d: dict) -> str:
    return f'<a class="ref" href="#d-{E(d["event_id"])}">decl. <b>{E(d["event_id"][:8])}</b></a>'


def _latest_tag(d: dict, model: Model) -> str:
    return '<span class="etq ultima">última declaración</span>' if d is model.latest else ""


def _when(d: dict) -> str:
    return (f'<div class="cuando"><span class="rotulo">declarado abierto</span>{E(_fmt_date(d))}'
            f'{_age_span(d)}</div>')


def _item_row(it: dict, model: Model, index: int | None = None) -> str:
    d = it["decl"]
    klass = CLASS_NAME.get(it["class"], it["class"])
    extra = ""
    if it["gap_reason"]:
        extra = f" · {GAP_REASON_NAME.get(it['gap_reason'], it['gap_reason'])}"
    elif it["refutation_type"]:
        extra = " · " + ("interpretativa" if it["refutation_type"] == "interpretive" else "verificable")
    if it["description"]:
        text = f'<div class="txt">{E(it["description"])}</div>'
    else:
        text = ('<div class="txt mudo">Sin descripción: perfil minimizado. Quedan la clase, la atención '
                'humana y de qué declaración salió.</div>')
    origin = _referenced_finding(it)
    if origin is not None and origin["title"]:
        text += (f'<div class="txt origen"><b>{E(STATE_NAME.get(origin["state"], origin["state"]))}</b> '
                 f'{E(origin["title"])}</div>')
    in_open = index is not None
    footer = [
        '<span class="etq abierto">pide atención humana</span>' if it["attention"] else "",
        _latest_tag(d, model) if in_open else "",
        "<span>sin evidencia posterior de cierre</span>" if in_open else "",
        _decl_ref(d) if in_open else "",
        f"<span>hallazgo {E(it['finding_ref'])}</span>" if it["finding_ref"] else "",
        f"<span>revisor {E(it['reviewer_ref'])}</span>" if it["reviewer_ref"] else "",
        f"<span>{_link(it['evidence_link'], 'evidencia')}</span>" if it["evidence_link"] else "",
        f"<span>aceptado por {E(it['lead'])}</span>" if it["lead"] else "",
    ]
    attrs = f' data-orden="{index}"' if in_open else ""
    classes = "fila" + (" abierta" if it["attention"] else "") + ("" if in_open else " sola")
    when = _when(d) if in_open else ""
    pie = "".join(footer)
    return (f'<div class="{classes}"{attrs}>{when}<div class="cuerpo"><div class="tit">{E(klass)}{E(extra)}</div>'
            f'{text}<div class="pie">{pie}</div></div></div>')


def _finding_row(f: dict, model: Model, index: int | None = None) -> str:
    """A finding as a row of the open queue (with `index`, its place in the
    chronological order the switch moves) or of the block of the latest
    declaration (without it: no date column, no tag, no reference back,
    nothing the block's heading already says)."""
    d = f["decl"]
    in_open = index is not None
    is_open = f["state"] not in CLOSED_STATES
    if f["title"]:
        title = f'<div class="tit">{E(f["title"])}</div>'
    else:
        title = ('<div class="tit mudo">Sin título: perfil minimizado. Quedan la severidad, el estado '
                 'y de qué declaración salió.</div>')
    note = f["risk_record"] or f["description"] or ""
    footer = [
        _meter(f["severity"]),
        f'<span class="etq{" abierto" if is_open else ""}">{E(STATE_NAME.get(f["state"], f["state"]))}</span>',
        _latest_tag(d, model) if in_open else "",
        "<span>sin evidencia posterior de cierre</span>" if in_open else "",
        f"<span>deuda <b>{_link(f['debt_id'], _cut(f['debt_id'], 46))}</b></span>" if f["debt_id"] else "",
        f"<span>{E(f['location'])}</span>" if f["location"] else "",
        _decl_ref(d) if in_open else "",
    ]
    classes = "fila" + (" abierta" if is_open else "") + ("" if in_open else " sola")
    attrs = f' data-orden="{index}"' if in_open else ""
    when = _when(d) if in_open else ""
    body = f'<div class="txt">{E(note)}</div>' if note else ""
    pie = "".join(footer)
    return (f'<div class="{classes}"{attrs}>{when}'
            f'<div class="cuerpo">{title}{body}<div class="pie">{pie}</div></div></div>')


def _cut(text, limit: int) -> str:
    text = "" if text is None else str(text)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _group(key: str, title: str, note: str, rows_html: list[str], folded: bool = False) -> str:
    if not rows_html:
        return ""
    rows = "".join(rows_html)
    head = f'<h3>{E(title)}</h3><span class="c">{len(rows_html)}</span><span class="d">{E(note)}</span>'
    if folded:
        return (f'<details class="grupo plegado" data-grupo="{E(key)}"><summary class="grupo-cab">{head}</summary>'
                f'<div class="filas">{rows}</div></details>')
    return (f'<section class="grupo" data-grupo="{E(key)}"><div class="grupo-cab">{head}</div>'
            f'<div class="filas">{rows}</div></section>')


def _row(r: dict, model: Model, index: int | None = None) -> str:
    return _item_row(r, model, index) if r["kind"] == "item" else _finding_row(r, model, index)


def _oldest(groups: dict, keys: list[str]) -> dict | None:
    """The declaration of the oldest row across those groups, or None."""
    heads = [groups[k][0] for k in keys if groups[k]]
    return min(heads, key=lambda r: _sort_key(r["decl"]))["decl"] if heads else None


def _digest(model: Model) -> str:
    """What the whole queue asks, before any row: how many wait for a decision
    and since when, how many debts, how many gaps. Sums of the groups below,
    so the reader who stops here read the same numbers as the one who goes on."""
    groups = {key: rows for key, _, _, rows in model.open_groups}

    def since(d: dict | None) -> str:
        return f", la más vieja declarada el {E(_fmt_date(d))}{_age_span(d)}" if d else ""

    lines = []
    n = len(groups["decision"])
    if n:
        lines.append(f'<li><b>{n}</b> {"espera" if n == 1 else "esperan"} una decisión'
                     f'{since(_oldest(groups, ["decision"]))}.</li>')
    n = len(groups["debt"])
    if n:
        lines.append(f'<li><b>{n}</b> {"deuda anotada" if n == 1 else "deudas anotadas"} sin evidencia de pago'
                     f'{since(_oldest(groups, ["debt"]))}.</li>')
    n = sum(len(groups[k]) for k in GAP_KEYS)
    if n:
        reasons = "; ".join(f"{len(groups[k])} {QUEUE_TITLE[k].split(': ', 1)[1]}" for k in GAP_KEYS if groups[k])
        lines.append(f'<li><b>{n}</b> {"hueco" if n == 1 else "huecos"} de ejecución que '
                     f'{"pide" if n == 1 else "piden"} atención humana: {E(reasons)}.</li>')
    n = len(groups["reviewer"])
    if n:
        lines.append(f'<li><b>{n}</b> sobre el revisor: independencia o endurecimiento sin verificar.</li>')
    n = len(groups["judgement"])
    if n:
        lines.append(f'<li><b>{n}</b> {"descansa" if n == 1 else "descansan"} en un juicio, no en una prueba.</li>')
    n = len(groups["accepted"])
    if n:
        lines.append(f'<li><b>{n}</b> {"riesgo aceptado" if n == 1 else "riesgos aceptados"} por el dueño, '
                     f'{"plegado" if n == 1 else "plegados"} al final: no {"pide" if n == 1 else "piden"} acción.</li>')
    n = len(groups["other"])
    if n:
        lines.append(f'<li><b>{n}</b> de una clase que este informe no conoce.</li>')
    total = model.open_total
    head = (f'<p class="digest-cab"><b>{total}</b> '
            f'{"ítem declarado abierto" if total == 1 else "ítems declarados abiertos"}, '
            f'sin evidencia posterior de cierre.</p>')
    return f'<div class="digest">{head}<ul>{"".join(lines)}</ul></div>'


def _now(model: Model) -> str:
    """What the latest declaration left open, always on top and also when it
    is nothing: before a merge, this is the block to read."""
    d = model.latest
    if d is None:
        return ""
    ref = f'<a href="#d-{E(d["event_id"])}"><code>{E(d["event_id"][:8])}</code></a>'
    when = f"{E(_fmt_date(d))}{_age_span(d)}"
    if not model.now_rows:
        return (f'<section class="ahora"><div class="grupo-cab"><h3>La última declaración</h3>'
                f'<span class="d">{ref} · {when}</span></div>'
                f'<p class="ahora-vacia">No dejó ítems abiertos: ni residuo con atención humana ni hallazgos '
                f'sin cerrar. Lo que sí declaró está en su ficha.</p></section>')
    n = len(model.now_rows)
    rows = "".join(_row(r, model) for r in model.now_rows)
    return (f'<section class="ahora"><div class="grupo-cab"><h3>Lo que dejó abierto la última declaración</h3>'
            f'<span class="c">{n}</span><span class="d">{ref} · {when}</span></div>'
            f'<div class="filas">{rows}</div></section>')


def render_open(model: Model) -> str:
    groups_html = []
    for key, title, note, rows in model.open_groups:
        rendered = [_row(r, model, i) for i, r in enumerate(rows)]
        groups_html.append(_group(key, title, note, rendered, folded=(key == "accepted")))
    digest = _digest(model) if model.open_total else ""
    empty = ""
    if not model.open_total:
        empty = ('<div class="vacio">Ninguna declaración dejó residuo abierto. Eso también se declara: '
                 'las ausencias expresas están en cada ficha.</div>')
    groups = "".join(groups_html)
    return f"""
    <div class="intro">
      <h2>Lo que el ciclo no cerró por sí mismo</h2>
      <p>De todo el repositorio, agrupado por lo que le pide a quien lee y no por el campo del esquema. <span class="orden-nota" data-orden-nota="antiguo">Dentro de cada grupo, lo más viejo arriba, porque es lo más olvidado.</span><span class="orden-nota" data-orden-nota="reciente" hidden>Dentro de cada grupo, lo más reciente arriba: lo que acaba de quedar abierto.</span> Los hallazgos incorporados no están acá: no son noticia.</p>
    </div>
    {digest}
    <div class="nota"><b>El artefacto no registra cierres.</b> Una deuda anotada hace un mes y una de ayer se ven
      igual, porque nada en el formato dice que algo se saldó después. Lo que sigue es lo declarado abierto en su
      momento, sin evidencia posterior de cierre; no una lista de pendientes vigentes. Es un hueco conocido del
      esquema (issue #6), y este informe existe en parte para hacerlo visible.</div>
    {_now(model)}
    <div class="tools">
      <div class="conmutador" role="group" aria-label="Orden de la lista">
        <span>orden</span>
        <button type="button" id="o-antiguo" data-orden="antiguo" aria-pressed="true">más antiguo primero</button>
        <button type="button" id="o-reciente" data-orden="reciente" aria-pressed="false">más reciente primero</button>
      </div>
    </div>
    {groups}
    {empty}"""


def _reviewer_field(d: dict, key: str, names: dict, missing: str) -> str:
    parts = []
    for r in d["reviewers"]:
        value = r.get(key)
        if value:
            parts.append(E(names.get(value, value)))
        else:
            parts.append(f'<span class="mudo">{E(missing)} en {E(d["schema"].replace("residue/", ""))}</span>')
    return " / ".join(parts) or '<span class="mudo">sin revisores declarados</span>'


def _finding_block(f: dict) -> str:
    d = f["decl"]
    is_open = f["state"] not in CLOSED_STATES
    title = (f'<h4>{E(f["title"])}</h4>' if f["title"]
             else '<h4 class="mudo">Sin título: perfil minimizado</h4>')
    if f["location"]:
        where = f'<div class="ruta">{E(f["location"])}</div>'
    elif d["schema"].endswith("v0.2"):
        where = '<div class="ruta gris">v0.2 no registra ubicaciones</div>'
    elif d["profile"] == "minimized":
        where = '<div class="ruta gris">sin ubicación: perfil minimizado</div>'
    else:
        where = ""
    if f["description"]:
        body = f"<p>{E(f['description'])}</p>"
    elif d["profile"] == "minimized":
        body = '<p class="mudo">Sin descripción: perfil minimizado.</p>'
    else:
        body = ""
    fields = []
    if f["against"]:
        fields.append(f'<div class="campo"><b>verificado contra {E(AGAINST_NAME.get(f["against"], f["against"]))}</b>'
                      f'{E(f["detail"] or "")}</div>')
    if f["remedy_adjustment"]:
        fields.append(f'<div class="campo"><b>ajuste del remedio</b>{E(f["remedy_adjustment"])}</div>')
    if f["risk_record"]:
        fields.append(f'<div class="campo"><b>riesgo aceptado</b>{E(f["risk_record"])}</div>')
    if f["debt_id"]:
        fields.append(f'<div class="campo"><b>deuda</b><span class="ruta">{_link(f["debt_id"])}</span></div>')
    if f["fix_type"]:
        fields.append(f'<div class="campo"><b>corrección verificada por '
                      f'{E(FIX_TYPE_NAME.get(f["fix_type"], f["fix_type"]))}</b>{E(f["fix_reference"] or "")}</div>')
    if f["evidence_link"]:
        fields.append(f'<div class="campo"><b>evidencia</b>{_link(f["evidence_link"])}</div>')
    if f["evidence_hash"]:
        fields.append(f'<div class="campo"><b>evidencia (hash)</b><span class="ruta">{E(f["evidence_hash"])}</span></div>')
    return (f'<div class="halla"><div class="cab"><span class="id">{E(f["id"])}</span>{_meter(f["severity"])}'
            f'{title}<span class="etq{" abierto" if is_open else ""}">{E(STATE_NAME.get(f["state"], f["state"]))}</span>'
            f'</div>{where}{body}{"".join(fields)}</div>')


def _search_text(d: dict) -> str:
    parts = [d["event_id"], d["head"], d["base"] or "", d["file"], d["generator"]["model"], d["schema"],
             d["repository"], d["pr"] or ""]
    parts += [f"{r['model']} {r['family']}" for r in d["reviewers"]]
    parts += [f"{f['title'] or ''} {f['description'] or ''} {f['location'] or ''} {f['debt_id'] or ''}"
              for f in d["findings"]]
    parts += [f"{CLASS_NAME.get(it['class'], it['class'])} {it['description'] or ''}" for it in d["items"]]
    return " ".join(p for p in parts if p).lower()


def _declaration_block(d: dict, model: Model) -> str:
    attention = sum(1 for it in d["items"] if it["attention"])
    closed = [f for f in d["findings"] if f["state"] in CLOSED_STATES]
    alive = [f for f in d["findings"] if f["state"] not in CLOSED_STATES]
    total = d["counts"].get("total_findings")
    total = total if isinstance(total, int) else len(d["findings"])
    if d["absence"]:
        summary = "<b>Ausencia de residuo declarada.</b>"
    else:
        n = len(d["items"])
        summary = (f'<b>{n}</b> {"ítem" if n == 1 else "ítems"} de residuo'
                   + (f", {attention} con atención humana" if attention else ""))
    reviewers = ", ".join(f"{r['model']} ({r['family']})" for r in d["reviewers"])
    confinement = " / ".join(
        E(CONFINEMENT_NAME.get(r["confinement"], r["confinement"] or "no declarado"))
        + (' <span class="mudo">· sin verificar</span>' if r["confinement_verified"] is not True else " · verificado")
        for r in d["reviewers"]
    ) or '<span class="mudo">sin revisores declarados</span>'
    ficha = [
        ("Generador", f'{E(d["generator"]["model"])} <span class="mudo">({E(d["generator"]["family"])})</span>'),
        ("Revisor", _short(reviewers, 70) if reviewers else '<span class="mudo">sin revisores declarados</span>'),
        ("Confinamiento", confinement),
        ("Independencia", _reviewer_field(d, "independence", INDEPENDENCE_NAME, "no declarada")),
        ("Endurecimiento", _reviewer_field(d, "hardening", HARDENING_NAME, "no declarado")),
        ("Árbitro humano", "presente" if d["arbiter"] else "AUSENTE"),
        ("Commit", E(d["head"][:10]) + (f' <span class="mudo">sobre</span> {E(d["base"][:10])}' if d["base"] else "")),
    ]
    if d["pr"]:
        ficha.append(("PR", _link(d["pr"], re.sub(r"^https?://(www\.)?github\.com/", "", d["pr"]))))
    ficha.append(("Repositorio", _short(d["repository"], 40)))
    profile = E(d["profile"])
    if d["profile"] == "minimized":
        profile += ' <span class="mudo">· sin títulos, descripciones ni ubicaciones por diseño</span>'
    ficha.append(("Perfil", profile))
    if d["abbreviated"]:
        ficha.append(("Ruta abreviada", f'usada: {E(d["abbreviated_justification"] or "sin justificación registrada")}'))
    ficha.append(("Artefacto", E(d["file"])))
    ficha_html = "".join(f"<div><dt>{E(k)}</dt><dd>{v}</dd></div>" for k, v in ficha)

    if d["absence"]:
        residue = f'<p class="ausencia">{E(d["declaration"] or "")}</p>'
    else:
        residue = "".join(_item_row(it, model) for it in d["items"]) or '<div class="vacio">Sin ítems.</div>'
    alive_html = ""
    if alive:
        alive_html = '<h4 class="sub">Hallazgos que no cerraron</h4>' + "".join(_finding_block(f) for f in alive)
    closed_html = ""
    if closed:
        incorporated = sum(1 for f in closed if f["state"] == "incorporated")
        closed_html = (f'<details class="cerrados"><summary>{len(closed)} hallazgos cerrados por el ciclo '
                       f'({incorporated} incorporados, {len(closed) - incorporated} refutados verificables): '
                       f'mostrar</summary>{"".join(_finding_block(f) for f in closed)}</details>')
    return (
        f'<details class="decl{" abierta" if attention else ""}" id="d-{E(d["event_id"])}" '
        f'data-q="{E(_search_text(d))}" data-atencion="{1 if attention else 0}">'
        f'<summary><span class="fecha">{E(_fmt_date(d))} {E(_fmt_time(d))}</span>'
        f'<span class="etq plana compuerta">{E(GATE_NAME.get(d["gate"], d["gate"]))} · nivel {E(d["level"])}</span>'
        f'<span class="resumen">{summary} {_latest_tag(d, model)}</span>'
        f'<span class="cifras">{total} hallazgos · {E(d["schema"].replace("residue/", ""))}</span></summary>'
        f'<div class="detalle"><dl class="ficha">{ficha_html}</dl>'
        f'<h4 class="sub">Residuo</h4>{residue}{alive_html}{closed_html}</div></details>'
    )


def render_declarations(model: Model) -> str:
    n = len(model.declarations)
    heading = "La declaración" if n == 1 else f"Las {n} declaraciones"
    blocks = "".join(_declaration_block(d, model) for d in model.declarations)
    if not blocks:
        blocks = '<div class="vacio">Sin declaraciones.</div>'
    return f"""
    <div class="intro"><h2>{heading}</h2>
      <p>De la más reciente a la más vieja. Dentro de cada una el residuo va primero; los hallazgos cerrados se
      despliegan sólo si los pedís.</p></div>
    <div class="tools">
      <label class="buscar"><span>buscar</span>
        <input type="search" id="q" placeholder="título, archivo, commit, modelo, deuda" autocomplete="off"></label>
      <button type="button" class="filtro" id="f-atencion" aria-pressed="false">sólo con atención humana</button>
    </div>
    <div id="lista">{blocks}</div>
    <div class="vacio" id="sin-coincidencia" hidden>Ninguna declaración coincide.</div>"""


def _stacked_bar(segments: list[tuple[str, int, str]], total: int) -> str:
    width, height, gap = 600.0, 34, 2.0
    x = 0.0
    rects = []
    for name, value, token in segments:
        w = max(0.0, (value / total) * width - gap)
        rects.append(f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="{height}" rx="1" '
                     f'style="fill:var(--{token})"><title>{E(name)}: {value}</title></rect>')
        x += w + gap
    return (f'<svg viewBox="0 0 {width:.0f} {height}" role="img" aria-label="reparto de los {total} hallazgos '
            f'por estado terminal" preserveAspectRatio="none" style="height:34px">{"".join(rects)}</svg>')


def _day_bars(days: list[dict]) -> str:
    width, height, pad = 900.0, 132.0, 18
    top = max((d["findings"] for d in days), default=0) or 1
    step = width / len(days)
    bar = max(3.0, min(16.0, step - 3))
    parts = [f'<line x1="0" y1="{height}" x2="{width}" y2="{height}" style="stroke:var(--line-soft)" stroke-width="1"/>']
    for i, d in enumerate(days):
        h = max(2.0, (d["findings"] / top) * (height - 8)) if d["findings"] else 0.0
        x = i * step + (step - bar) / 2
        label = (f'{d["day"].strftime("%d/%m/%Y")}: {d["declarations"]} declaraciones, {d["findings"]} hallazgos'
                 + (f', {d["attention"]} ítems con atención humana' if d["attention"] else ""))
        mark = ""
        if h:
            token = "open" if d["attention"] else "mark-2"
            mark = (f'<rect x="{x:.1f}" y="{height - h:.1f}" width="{bar:.1f}" height="{h:.1f}" rx="1" '
                    f'style="fill:var(--{token})"/>')
        dot = f'<circle cx="{i * step + step / 2:.1f}" cy="{height + 6}" r="1.6" style="fill:var(--ink-3)"/>' if d["declarations"] else ""
        parts.append(f'<g><rect x="{i * step:.1f}" y="0" width="{step:.1f}" height="{height}" fill="transparent">'
                     f'<title>{E(label)}</title></rect>{mark}{dot}</g>')
    parts.append(f'<text x="0" y="{height + pad}" font-size="10" style="fill:var(--ink-3);font-family:var(--mono)">'
                 f'{days[0]["day"].strftime("%d/%m/%Y")}</text>')
    parts.append(f'<text x="{width}" y="{height + pad}" font-size="10" text-anchor="end" '
                 f'style="fill:var(--ink-3);font-family:var(--mono)">{days[-1]["day"].strftime("%d/%m/%Y")}</text>')
    return (f'<svg viewBox="0 0 {width:.0f} {height + pad:.0f}" role="img" aria-label="hallazgos por día">'
            f'{"".join(parts)}</svg>')


def _file_bars(rows: list[tuple[str, int]]) -> str:
    top = rows[0][1] if rows else 1
    cells = []
    for i, (name, n) in enumerate(rows):
        cells.append(f'<span class="n" title="{E(name)}">{E(name)}</span>'
                     f'<span class="b{" alto" if i < 3 else ""}"><i style="--w:{(n / top) * 100:.1f}%"></i></span>'
                     f'<span class="v">{n}</span>')
    return f'<div class="barras">{"".join(cells)}</div>'


def render_corpus(model: Model) -> str:
    c = model.counts
    total = c.get("total", 0)
    segments = [(name, c.get(key, 0), token) for key, name, token in (
        ("incorporated", "Incorporado", "mark"),
        ("refuted_verifiable", "Refutado verificable", "mark-3"),
        ("debt_recorded", "Deuda registrada", "o2"),
        ("owner_decision", "Decisión del dueño", "o3"),
        ("escalated_open", "Escalado abierto", "o1"),
        ("refuted_interpretive", "Refutado interpretativo", "o4"),
    ) if c.get(key, 0)]
    legend = "".join(f'<span><i style="background:var(--{token})"></i>{E(name)} <b>{value}</b></span>'
                     for name, value, token in segments)
    items = sum(len(d["items"]) for d in model.declarations)
    n = len(model.declarations)
    if model.minimized:
        location_note = " (el perfil minimizado no la lleva por diseño)"
    elif model.without_location:
        location_note = " (casi todos de v0.2, que no la traía)"
    else:
        location_note = ""
    files_html = _file_bars(model.by_file) if model.by_file else (
        '<div class="vacio">Ninguna ubicación declarada: en el perfil minimizado este mapa no existe, '
        'y el informe lo dice en vez de dejar el hueco.</div>')
    reviewers = "".join(
        f'<tr><td>{E(family)}</td><td class="ruta">{_short(model_name, 54)}</td><td class="num">{count}</td></tr>'
        for (family, model_name), count in model.reviewers
    )
    versions = "".join(
        f'<tr><td class="ruta" style="white-space:nowrap">{E(schema)}</td><td class="num">{count}</td>'
        f'<td class="gris">{E(note)}</td></tr>'
        for schema, count, note in model.versions
    )
    noun = "declaración" if n == 1 else "declaraciones"
    unit_name = UNIT_NAME.get(model.unit, "día")
    if model.unit == "sparse":
        series_help = ("Sólo los días con declaraciones: el rango es demasiado amplio para un eje continuo. "
                       "Altura: hallazgos de ese día. Ámbar: días que dejaron residuo con atención humana.")
    else:
        series_help = (f"Altura: hallazgos de ese {unit_name}. Ámbar: los que dejaron residuo con atención "
                       f"humana. El punto de abajo marca los que tienen declaración.")
    stacked = _stacked_bar(segments, total) if total else '<div class="vacio">Sin hallazgos declarados.</div>'
    days = _day_bars(model.by_day) if model.by_day else '<div class="vacio">Sin fechas legibles.</div>'
    return f"""
    <div class="intro"><h2>El corpus</h2>
      <p>{total} hallazgos declarados y {items} ítems de residuo en {n} {noun}.
      Los números describen el registro, no la calidad del código. Los conteos son los que cada declaración
      declara; no se recalculan.</p></div>
    <div class="rejilla">
      <div class="panel">
        <h3>Estado terminal de los {total} hallazgos</h3>
        <p class="ayuda">Cada hallazgo que levantó el revisor terminó en uno de seis estados. En ámbar, los cuatro
          que no cierran solos y pasan a residuo. Los incorporados van en gris: son cobertura, no un sello.</p>
        <figure>{stacked}</figure>
        <div class="leyenda">{legend}</div>
      </div>
      <div class="panel">
        <h3>Hallazgos por {unit_name}</h3>
        <p class="ayuda">{series_help}</p>
        <figure>{days}</figure>
      </div>
      <div class="panel p-7">
        <h3>Dónde se concentran</h3>
        <p class="ayuda">Aproximado: <code>location</code> es texto libre y a veces nombra más de un archivo.
          {model.without_location} hallazgos no registran ubicación{E(location_note)}.</p>
        {files_html}
      </div>
      <div class="panel p-5">
        <h3>Quién revisó</h3>
        <p class="ayuda">La regla R4 exige que la independencia declarada coincida con las familias declaradas.
          El modelo es lo que el operador declaró; el informe no puede probarlo.</p>
        <div class="tabla-scroll"><table><thead><tr><th>Familia</th><th>Modelo</th><th class="num">Decl.</th></tr></thead>
          <tbody>{reviewers}</tbody></table></div>
      </div>
      <div class="panel p-5">
        <h3>Versiones del esquema</h3>
        <p class="ayuda">Conviven en el mismo directorio. Las viejas se leen; no se emiten.</p>
        <div class="tabla-scroll"><table><thead><tr><th>Esquema</th><th class="num">Decl.</th><th>Qué falta al leerlas</th></tr></thead>
          <tbody>{versions}</tbody></table></div>
      </div>
    </div>"""


# ---------------------------------------------------------------------------
# The board: for whoever coordinates, not for whoever reviews. What is waiting
# on someone and since when, and whether the process was followed as declared.
# Nothing here scores the code or the people: every number is a count of what
# the declarations say, and the page opens with the limit that none of it
# records a closure.
# ---------------------------------------------------------------------------
def _tile(label: str, value: str, note: str, hero: bool = False, open_: bool = True) -> str:
    classes = "cifra" + (" hero" if hero else "") + (" abierta" if open_ else "")
    return (f'<div class="{classes}"><span class="rotulo">{E(label)}</span><span class="valor">{value}</span>'
            f'<span class="nota-cifra">{note}</span></div>')


def _board_title(r: dict) -> str:
    """What a row of the board is about: a finding by its title, an item by
    the title of the finding it points at, or else by its class."""
    if r["kind"] == "finding":
        return r["title"] or "Sin título: perfil minimizado"
    origin = _referenced_finding(r)
    if origin is not None and origin["title"]:
        return origin["title"]
    return CLASS_NAME.get(r["class"], r["class"])


def _board_text(r: dict) -> str:
    if r["kind"] == "finding":
        return r["risk_record"] or r["description"] or ""
    return r["description"] or ""


def _board_when(d: dict) -> str:
    return f'<td class="fecha">{E(_fmt_date(d))}{_age_span(d)}</td>'


def _board_origin(d: dict) -> str:
    return _decl_ref(d) + (f' · {_link(d["pr"], "PR")}' if d["pr"] else "")


def _board_decisions(rows: list) -> str:
    if not rows:
        return '<div class="vacio">Ninguna escalación sin decisión en todo el registro.</div>'
    trs = []
    for r in rows:
        d = r["decl"]
        since = f' data-desde="{E(_iso(d))}"' if d["date"] else ""
        trs.append(f'<tr{since}>{_board_when(d)}<td><div class="tit">{E(_board_title(r))}</div>'
                   f'<div class="txt">{E(_cut(_board_text(r), 240))}</div></td>'
                   f'<td class="ref">{_board_origin(d)}</td></tr>')
    chips = ('<div class="tools chips">'
             '<span class="chip abierta">más de 30 días · <b data-corte="30"></b></span>'
             '<span class="chip">7 a 30 días · <b data-corte="7"></b></span>'
             '<span class="chip">menos de 7 días · <b data-corte="0"></b></span></div>')
    return (f'{chips}<div class="tabla-scroll"><table><thead><tr><th>Declarado</th><th>Qué hay que decidir</th>'
            f'<th>Origen</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')


def _board_debts(rows: list) -> str:
    if not rows:
        return '<div class="vacio">Ninguna deuda registrada.</div>'
    trs = []
    for f in rows:
        d = f["decl"]
        ref = _link(f["debt_id"], _cut(f["debt_id"], 46)) if f["debt_id"] else '<span class="mudo">sin debt_id</span>'
        trs.append(f'<tr>{_board_when(d)}<td><div class="tit">{E(f["title"] or "Sin título: perfil minimizado")}</div></td>'
                   f'<td class="ref">{ref}</td><td class="ref">{_decl_ref(d)}</td></tr>')
    return (f'<div class="tabla-scroll"><table><thead><tr><th>Declarado</th><th>Qué se debe</th><th>Referencia</th>'
            f'<th>Origen</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')


def _board_accepted(rows: list) -> str:
    if not rows:
        return '<div class="vacio">Ningún riesgo aceptado por el dueño.</div>'
    trs = []
    for f in rows:
        d = f["decl"]
        trs.append(f'<tr>{_board_when(d)}<td><div class="tit">{E(f["title"] or "Sin título: perfil minimizado")}</div>'
                   f'<div class="txt">{E(_cut(f["risk_record"] or "", 240))}</div></td>'
                   f'<td class="ref">{_decl_ref(d)}</td></tr>')
    return (f'<div class="tabla-scroll"><table><thead><tr><th>Declarado</th><th>Riesgo y decisión</th><th>Origen</th>'
            f'</tr></thead><tbody>{"".join(trs)}</tbody></table></div>')


def _gauge(name: str, note: str, n: int, total: int) -> str:
    """One row of the process panel: a count over its denominator, the fill
    in the neutral mark and the track a lighter step of the same ramp. Not
    the severity meter, which is `_meter`."""
    pct = (n / total * 100) if total else 0.0
    small = f"<small>{E(note)}</small>" if note else ""
    return (f'<div class="medidor"><div class="n">{E(name)}{small}</div>'
            f'<div class="b"><i style="--w:{pct:.0f}%"></i></div><div class="v">{n} de {total}</div></div>')


def _board_health(h: dict) -> str:
    n = h["events"]
    if not n:
        return '<div class="vacio">Sin declaraciones.</div>'

    def missing(declared: int) -> str:
        k = n - declared
        if not k:
            return "todas las declaraciones lo traen"
        return f'{k} {"declaración no trae" if k == 1 else "declaraciones no traen"} el campo (v0.2 y v0.3)'

    return "".join([
        _gauge("Revisor de otra familia", missing(h["independence_declared"]), h["cross_family"], h["independence_declared"]),
        _gauge("Endurecimiento del revisor verificado", missing(h["hardening_declared"]), h["hardening_verified"], h["hardening_declared"]),
        _gauge("Confinamiento verificado", "git status limpio después de la ronda", h["confinement_verified"], n),
        _gauge("Árbitro humano presente", "", h["arbiter"], n),
        _gauge("Ausencia de residuo declarada", "eventos sin ítems, con declaración expresa", h["absence"], n),
    ])


def _bucket_label(day: date, unit: str, short: bool = False) -> str:
    if unit == "week":
        week = day.isocalendar()[1]
        return f"S{week}" if short else f"semana {week}, desde el {day.strftime('%d/%m/%Y')}"
    if unit == "month":
        return day.strftime("%m/%Y")
    if unit == "year":
        return day.strftime("%Y")
    return day.strftime("%d/%m") if short else day.strftime("%d/%m/%Y")


def _board_columns(series: list[dict], unit: str) -> str:
    if not series:
        return '<div class="vacio">Sin fechas legibles.</div>'
    top = max(s["declarations"] for s in series) or 1
    peak = max(range(len(series)), key=lambda i: series[i]["declarations"])
    last = len(series) - 1
    cols = []
    for i, s in enumerate(series):
        n = s["declarations"]
        label = f'{_bucket_label(s["day"], unit)}: {n} {"declaración" if n == 1 else "declaraciones"}'
        shown = n if n and i in (peak, last) else ""
        cols.append(f'<div class="col{" alto" if n and i == peak else ""}" title="{E(label)}">'
                    f'<b>{shown}</b><i style="--h:{(n / top) * 100:.0f}%"></i></div>')
    guides = f'<div class="guia" style="bottom:calc(100% - 4px)"><span>{top}</span></div>'
    if top >= 4:
        guides += f'<div class="guia" style="bottom:calc(50% - 2px)"><span>{top / 2:g}</span></div>'
    grid = f"grid-template-columns:repeat({len(series)},1fr)"
    if len(series) <= 16:
        axis = (f'<div class="eje" style="{grid}">'
                + "".join(f'<span>{E(_bucket_label(s["day"], unit, short=True))}</span>' for s in series) + "</div>")
    else:
        axis = (f'<div class="eje dos"><span>{E(_bucket_label(series[0]["day"], unit, short=True))}</span>'
                f'<span>{E(_bucket_label(series[-1]["day"], unit, short=True))}</span></div>')
    return f'<div class="columnas" style="{grid}">{guides}{"".join(cols)}</div>{axis}'


def _board_gaps(rows: list[tuple[str, str, int]], total: int) -> str:
    if not rows:
        return '<div class="vacio">Ningún hueco de ejecución declarado.</div>'
    top = rows[0][2] or 1
    cells = "".join(
        f'<span class="n">{E(name)}</span><span class="b{" alto" if i == 0 else ""}" title="{n} de {total}">'
        f'<i style="--w:{(n / top) * 100:.1f}%"></i></span><span class="v">{n}</span>'
        for i, (_, name, n) in enumerate(rows)
    )
    return f'<div class="barras">{cells}</div>'


def _coverage_tile(c) -> str:
    """The fourth figure: merges that demanded a review and carry no anchored
    declaration, over the merges that demanded one. Never a made-up number:
    without a branch to walk, or with the gate not required, the tile says so."""
    if c is None or c.error:
        return _tile("Merges sin declaración", '<small>sin calcular</small>',
                     "La vista no tuvo una rama que recorrer; el panel dice por qué." if c is None
                     else f"No se pudo recorrer la rama: {E(c.error)}.", open_=False)
    if not c.required:
        return _tile("Merges sin declaración", '<small>no exigida</small>',
                     f"La política de la punta declara gate.required=false. {c.merges} merges en el período, "
                     f"{c.covered} con una declaración anclada.", open_=False)
    n = len(c.uncovered)
    note = (f"De los merges de {E(c.ref)} que exigían revisión desde el commit que trajo la primera declaración válida. "
            + (f"Los otros {c.covered} tienen una declaración anclada a un commit del PR." if c.covered
               else "Ninguno tiene una declaración anclada a un commit del PR." if n else "Ningún merge exigió revisión."))
    return _tile("Merges sin declaración", f'{n}<small>de {c.merges}</small>', note, open_=bool(n))


def _board_coverage(c) -> str:
    if c is None:
        return ('<div class="vacio">Sin calcular: el informe no tuvo una rama que recorrer. El gate la recibe de '
                'la base del PR y el comando de <code>--branch</code>, que por defecto es HEAD.</div>')
    if c.error:
        return f'<div class="vacio">Sin calcular: {E(c.error)}.</div>'
    where = f"{E(c.ref)} <code>{E(c.tip[:7])}</code>"
    since = E(c.since.strftime("%d/%m/%Y")) if c.since else "fecha ilegible"
    opened = f"<code>{E(c.since_oid[:7])}</code>, el primero que trajo una declaración válida ({since})"
    policy = (f"la política por defecto del gate, porque la punta no tiene <code>{E(c.config_path)}</code>"
              if c.policy_default else f"la política de <code>{E(c.config_path)}</code> en la punta, la de hoy")
    intro = (f'<p class="ayuda">Historia first-parent de {where}, desde el commit {opened}. Cada merge se juzga como '
             f'el gate juzgó su PR, con {policy} y las mismas funciones del gate: exige revisión según su '
             f'clasificación de rutas, y está cubierto cuando la declaración que el PR agregó pasa las '
             f'comprobaciones por artefacto (identidad y unicidad G8, nivel G2 y G3, confinamiento G4, pertenencia '
             f'G5) y cubre cada ruta exigente en su estado final con el árbol integrado visto (G6 y G7). No se aplica '
             f'G9, la versión vigente del esquema: una versión anterior era la vigente cuando un merge viejo ocurrió. '
             f'Son las compuertas de hoy: un merge anterior a una de ellas puede figurar sin declaración admisible '
             f'aunque el gate de su momento lo haya aprobado. Mide declaraciones, no corridas del gate: el '
             f'repositorio no guarda el veredicto de ninguna corrida.</p>')
    if not c.required:
        body = (f'<div class="vacio">La política de la punta declara <code>gate.required=false</code>: no exige '
                f'cobertura. {c.merges} merges en el período, {c.covered} con una declaración anclada.</div>')
    elif not c.uncovered:
        body = (f'<div class="vacio">Los {c.merges} merges que exigían revisión tienen una declaración anclada.</div>'
                if c.merges else '<div class="vacio">Ningún merge exigió revisión en el período.</div>')
    else:
        trs = []
        for row in c.uncovered:
            marks = ""
            if row["mutations"]:
                marks += f' <span class="etq abierto">muta evidencia: {row["mutations"]}</span>'
            if row["code"] == "no_common_gate":
                marks += ' <span class="etq abierto">sin compuerta común</span>'
            if row["code"] == "octopus":
                marks += ' <span class="etq abierto">octopus</span>'
            reason = f'<div class="txt">{E(_cut(row.get("reason") or "", 160))}</div>' if row.get("reason") else ""
            trs.append(f'<tr><td class="fecha">{E(row["date"].strftime("%d/%m/%Y"))}</td>'
                       f'<td class="ref">{E(row["oid"][:8])}</td>'
                       f'<td><div class="tit">{E(_cut(row["subject"], 80))}</div>{reason}</td>'
                       f'<td class="num">{row["demanding"]}</td><td>{marks}</td></tr>')
        body = (f'<div class="tabla-scroll"><table><thead><tr><th>Fecha</th><th>Merge</th><th>Asunto y por qué</th>'
                f'<th class="num">Rutas</th><th></th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')
    notes = []
    if c.invalid:
        notes.append(f"{c.invalid} {'archivo' if c.invalid == 1 else 'archivos'} bajo la evidencia en la punta no "
                     f"{'valida' if c.invalid == 1 else 'validan'} y no {'cuenta' if c.invalid == 1 else 'cuentan'} "
                     f"como declaración")
    if c.exempt:
        notes.append(f"{c.exempt} {'merge exento' if c.exempt == 1 else 'merges exentos'} por la política")
    if c.before:
        notes.append(f"{c.before} {'anterior' if c.before == 1 else 'anteriores'} al commit que abre el período, fuera del recuento")
    if c.mutated:
        notes.append(f"{c.mutated} {'modificó' if c.mutated == 1 else 'modificaron'} evidencia ya presente (G8)")
    if c.truncated:
        notes.append(f"historia leída hasta un tope de {MAX_HISTORY_NOTE} commits: el recuento es parcial")
    notes_html = f'<p class="ayuda" style="margin:12px 0 0">{E(". ".join(notes))}.</p>' if notes else ""
    d = c.direct_demanding
    direct = (f'<p class="ayuda" style="margin:12px 0 0"><b>Commits directos:</b> {d} sin merge que '
              f'{"exigía" if d == 1 else "exigían"} revisión, {c.direct_with_declaration} de ellos agregan una '
              f'declaración, {c.direct_exempt} exentos. Un push directo no pasa por el gate, y con squash merge cada '
              f'PR es un commit directo cuya declaración ancla a un commit que no está en la rama: no se cuentan '
              f'como cubiertos ni como faltantes.</p>')
    if c.direct_recent:
        lis = "".join(f'<tr><td class="fecha">{E(r["date"].strftime("%d/%m/%Y"))}</td><td class="ref">{E(r["oid"][:8])}</td>'
                      f'<td><div class="tit">{E(_cut(r["subject"], 80))}</div></td>'
                      f'<td class="ref">{"declara" if r["declares"] else ""}</td></tr>' for r in c.direct_recent)
        direct += f'<div class="tabla-scroll"><table><tbody>{lis}</tbody></table></div>'
    return intro + body + notes_html + direct


MAX_HISTORY_NOTE = 2000


def render_board(model: Model, coverage=None) -> str:
    groups = {key: rows for key, _, _, rows in model.open_groups}
    decisions, debts, accepted = groups["decision"], groups["debt"], groups["accepted"]
    oldest = _oldest(groups, ["decision"])
    n = len(decisions)
    decisions_note = (f"La más vieja, declarada el {E(_fmt_date(oldest))}{_age_span(oldest)}."
                      if oldest else "Ninguna escalación sin decisión.")
    k = len(debts)
    with_link = sum(1 for f in debts if f["debt_id"] and _SCHEME.match(str(f["debt_id"])))
    debts_note = ("Sin evidencia de pago. " + (f"{with_link} con enlace, {k - with_link} con etiqueta a mano."
                                              if k else "Ninguna registrada."))
    g = model.gaps_total
    unstated = sum(x for key, _, x in model.gaps_by_reason if key in ("other", "unstated"))
    gaps_note = (f"{model.gaps_attention} {'pide' if model.gaps_attention == 1 else 'piden'} atención humana. "
                 + (f"{unstated} sin motivo específico: el vocabulario no alcanza para ver recurrencia." if unstated else ""))
    unit_name = UNIT_NAME.get(model.week_unit, "semana")
    weeks_help = ("Semanas ISO. Cada declaración es un evento de revisión." if model.week_unit == "week"
                  else f"Por {unit_name}: el rango es demasiado amplio para semanas.")
    h = model.health
    branch_name = E(coverage.ref) if coverage is not None else "la rama"
    return f"""
    <div class="intro">
      <h2>Qué está esperando a alguien, y si el proceso se cumple</h2>
      <p>Para quien coordina, no para quien revisa. Nada de esta vista puntúa el código ni a las personas: cuenta lo que las declaraciones dicen del proceso y lista lo que pide una decisión. Las edades se calculan al abrir la página.</p>
    </div>
    <div class="cifras">
      {_tile("Esperan una decisión", str(n), decisions_note, hero=True)}
      {_tile("Deudas anotadas", str(k), E(debts_note))}
      {_coverage_tile(coverage)}
      {_tile("Huecos de ejecución", str(g), E(gaps_note), open_=False)}
    </div>
    <div class="nota fuerte"><b>El artefacto no registra cierres.</b> Todo lo listado abajo está declarado abierto en su
      momento, sin evidencia posterior de cierre: una deuda saldada fuera del registro sigue figurando, y esta vista no
      puede saberlo. No es una lista de pendientes vigentes. Es un hueco conocido del esquema (issue #66).</div>
    <div class="rejilla">
      <section class="panel p-7">
        <div class="panel-cab"><h3>Decisiones esperando</h3><span class="c">{n}</span></div>
        <p class="ayuda">Escalaciones sin decisión, la más vieja arriba. Un hallazgo escalado y su ítem de residuo son una fila.</p>
        {_board_decisions(decisions)}
      </section>
      <section class="panel p-5">
        <div class="panel-cab"><h3>Merges sin declaración en {branch_name}</h3><span class="c">{len(coverage.uncovered) if coverage is not None and not coverage.error else ""}</span></div>
        {_board_coverage(coverage)}
      </section>
    </div>
    <div class="rejilla">
      <section class="panel p-7">
        <div class="panel-cab"><h3>Deuda anotada</h3><span class="c">{k}</span></div>
        <p class="ayuda">Hallazgos válidos y diferidos. Un <code>debt_id</code> que es URL se enlaza; una etiqueta escrita a mano no la resuelve ningún sistema.</p>
        {_board_debts(debts)}
      </section>
      <section class="panel p-5">
        <div class="panel-cab"><h3>Riesgos aceptados por el dueño</h3><span class="c">{len(accepted)}</span></div>
        <p class="ayuda">Quién aceptó qué, leído del registro de riesgo de cada hallazgo. Es el único lugar donde el artefacto nombra a alguien, y es una decisión, no un puntaje.</p>
        {_board_accepted(accepted)}
      </section>
    </div>
    <div class="rejilla">
      <section class="panel p-6">
        <div class="panel-cab"><h3>Salud del proceso de revisión</h3><span class="c">{h["events"]} eventos</span></div>
        <p class="ayuda">Lo que cada declaración dice de cómo se revisó. Mide el protocolo, no a las personas; en un repositorio de una sola persona mide a la persona, y hay que leerlo así.</p>
        {_board_health(h)}
      </section>
      <section class="panel p-6">
        <div class="panel-cab"><h3>Declaraciones por {E(unit_name)}</h3><span class="c">{h["events"]}</span></div>
        <p class="ayuda">{E(weeks_help)}</p>
        {_board_columns(model.by_week, model.week_unit)}
      </section>
    </div>
    <div class="rejilla">
      <section class="panel p-6">
        <div class="panel-cab"><h3>Huecos de ejecución por motivo</h3><span class="c">{g}</span></div>
        <p class="ayuda">Todo lo que ninguna ronda pudo arbitrar por ejecución, con y sin atención humana. Con tres motivos en el vocabulario, "otro" se lleva casi todo y la recurrencia queda en el texto libre, donde ningún programa la lee (issues #51 a #53).</p>
        {_board_gaps(model.gaps_by_reason, g)}
      </section>
      <section class="panel p-6">
        <div class="panel-cab"><h3>Lo que esta vista no puede decir</h3></div>
        <p class="ayuda">Todo lo de arriba sale de los campos declarados y de los objetos git de la rama. Lo que quien coordina pregunta después necesita esquema o está fuera del registro.</p>
        <div class="tabla-scroll"><table><thead><tr><th>Pregunta</th><th>Qué falta</th></tr></thead><tbody>
          <tr><td><div class="tit">Quién tiene que decidir cada escalación</div></td><td class="txt">Un dueño por ítem. Hoy solo el registro de riesgo y la aceptación de nivel A nombran a alguien.</td></tr>
          <tr><td><div class="tit">Cuándo se cerró, cuánto tardó</div></td><td class="txt">El cierre declarado (issue #66). Sin eso, todo envejece para siempre y la vista no distingue lo saldado de lo olvidado.</td></tr>
          <tr><td><div class="tit">Qué brecha se repite</div></td><td class="txt">Motivos de hueco más finos (issues #51 a #53) y el límite permanente marcado al abrir.</td></tr>
          <tr><td><div class="tit">Si el gate corrió en cada merge</div></td><td class="txt">El repositorio no guarda el veredicto de una corrida, y una declaración anclada no lo prueba. Lo garantiza el required check de la plataforma, y lo verifica el muestreo (issue #96).</td></tr>
          <tr><td><div class="tit">Si lo declarado es lo que pasó</div></td><td class="txt">El muestreo humano de eventos mergeados (issue #96). Esta vista muestra la declaración, no la verdad.</td></tr>
        </tbody></table></div>
      </section>
    </div>"""


def _case_row(f: dict) -> str:
    d = f["decl"]
    detail = ""
    if f["detail"] or f["against"]:
        detail = (f'<div class="txt verificado"><b>Verificado contra '
                  f'{E(AGAINST_NAME.get(f["against"], f["against"] or "nada"))}:</b> {E(f["detail"] or "")}</div>')
    reviewer = d["reviewers"][0]["model"] if d["reviewers"] else ""
    text = " ".join(str(f[k] or "") for k in ("title", "description", "detail", "location")).lower()
    description = f'<div class="txt">{E(f["description"])}</div>' if f["description"] else ""
    where = f'<span>{E(f["location"])}</span>' if f["location"] else ""
    return (f'<div class="fila" data-q="{E(text)}"><div class="cuando">{E(_fmt_date(d))}{_age_span(d)}</div>'
            f'<div class="cuerpo"><div class="tit">{E(f["title"])}</div>{description}{detail}'
            f'<div class="pie">{_meter(f["severity"])}{where}'
            f'<span>revisor <b>{_short(reviewer, 34)}</b></span>{_decl_ref(d)}</div></div></div>')


def render_cases(model: Model) -> str:
    with_text = [f for f in model.cases if f["title"]]
    n = len(model.cases)
    if not with_text:
        if n:
            how_many = "Hay 1 caso" if n == 1 else f"Hay {n} casos"
            empty = (f"{how_many}, pero sin títulos ni descripciones: perfil minimizado. Su texto no sale del "
                     "entorno por diseño; quedan la severidad, el estado y la verificación, en la pestaña "
                     "Declaraciones.")
        else:
            empty = "Ningún hallazgo crítico o mayor fue incorporado todavía."
        body = f'<div class="vacio">{E(empty)}</div>'
        tools = ""
    else:
        rows = "".join(_case_row(f) for f in with_text)
        body = (f'<div id="lista-casos">{rows}</div>'
                '<div class="vacio" id="sin-caso" hidden>Ningún caso coincide.</div>')
        tools = ('<div class="tools"><label class="buscar"><span>buscar</span>'
                 '<input type="search" id="qc" placeholder="filtrar casos" autocomplete="off"></label></div>')
    return f"""
    <div class="intro"><h2>Qué encontró el adversario</h2>
      <p>Los {n} hallazgos críticos y mayores que cambiaron el código, con lo que el generador verificó
      antes de aceptarlos. Es la parte que se puede mostrar sin pedirle a nadie que confíe.</p></div>
    {tools}
    {body}"""


def render_unreadable(model: Model) -> str:
    if not model.unreadable:
        return ""
    rows = "".join(f'<tr><td class="ruta">{E(u.file)}</td><td class="gris">{E(u.reason)}</td></tr>'
                   for u in model.unreadable)
    return (f'<div class="panel"><h3>Archivos que no se pudieron leer</h3>'
            f'<p class="ayuda">El informe lee, no valida: lo único que chequea es que cada archivo parsee y tenga '
            f'la forma de una declaración. Estos no, y el resto siguió.</p>'
            f'<div class="tabla-scroll"><table><tbody>{rows}</tbody></table></div></div>')


@dataclass
class Source:
    """Where the declarations came from, for the footer. Data, never a local path."""
    directory: str                 # the evidence directory as a repo-relative name
    commit: str | None = None      # short sha, when known
    uncommitted: int = 0           # files under the directory that differ from the commit
    since: date | None = None
    total: int | None = None       # declarations before the --since filter


def _footer(model: Model, source: Source) -> str:
    origin = f"<code>{E(source.directory)}</code>"
    if source.commit:
        origin += f" en el commit <code>{E(source.commit)}</code>"
        if source.uncommitted:
            n = source.uncommitted
            origin += f", más {n} {'archivo' if n == 1 else 'archivos'} sin commitear en <code>{E(source.directory)}/</code>"
    since = ""
    if source.since:
        since = (f" · sólo declaraciones desde el {source.since.strftime('%d/%m/%Y')} "
                 f"({len(model.declarations)} de {source.total})")
    return (f"Generado desde {origin}{since} · disensor {E(__version__)}. Este informe lee los artefactos; no "
            f"los valida: la validación la hace la compuerta. Las edades (\"hace N días\") se calculan al abrirlo.")


def _template() -> str:
    return resources.files("disensor").joinpath("report.html").read_text(encoding="utf-8")


def build_html(declarations: list[dict], unreadable: list[Unreadable], source: Source, coverage=None) -> str:
    """The whole page. Markers are replaced in ONE pass over the template, so a
    declaration whose title contains the literal of a marker survives intact.
    `coverage` is what the branch shows (branch.Coverage), computed by whoever
    has a branch to walk; without it the board says the panel was not computed."""
    model = aggregate(declarations, unreadable)
    n = len(model.declarations)
    period = f"{n} {'declaración' if n == 1 else 'declaraciones'}"
    if model.first and model.last:
        period += f" · {model.first.strftime('%d/%m/%Y')} a {model.last.strftime('%d/%m/%Y')}"
    tabs = [("abierto", "Abierto", model.open_total), ("declaraciones", "Declaraciones", n),
            ("corpus", "Corpus", None), ("casos", "Casos", len(model.cases)), ("tablero", "Tablero", None)]
    tabs_html = ""
    for key, label, count in tabs:
        selected = "true" if key == "abierto" else "false"
        badge = f'<span class="n">{count}</span>' if count is not None else ""
        tabs_html += (f'<button class="pestana" role="tab" id="t-{key}" aria-controls="v-{key}" '
                      f'aria-selected="{selected}" data-v="{key}">{E(label)}{badge}</button>')
    repos = " · ".join(_short(r, 44) for r in model.repositories)
    values = {
        "REPO": repos or '<span class="mudo">sin repositorio</span>',
        "PERIODO": E(period),
        "PESTANAS": tabs_html,
        "ABIERTO": render_open(model),
        "DECLARACIONES": render_declarations(model),
        "CORPUS": render_corpus(model),
        "CASOS": render_cases(model),
        "TABLERO": render_board(model, coverage),
        "ILEGIBLES": render_unreadable(model),
        "PIE": _footer(model, source),
    }
    return _MARKER.sub(lambda m: values[m.group(1)], _template())


def write_html(out: Path, page: str) -> None:
    """UTF-8, LF, no BOM: the file has to hash the same on every platform.

    Written next to the destination and moved into place, so a write that
    fails halfway (disk full, interruption) leaves the previous report intact
    instead of a truncated file that is neither the old one nor the new one.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    try:
        tmp.write_bytes(page.replace("\r\n", "\n").encode("utf-8"))
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            tmp.unlink()


def summary_line(declarations: list[dict], unreadable: list[Unreadable], out: Path, prefix: str = "") -> str:
    """What the command (or the gate) prints: the digest of the open view, and
    what the latest declaration left open, so the terminal answers the two
    questions the page opens with. The path is always the LAST line."""
    n = len(declarations)
    groups = {key: rows for key, _, _, rows in open_queue(declarations)}
    total = sum(len(rows) for rows in groups.values())
    lines = []
    if unreadable:
        k = len(unreadable)
        lines.append(f"{prefix}{k} {'file' if k == 1 else 'files'} unreadable, listed in the report")

    def since(d: dict | None) -> str:
        return f" (oldest {d['date'].strftime('%Y-%m-%d')})" if d and d["date"] else ""

    parts = []
    k = len(groups["decision"])
    if k:
        parts.append(f"{k} {'awaits' if k == 1 else 'await'} a decision{since(_oldest(groups, ['decision']))}")
    k = len(groups["debt"])
    if k:
        parts.append(f"{k} {'debt' if k == 1 else 'debts'}{since(_oldest(groups, ['debt']))}")
    k = sum(len(groups[g]) for g in GAP_KEYS)
    if k:
        parts.append(f"{k} execution {'gap' if k == 1 else 'gaps'} with human attention")
    k = len(groups["reviewer"])
    if k:
        parts.append(f"{k} on the reviewer")
    k = len(groups["judgement"])
    if k:
        parts.append(f"{k} resting on judgement")
    k = len(groups["accepted"])
    if k:
        parts.append(f"{k} accepted {'risk' if k == 1 else 'risks'}")
    k = len(groups["other"])
    if k:
        parts.append(f"{k} of a class this report does not know")
    head = f"{prefix}{n} {'declaration' if n == 1 else 'declarations'}"
    lines.append(f"{head}, {total} declared open: {', '.join(parts)}" if total
                 else f"{head}, nothing declared open")
    latest = declarations[0] if declarations else None
    if latest is None:
        lines[-1] += f" -> {out}"
    else:
        m = len(open_rows(latest))
        left = f"{m} {'item' if m == 1 else 'items'}" if m else "nothing"
        lines.append(f"{prefix}the latest declaration ({latest['event_id'][:8]}) left {left} open -> {out}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------
def repo_root(cwd: Path) -> Path:
    """The git root, or the directory itself outside a repository (or without git)."""
    try:
        return gitctx.repo_root(cwd)
    except (gitctx.GitError, OSError):
        return cwd


def resolve_against(raw: str, root: Path) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else root / path


def inside(path: Path, directory: Path) -> bool:
    """Whether `path` falls under `directory`, on canonical paths.

    Both are resolved, so a symlink or a junction to the evidence directory is
    the evidence directory, and `..` and absolute aliases collapse. The output
    may not exist yet: `resolve` canonicalises the parts that do.
    """
    try:
        return path.resolve().is_relative_to(directory.resolve())
    except OSError:
        return False


def branch_of_directory(directory: Path, ref: str, config_path: str = DEFAULT_CONFIG):
    """What the branch of the directory's OWN repository shows, for the board.

    The same provenance rule as the footer: the repository is the one the
    evidence directory lives in, never the one the command runs in. Outside a
    repository there is no branch to walk and the board says so; inside one,
    the coverage is read from the objects at `ref`, never from the working
    tree the command is displaying. `config_path` is the file the gate runs
    with: a repository that runs the gate with `--config` has to name it here
    too, or the board would judge the merges by a policy the gate never read.
    """
    try:
        source_root = gitctx.repo_root(directory)
        rel = directory.resolve().relative_to(source_root.resolve()).as_posix()
    except (gitctx.GitError, OSError, ValueError):
        return None
    from .branch import Coverage, branch_coverage  # branch imports gate, which imports this module
    from .gate import GateFailure, canonical_repo_path
    # The same spelling rules as the gate's --config: backslashes become the
    # separator, and an absolute path, a drive letter or an escape from the
    # repository is refused with the gate's own message, never read raw by git.
    try:
        canonical = canonical_repo_path(config_path, source_root, "--config")
    except GateFailure as exc:
        return Coverage(ref=ref, error=str(exc))
    return branch_coverage(ref, rel, canonical, source_root, label=ref)


def describe_source(directory: Path, since: date | None = None, total: int | None = None) -> Source:
    """The footer's origin for the working-tree reader.

    The commit is the one the directory's OWN repository is at, and the count
    is how far that directory is from it. An absolute `--residue` can point at
    another checkout, and its provenance is that repository's, never the one
    the command runs in; a directory that lives in no repository has no commit
    to name, and the footer names only the directory.
    """
    label = directory.name or str(directory)
    try:
        source_root = gitctx.repo_root(directory)
    except (gitctx.GitError, OSError):
        return Source(directory=label, since=since, total=total)
    try:
        rel = directory.resolve().relative_to(source_root.resolve()).as_posix()
    except ValueError:
        rel = label
    commit = None
    uncommitted = 0
    try:
        commit = gitctx._git(["rev-parse", "--short", "HEAD"], source_root).strip() or None
        status = gitctx.run_git(
            ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", rel], source_root,
        )
        if status.returncode == 0:
            uncommitted = len([f for f in status.stdout.split("\0") if f])
    except (gitctx.GitError, OSError):
        commit = None
    return Source(directory=rel, commit=commit, uncommitted=uncommitted, since=since, total=total)


def tracked_by_git(path: Path) -> bool:
    """Whether git tracks `path` in the repository it lives in. Anything but a clean yes is a no.

    The report is derived and never versioned, so it never overwrites a file
    that is: a mistyped `--out` must not take a tracked file with it.
    """
    parent = path.parent
    if not parent.exists():
        return False
    try:
        root = gitctx.repo_root(parent)
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        r = gitctx.run_git(["ls-files", "--error-unmatch", "--", rel], root)
    except (gitctx.GitError, OSError, ValueError):
        return False
    return r.returncode == 0


def _err(message: str) -> None:
    print(message, file=sys.stderr)


def main_report(args) -> int:
    root = repo_root(Path.cwd())
    directory = resolve_against(args.residue, root)
    out = resolve_against(args.out, root)
    if not directory.is_dir():
        _err(f"report: {directory} is not a directory")
        return MISSING
    if inside(out, directory):
        _err(f"report: --out {out} falls inside the evidence directory {directory}. An HTML there would be "
             "read by the gate as an artifact and rejected; write it anywhere else")
        return NOT_WRITTEN
    if tracked_by_git(out):
        _err(f"report: --out {out} is a file git tracks, so it was not written: the report is derived and "
             "never versioned")
        return NOT_WRITTEN
    declarations, unreadable = read_directory(directory)
    if not declarations and not unreadable:
        _err(f"report: {directory} has no declarations")
        return EMPTY
    total = len(declarations)
    since = getattr(args, "since", None)
    if since:
        # A declaration whose date cannot be read is kept and marked: a filter
        # that dropped it would hide data instead of naming what it cannot tell.
        declarations = [d for d in declarations if d["date"] is None or d["date"].date() >= since]
    source = describe_source(directory, since=since, total=total if since else None)
    coverage = branch_of_directory(directory, getattr(args, "branch", None) or "HEAD",
                                   getattr(args, "config", None) or DEFAULT_CONFIG)
    try:
        write_html(out, build_html(declarations, unreadable, source, coverage))
    except (OSError, KeyError, ValueError) as exc:
        _err(f"report: could not write {out}: {exc}")
        return NOT_WRITTEN
    if not getattr(args, "quiet", False):
        print(summary_line(declarations, unreadable, out))
    if getattr(args, "open", False):
        webbrowser.open(out.resolve().as_uri())
    return WRITTEN


def iso_date(raw: str) -> date:
    """argparse type for --since: a calendar date, ISO spelled."""
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{raw!r} is not an ISO date (YYYY-MM-DD)") from exc


# ---------------------------------------------------------------------------
# The gate hook: the document is the last thing of an event
# ---------------------------------------------------------------------------
def ignored_by_git(path: Path, root: Path) -> bool:
    """Whether git would ignore `path`. Anything but a clean yes is a no."""
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    try:
        r = gitctx.run_git(["check-ignore", "-q", "--", rel], root)
    except OSError:
        return False
    return r.returncode == 0


def after_gate(root: Path, evidence_root: str, head: str, repo_dir: Path, out: str | None = None,
               base: str | None = None, config_path: str | None = None) -> str:
    """The report the gate writes when its verdict is green. Returns the lines to print.

    With `base`, the tip of the target branch, the board also walks that
    branch: which merges demanded a review and carry no declaration anchored
    to their commits, under the policy the gate itself just applied.

    Read from the git objects at `head`, the ones the gate just judged: never
    the working tree, never the synthetic merge commit of a CI checkout. Best
    effort and never silent: the verdict is already given, so nothing here
    changes the exit code, but a real failure ends in one unmistakable line
    that stays in the log of the event.

    Without `out`, the destination is the default file at the root, and only if
    git ignores it: `round` demands a clean tree and `git status` does not
    list ignored files, so a report that git tracked as untracked would break
    the next round. With `out`, whoever asked chose the place.
    """
    try:
        if out:
            destination = resolve_against(out, root)
            evidence_dir = root / evidence_root
            if inside(destination, evidence_dir):
                return (f"[gate] report: {destination} falls inside the evidence directory, so it was "
                        "not written: the gate would read it as an artifact and reject it")
            if tracked_by_git(destination):
                return (f"[gate] report: {destination} is a file git tracks, so it was not written: the "
                        "report is derived and never versioned")
        else:
            destination = root / DEFAULT_OUT
            if not ignored_by_git(destination, root):
                return (f"[gate] report: {DEFAULT_OUT} is not ignored by git, so it was not written (it "
                        "would dirty the tree; `disensor init --upgrade` adds it to .gitignore, or run "
                        "`disensor report` yourself)")
        declarations, unreadable = read_tree(head, evidence_root, repo_dir)
        coverage = None
        if base:
            from .branch import branch_coverage  # gate imports this module: resolved here, not at import
            coverage = branch_coverage(base, evidence_root, config_path or DEFAULT_CONFIG, repo_dir,
                                       label="la base del PR")
        write_html(destination, build_html(declarations, unreadable,
                                           Source(directory=evidence_root, commit=head[:7]), coverage))
        return summary_line(declarations, unreadable, destination, prefix="[gate] report: ")
    except Exception as exc:  # noqa: BLE001 - reported, never raised past the verdict
        return f"[gate] report: FAILED: {type(exc).__name__}: {exc}"

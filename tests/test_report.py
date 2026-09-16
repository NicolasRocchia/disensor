"""`disensor report`: the HTML that reads the declarations and never validates them.

Two invariants carry the suite. The report is a pure function of the
declarations: no timestamp, no local path, so two runs over the same directory
give identical bytes. And it loads nothing: no stylesheet, script, image or
font from anywhere, enforced by a Content-Security-Policy in the file itself,
because the first regulated user opens it on a machine without internet.

The numbers of the real corpus are compared two ways (what the report read
against what each declaration declares in `metrics.counts`), never fixed as
constants: every event adds a declaration and the suite has to keep passing.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from disensor.cli import build_parser
from disensor.report import (
    AGAINST_NAME,
    CLASS_NAME,
    CONFINEMENT_NAME,
    FIX_TYPE_NAME,
    GAP_REASON_NAME,
    GATE_NAME,
    HARDENING_NAME,
    INDEPENDENCE_NAME,
    SEVERITY_LEVEL,
    SEVERITY_NAME,
    STATE_NAME,
    Source,
    aggregate,
    build_html,
    group_repository,
    parse_created,
    read_directory,
    split_location,
)
from disensor.rules import load_schema

ROOT = Path(__file__).resolve().parents[1]
RESIDUE = ROOT / ".residue"
VECTORS = ROOT / "spec" / "vectors"
EXAMPLES = ROOT / "spec" / "examples"


def artifact(version: str, name: str) -> dict:
    return json.loads((VECTORS / version / f"{name}.json").read_text(encoding="utf-8"))["artifact"]


def example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def write(directory: Path, name: str, data) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return path


def html_of(directory: Path) -> str:
    declarations, unreadable = read_directory(directory)
    return build_html(declarations, unreadable, Source(directory=".residue"))


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


# --- the real corpus ----------------------------------------------------------

def test_reads_the_real_corpus_without_exceptions():
    declarations, unreadable = read_directory(RESIDUE)
    assert len(declarations) >= 44
    assert unreadable == []


def test_the_states_read_match_the_counts_each_declaration_declares():
    """The check the prototype ran on the side, as a test and not as render logic:
    the report shows `metrics.counts` as declared, and this is where read and
    declared are compared."""
    declarations, _ = read_directory(RESIDUE)
    read = Counter(f["state"] for d in declarations for f in d["findings"])
    declared = Counter()
    for d in declarations:
        c = d["counts"]
        declared["total"] += c["total_findings"]
        for key, n in c["valid"].items():
            declared[key] += n
        for key, n in c["false_positives"].items():
            declared[key] += n
        declared["escalated_open"] += c["escalated_open"]
    assert sum(read.values()) == declared["total"] >= 173
    for state in STATE_NAME:
        assert read[state] == declared[state], state


def test_residue_items_attention_and_absences_match_an_independent_walk():
    items = attention = absences = 0
    for path in RESIDUE.glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        residue = raw["residue"]
        absences += 1 if residue.get("declared_absence") else 0
        for it in residue.get("items") or []:
            items += 1
            attention += 1 if it.get("requires_human_attention") else 0
    declarations, unreadable = read_directory(RESIDUE)
    model = aggregate(declarations, unreadable)
    assert sum(len(d["items"]) for d in declarations) == items
    assert len(model.open_groups[0][3]) == attention
    assert sum(1 for d in declarations if d["absence"]) == absences


# --- profiles and versions -----------------------------------------------------

MINIMIZED = ("valid_minimized_profile", "valid_minimized_opaque_extensions", "valid_minimized_declared_absence")


@pytest.mark.parametrize("name", MINIMIZED)
def test_a_minimized_vector_renders_without_mute_blanks(tmp_path, name):
    """Every field the profile strips is named in the page, never left as a hole:
    the first regulated client will have nothing but states and severities."""
    write(tmp_path / ".residue", f"{name}.json", artifact("v0.4", name))
    page = html_of(tmp_path / ".residue")
    assert "perfil minimizado" in page
    assert "sha256:f1e2d3c4b5a69788" in page  # the hashed repository, as is
    assert "<dd></dd>" not in page
    assert not re.search(r"\b(None|null|undefined)\b", page)
    assert chr(0x2014) not in page  # no em dash anywhere in what the template writes


def test_minimized_cases_say_why_the_view_is_empty(tmp_path):
    write(tmp_path / ".residue", "a.json", artifact("v0.4", "valid_minimized_profile"))
    page = html_of(tmp_path / ".residue")
    assert "sin títulos ni descripciones: perfil minimizado" in page


def test_one_vector_per_schema_version_in_the_same_directory(tmp_path):
    residue = tmp_path / ".residue"
    write(residue, "a.json", artifact("v0.2", "valid_real_01_plan_gate"))
    write(residue, "b.json", artifact("v0.3", "valid_diff_gate"))
    write(residue, "c.json", artifact("v0.4", "valid_diff_gate"))
    declarations, unreadable = read_directory(residue)
    assert len(declarations) == 3 and unreadable == []
    page = build_html(declarations, unreadable, Source(directory=".residue"))
    for version in ("residue/v0.2", "residue/v0.3", "residue/v0.4"):
        assert version in page
    assert "v0.2 no registra ubicaciones" in page
    assert "no declarada en v0.2" in page  # independence, a v0.4 field, read from an older version


# --- what cannot be read -------------------------------------------------------

def test_unreadable_files_are_listed_and_never_stop_the_report(tmp_path, monkeypatch, capsys):
    """Broken JSON, an empty object, and two files that have `schema` and `event`
    and nothing else of a declaration: one of them an `event` that is a list, the
    other a `findings` that is a string. All four go to the list; the valid one
    still renders."""
    residue = tmp_path / ".residue"
    write(residue, "valida.json", example("example_2_diff_gate.json"))
    write(residue, "roto.json", "{ esto no es JSON")
    write(residue, "vacio.json", "{}")
    write(residue, "evento-lista.json", {"schema": "residue/v0.4", "event": [1]})
    malformed = example("example_2_diff_gate.json")
    malformed["findings"] = "x"
    write(residue, "hallazgos-texto.json", malformed)
    monkeypatch.chdir(tmp_path)
    assert run(["report"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("1 declaration,")
    assert "4 files unreadable" in out
    page = (tmp_path / "informe-residuo.html").read_text(encoding="utf-8")
    for name in ("roto.json", "vacio.json", "evento-lista.json", "hallazgos-texto.json"):
        assert name in page
    assert "no se pudieron leer" in page


# --- the file loads nothing ----------------------------------------------------

def test_the_page_loads_nothing_from_outside(tmp_path):
    residue = tmp_path / ".residue"
    write(residue, "a.json", example("example_2_diff_gate.json"))
    page = html_of(residue)
    for forbidden in ("<link", "<script src", "<img", "<iframe", "@import", "url(", "file:"):
        assert forbidden not in page, forbidden
    assert "Content-Security-Policy" in page and "default-src 'none'" in page
    assert str(residue) not in page and str(tmp_path) not in page


# --- order and reproducibility -------------------------------------------------

def test_a_repeated_created_at_orders_by_event_id_and_the_bytes_are_reproducible(tmp_path):
    residue = tmp_path / ".residue"
    base = example("example_2_diff_gate.json")
    for event_id, name in (("bbbbbbbb-1a2b-4c3d-8e5f-6a7b8c9d0e1f", "z.json"),
                           ("aaaaaaaa-1a2b-4c3d-8e5f-6a7b8c9d0e1f", "y.json")):
        data = json.loads(json.dumps(base))
        data["event"]["event_id"] = event_id
        write(residue, name, data)
    declarations, _ = read_directory(residue)
    assert [d["event_id"][:8] for d in declarations] == ["bbbbbbbb", "aaaaaaaa"]
    assert html_of(residue) == html_of(residue)


def test_a_naive_date_reads_as_utc_and_orders_the_same_on_any_host(tmp_path):
    when, naive = parse_created("2026-09-01T10:00:00")
    assert naive and when == datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    residue = tmp_path / ".residue"
    base = example("example_2_diff_gate.json")
    for event_id, created in (("aaaaaaaa-1a2b-4c3d-8e5f-6a7b8c9d0e1f", "2026-09-01T10:00:00"),
                              ("bbbbbbbb-1a2b-4c3d-8e5f-6a7b8c9d0e1f", "2026-09-01T08:00:00-03:00")):
        data = json.loads(json.dumps(base))
        data["event"]["event_id"] = event_id
        data["event"]["created_at"] = created
        write(residue, f"{event_id[:8]}.json", data)
    declarations, _ = read_directory(residue)
    # 08:00-03:00 is 11:00 UTC, later than the naive 10:00 read as UTC.
    assert [d["event_id"][:8] for d in declarations] == ["bbbbbbbb", "aaaaaaaa"]
    assert "sin zona horaria" in html_of(residue)


# --- vocabulary against the schema ----------------------------------------------

def test_the_vocabulary_covers_every_enum_of_the_current_schema():
    """Same guard as the PR comment: a value the schema adds cannot fall through
    as its raw identifier without the suite saying so."""
    s = load_schema()
    finding = s["$defs"]["finding"]["properties"]
    item = s["$defs"]["residue_item"]["properties"]
    reviewer = s["properties"]["actors"]["properties"]["reviewers"]["items"]["properties"]
    assert set(CLASS_NAME) == set(item["class"]["enum"])
    assert set(GAP_REASON_NAME) == set(item["gap_reason"]["enum"])
    assert set(STATE_NAME) == set(finding["final_state"]["enum"])
    assert set(SEVERITY_NAME) == set(SEVERITY_LEVEL) == set(finding["severity"]["enum"])
    assert set(AGAINST_NAME) == set(finding["verification"]["properties"]["against"]["enum"])
    assert set(FIX_TYPE_NAME) == set(finding["fix_verification"]["properties"]["type"]["enum"])
    assert set(INDEPENDENCE_NAME) == set(reviewer["independence"]["enum"])
    assert set(HARDENING_NAME) == set(reviewer["hardening"]["enum"])
    assert set(CONFINEMENT_NAME) == set(reviewer["confinement"]["properties"]["mode"]["enum"])
    assert set(GATE_NAME) == set(s["properties"]["event"]["properties"]["gate"]["enum"])


# --- normalisation -------------------------------------------------------------

def test_the_three_spellings_of_the_repository_group_as_one_and_the_original_stays(tmp_path):
    spellings = ("github.com/NicolasRocchia/disensor", "https://github.com/NicolasRocchia/disensor.git",
                 "https://github.com/NicolasRocchia/disensor")
    assert {group_repository(s) for s in spellings} == {"github.com/NicolasRocchia/disensor"}
    hashed = "sha256:" + "f" * 64
    assert group_repository(hashed) == hashed
    residue = tmp_path / ".residue"
    base = example("example_2_diff_gate.json")
    for i, spelling in enumerate(spellings):
        data = json.loads(json.dumps(base))
        data["event"]["event_id"] = f"{i:08d}-1a2b-4c3d-8e5f-6a7b8c9d0e1f"
        data["event"]["repository"] = spelling
        write(residue, f"{i}.json", data)
    declarations, unreadable = read_directory(residue)
    assert aggregate(declarations, unreadable).repositories == ["github.com/NicolasRocchia/disensor"]
    assert sorted(d["repository"] for d in declarations) == sorted(spellings)


def test_a_location_splits_only_when_every_part_looks_like_a_path():
    assert split_location("README.md, README.es.md") == ["README.md", "README.es.md"]
    assert split_location("src/disensor/gate.py") == ["src/disensor/gate.py"]
    assert split_location("gate.py, the part that posts the comment") == ["gate.py, the part that posts the comment"]
    assert split_location(None) == []


# --- the command ---------------------------------------------------------------

def test_since_filters_by_date_and_keeps_what_it_cannot_date(tmp_path, monkeypatch, capsys):
    residue = tmp_path / ".residue"
    base = example("example_2_diff_gate.json")
    for event_id, created in (("aaaaaaaa-1a2b-4c3d-8e5f-6a7b8c9d0e1f", "2026-08-01T10:00:00-03:00"),
                              ("bbbbbbbb-1a2b-4c3d-8e5f-6a7b8c9d0e1f", "2026-09-10T10:00:00-03:00"),
                              ("cccccccc-1a2b-4c3d-8e5f-6a7b8c9d0e1f", "ayer a la tarde")):
        data = json.loads(json.dumps(base))
        data["event"]["event_id"] = event_id
        data["event"]["created_at"] = created
        write(residue, f"{event_id[:8]}.json", data)
    monkeypatch.chdir(tmp_path)
    assert run(["report", "--since", "2026-09-01"]) == 0
    assert capsys.readouterr().out.startswith("2 declarations,")
    page = (tmp_path / "informe-residuo.html").read_text(encoding="utf-8")
    assert "bbbbbbbb" in page and "cccccccc" in page and "aaaaaaaa" not in page
    assert "fecha ilegible" in page
    assert "sólo declaraciones desde el 01/09/2026 (2 de 3)" in page


def test_exit_codes_for_a_missing_and_an_empty_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert run(["report"]) == 2
    (tmp_path / ".residue").mkdir()
    assert run(["report"]) == 1
    assert not (tmp_path / "informe-residuo.html").exists()
    err = capsys.readouterr().err
    assert "is not a directory" in err and "has no declarations" in err


@pytest.mark.parametrize("out", [".residue/informe.html", ".residue/../.residue/informe.html"])
def test_an_output_inside_the_evidence_directory_is_refused(tmp_path, monkeypatch, capsys, out):
    write(tmp_path / ".residue", "a.json", example("example_2_diff_gate.json"))
    monkeypatch.chdir(tmp_path)
    assert run(["report", "--out", out]) == 3
    assert "inside the evidence directory" in capsys.readouterr().err
    assert list((tmp_path / ".residue").glob("*.html")) == []


def test_an_absolute_alias_of_the_evidence_directory_is_refused_too(tmp_path, monkeypatch):
    write(tmp_path / ".residue", "a.json", example("example_2_diff_gate.json"))
    monkeypatch.chdir(tmp_path)
    assert run(["report", "--out", str((tmp_path / ".residue" / "x.html").resolve())]) == 3


def test_a_symlink_to_the_evidence_directory_counts_as_the_evidence_directory(tmp_path, monkeypatch):
    write(tmp_path / ".residue", "a.json", example("example_2_diff_gate.json"))
    link = tmp_path / "alias"
    try:
        os.symlink(tmp_path / ".residue", link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not let the suite create symlinks")
    monkeypatch.chdir(tmp_path)
    assert run(["report", "--out", "alias/informe.html"]) == 3


def test_the_summary_line_and_quiet(tmp_path, monkeypatch, capsys):
    write(tmp_path / ".residue", "a.json", example("example_2_diff_gate.json"))
    monkeypatch.chdir(tmp_path)
    assert run(["report"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith(str(tmp_path / "informe-residuo.html"))
    assert re.match(r"1 declaration, \d+ items? asks? for human attention -> ", out)
    assert run(["report", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_a_title_holding_every_marker_reaches_the_page_intact(tmp_path):
    """The template is filled in one pass: what a declaration says is never
    rescanned for markers, so a title made of them survives."""
    data = example("example_2_diff_gate.json")
    title = "@@REPO@@ @@PERIODO@@ @@PESTANAS@@ @@ABIERTO@@ @@DECLARACIONES@@ @@CORPUS@@ @@CASOS@@ @@ILEGIBLES@@ @@PIE@@"
    data["findings"][0]["title"] = title
    write(tmp_path / ".residue", "a.json", data)
    page = html_of(tmp_path / ".residue")
    # A second pass would have replaced the markers inside the title with the
    # footer, the tabs and the views; the literal survives only if there is one.
    assert title in page
    assert "Generado desde" in page


def test_the_footer_names_the_commit_and_what_is_not_committed(tmp_path, monkeypatch, capsys):
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True, check=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "report@test")
    git("config", "user.name", "report")
    git("config", "commit.gpgsign", "false")
    write(tmp_path / ".residue", "a.json", example("example_2_diff_gate.json"))
    git("add", "-A")
    git("commit", "-q", "-m", "una declaracion")
    sha = git("rev-parse", "--short", "HEAD").stdout.strip()
    monkeypatch.chdir(tmp_path)
    assert run(["report", "--quiet"]) == 0
    page = (tmp_path / "informe-residuo.html").read_text(encoding="utf-8")
    assert f"en el commit <code>{sha}</code>" in page
    assert "sin commitear" not in page
    write(tmp_path / ".residue", "b.json", example("example_1_plan_gate.json"))
    assert run(["report", "--quiet"]) == 0
    page = (tmp_path / "informe-residuo.html").read_text(encoding="utf-8")
    assert "más 1 archivo sin commitear en <code>.residue/</code>" in page


def test_the_open_view_names_the_absence_of_closure_and_the_latest_declaration(tmp_path):
    residue = tmp_path / ".residue"
    write(residue, "a.json", example("example_2_diff_gate.json"))
    page = html_of(residue)
    assert "El artefacto no registra cierres" in page
    assert "sin evidencia posterior de cierre" in page
    assert "última declaración" in page
    assert 'data-orden="0"' in page

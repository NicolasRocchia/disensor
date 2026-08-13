"""Gate tests over real git repositories.

Every case that says "(used to pass)" is a bypass that was reproduced by hand
against 0.3.0 before being written down here: a PR merging code that no
declaration had reviewed, and the check was green.

The gate is the piece that decides whether a merge is allowed, so it is tested
against real repositories with real ranges. Faking git here would test the mock.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from disensor.gate import event_key, run_gate

EXAMPLES = Path(__file__).resolve().parents[1] / "spec" / "examples"
PLAN = json.loads((EXAMPLES / "example_1_plan_gate.json").read_text(encoding="utf-8"))
DIFF = json.loads((EXAMPLES / "example_2_diff_gate.json").read_text(encoding="utf-8"))

CONFIG = {"criticality_level": "B", "level_A_enabled": False}


class Repo:
    def __init__(self, path: Path):
        self.path = path
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "gate@test")
        self.git("config", "user.name", "gate")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args: str) -> str:
        r = subprocess.run(
            ["git", *args], cwd=self.path, capture_output=True, text=True, check=False
        )
        if r.returncode != 0 and args[0] not in ("merge-base",):
            raise AssertionError(f"git {' '.join(args)}: {r.stderr}")
        return r.stdout.strip()

    def write(self, relpath: str, content: str = "x") -> None:
        p = self.path / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def commit(self, message: str = "c") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def config(self, data: dict) -> None:
        self.write("disensor.config.json", json.dumps(data))

    def artifact(self, gate: str, head: str, base: str | None = None,
                 event_id: str | None = None, directory: str = ".residue",
                 name: str | None = None, level: str = "B") -> str:
        """Write a valid artifact declaring a review of `head`."""
        source = DIFF if gate == "diff" else PLAN
        data = json.loads(json.dumps(source))
        event_id = event_id or f"{abs(hash((gate, head, name))) % 10**8:08d}-1a2b-4c3d-8e5f-6a7b8c9d0e1f"
        data["event"]["event_id"] = event_id
        data["event"]["gate"] = gate
        data["event"]["head_commit"] = head
        data["event"]["criticality_level"] = level
        if base is not None:
            data["event"]["base_commit"] = base
        elif "base_commit" in data["event"]:
            del data["event"]["base_commit"]
        path = f"{directory}/{name or event_id}.json"
        self.write(path, json.dumps(data, ensure_ascii=False))
        return path

    def run(self, base: str, head: str, directory: str = ".residue",
            config: str = "disensor.config.json") -> int:
        return run_gate(
            directory=directory, config_path=config, base=base, head=head,
            repo_dir=self.path, post=False,
        )


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    r = Repo(tmp_path)
    r.config(CONFIG)
    r.write("README.md", "start")
    r.commit("base")
    return r


def out(capsys) -> str:
    return capsys.readouterr().out


# --- the happy path, and the regression that made the gate unusable -----------

def test_declared_pr_passes(repo, capsys):
    repo.write("src/app.py", "code")
    code_commit = repo.commit("feat")
    repo.artifact("diff", head=code_commit, base=repo.git("rev-parse", "HEAD~1"))
    head = repo.commit("docs(residue)")
    assert repo.run(repo.git("rev-parse", "HEAD~2"), head) == 0


def test_second_pr_is_not_broken_by_the_evidence_of_the_first(repo, capsys):
    """Used to fail: the artifact of PR 1 was judged against the range of PR 2."""
    repo.write("src/a.py", "one")
    c1 = repo.commit("feat 1")
    repo.artifact("diff", head=c1, base=repo.git("rev-parse", "HEAD~1"))
    first_pr_head = repo.commit("docs(residue) 1")

    repo.write("src/b.py", "two")
    c2 = repo.commit("feat 2")
    repo.artifact("diff", head=c2, base=first_pr_head)
    second_pr_head = repo.commit("docs(residue) 2")

    assert repo.run(first_pr_head, second_pr_head) == 0


def test_pr_without_declaration_fails_even_with_old_evidence(repo, capsys):
    """Used to pass: G1 was satisfied by artifacts from previous PRs."""
    repo.write("src/a.py", "one")
    c1 = repo.commit("feat 1")
    repo.artifact("diff", head=c1, base=repo.git("rev-parse", "HEAD~1"))
    first_pr_head = repo.commit("docs(residue) 1")

    repo.write("src/evil.py", "undeclared")
    head = repo.commit("feat undeclared")
    assert repo.run(first_pr_head, head) == 1
    assert "[G1]" in out(capsys)


# --- the two criticals --------------------------------------------------------

def test_code_after_the_reviewed_commit_fails(repo, capsys):
    """Used to pass: the reviewed commit was merely inside the range."""
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "reviewed")
    reviewed = repo.commit("feat reviewed")
    repo.artifact("diff", head=reviewed, base=base)
    repo.commit("docs(residue)")
    repo.write("src/app.py", "never reviewed")
    head = repo.commit("feat sneaked in")
    assert repo.run(base, head) == 1
    assert "[G6]" in out(capsys)


def test_plan_artifact_does_not_approve_code(repo, capsys):
    """Used to pass: the gate type was only consulted by R7."""
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "code")
    code = repo.commit("feat")
    repo.artifact("plan", head=code)
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 1
    assert "[G6]" in out(capsys)


def test_mosaic_coverage_fails(repo, capsys):
    """Two side branches reviewed apart, merged without reviewing the integration.

    Each artifact qualifies for its own path, so path-by-path coverage is
    satisfied while nobody ever saw the tree where both halves meet.
    """
    merge_base = repo.git("rev-parse", "HEAD")

    repo.git("checkout", "-q", "-b", "left")
    repo.write("src/auth.py", "half one")
    left_code = repo.commit("feat auth")
    repo.artifact("diff", head=left_code, base=merge_base, event_id="aaaaaaaa-1a2b-4c3d-8e5f-6a7b8c9d0e1f")
    repo.commit("docs(residue) left")

    repo.git("checkout", "-q", "-b", "right", merge_base)
    repo.write("src/permissions.py", "half two")
    right_code = repo.commit("feat permissions")
    repo.artifact("diff", head=right_code, base=merge_base, event_id="bbbbbbbb-1a2b-4c3d-8e5f-6a7b8c9d0e1f")
    repo.commit("docs(residue) right")

    repo.git("merge", "-q", "--no-ff", "left", "-m", "merge left")
    head = repo.git("rev-parse", "HEAD")

    assert repo.run(merge_base, head) == 1
    assert "[G7]" in out(capsys)


def test_several_diffs_pass_when_one_reaches_the_head(repo, capsys):
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/a.py", "one")
    first = repo.commit("feat 1")
    repo.artifact("diff", head=first, base=base, event_id="cccccccc-1a2b-4c3d-8e5f-6a7b8c9d0e1f")
    repo.commit("docs(residue) 1")
    repo.write("src/b.py", "two")
    second = repo.commit("feat 2")
    repo.artifact("diff", head=second, base=base, event_id="dddddddd-1a2b-4c3d-8e5f-6a7b8c9d0e1f")
    head = repo.commit("docs(residue) 2")
    assert repo.run(base, head) == 0


# --- policy comes from the base ----------------------------------------------

def test_pr_cannot_switch_off_the_gate_it_is_being_judged_by(repo, capsys):
    """Used to pass: the config was read from the PR checkout."""
    base = repo.git("rev-parse", "HEAD")
    repo.config({**CONFIG, "gate": {"required": False}})
    repo.write("src/evil.py", "undeclared")
    head = repo.commit("chore: relax the gate and sneak code in")
    assert repo.run(base, head) == 1


def test_required_false_in_the_base_still_validates_what_is_declared(repo, capsys):
    repo.config({**CONFIG, "gate": {"required": False}})
    base = repo.commit("chore: gate not required")
    repo.write("src/app.py", "code")
    code = repo.commit("feat")
    path = repo.artifact("diff", head=code, base=base)
    broken = json.loads((repo.path / path).read_text(encoding="utf-8"))
    broken["residue"]["items"][0]["description"] = "ninguno"  # generic marker, R2
    repo.write(path, json.dumps(broken, ensure_ascii=False))
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 1
    assert "[R2]" in out(capsys)


def test_bootstrap_without_config_in_the_base_uses_safe_defaults(tmp_path, capsys):
    r = Repo(tmp_path)
    r.write("README.md", "start")
    base = r.commit("base")
    r.write("src/app.py", "code")
    head = r.commit("feat without any declaration")
    assert r.run(base, head) == 1
    assert "safe defaults" in out(capsys)


# --- scope policy -------------------------------------------------------------

def test_docs_can_be_approved_with_a_plan_when_scope_says_so(repo, capsys):
    repo.config({**CONFIG, "gate": {"scope": [
        {"paths": ["docs/**"], "accepts": ["plan", "diff"]},
        {"paths": ["**"], "accepts": ["diff"]},
    ]}})
    base = repo.commit("chore: scope")
    repo.write("docs/guide.md", "text")
    doc = repo.commit("docs")
    repo.artifact("plan", head=doc)
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 0


def test_exempt_paths_need_no_artifact(repo, capsys):
    repo.config({**CONFIG, "gate": {"scope": [
        {"paths": ["CHANGELOG.md"], "accepts": []},
        {"paths": ["**"], "accepts": ["diff"]},
    ]}})
    base = repo.commit("chore: scope")
    repo.write("CHANGELOG.md", "release notes")
    head = repo.commit("chore: changelog")
    assert repo.run(base, head) == 0


def test_scope_cannot_lower_the_floor_on_workflows(repo, capsys):
    """The artifact is the gate the relaxed policy accepts, so only the floor can reject it."""
    repo.config({**CONFIG, "gate": {"scope": [
        {"paths": ["**/*.yml"], "accepts": ["architecture"]},
        {"paths": ["**"], "accepts": ["diff"]},
    ]}})
    base = repo.commit("chore: scope")
    repo.write(".github/workflows/ci.yml", "on: push")
    wf = repo.commit("ci")
    repo.artifact("architecture", head=wf)
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 1
    assert "[G6]" in out(capsys)


def test_the_floor_covers_the_protected_root_itself(repo, capsys):
    """`foo/**` does not match `foo`, so the exact root has to be in the floor too."""
    repo.config({**CONFIG, "gate": {"scope": [{"paths": ["**"], "accepts": []}]}})
    base = repo.commit("chore: everything exempt")
    repo.write(".residue", "a file where the evidence directory should be")
    head = repo.commit("chore: park a file on the evidence root")
    assert repo.run(base, head) == 1


def test_scope_is_case_sensitive(repo, capsys):
    repo.config({**CONFIG, "gate": {"scope": [
        {"paths": ["docs/**"], "accepts": []},
        {"paths": ["**"], "accepts": ["diff"]},
    ]}})
    base = repo.commit("chore: scope")
    repo.write("DOCS/payload.py", "code hiding behind a case difference")
    head = repo.commit("feat")
    assert repo.run(base, head) == 1


def test_unmatched_path_demands_diff(repo, capsys):
    repo.config({**CONFIG, "gate": {"scope": [{"paths": ["docs/**"], "accepts": ["plan"]}]}})
    base = repo.commit("chore: scope")
    repo.write("src/app.py", "code")
    head = repo.commit("feat")
    assert repo.run(base, head) == 1


def test_custom_config_path_is_protected_by_the_floor(repo, capsys):
    repo.write("security/policy.json", json.dumps({**CONFIG, "gate": {"scope": [
        {"paths": ["security/**"], "accepts": ["architecture", "plan"]},
        {"paths": ["**"], "accepts": ["diff"]},
    ]}}))
    base = repo.commit("chore: policy")
    repo.write("security/policy.json", json.dumps({**CONFIG, "gate": {"scope": [
        {"paths": ["src/**"], "accepts": []},
        {"paths": ["**"], "accepts": ["diff"]},
    ]}}))
    changed = repo.commit("chore: relax policy through the side door")
    repo.artifact("plan", head=changed)
    head = repo.commit("docs(residue)")
    assert repo.run(base, head, config="security/policy.json") == 1


# --- evidence integrity -------------------------------------------------------

def test_historical_evidence_cannot_be_modified(repo, capsys):
    repo.write("src/a.py", "one")
    c1 = repo.commit("feat")
    path = repo.artifact("diff", head=c1, base=repo.git("rev-parse", "HEAD~1"))
    first = repo.commit("docs(residue)")
    data = json.loads((repo.path / path).read_text(encoding="utf-8"))
    data["residue"]["items"] = []
    data["residue"]["declared_absence"] = True
    repo.write(path, json.dumps(data, ensure_ascii=False))
    head = repo.commit("chore: rewrite history")
    assert repo.run(first, head) == 1
    assert "[G8]" in out(capsys)


def test_historical_evidence_cannot_be_deleted(repo, capsys):
    repo.write("src/a.py", "one")
    c1 = repo.commit("feat")
    path = repo.artifact("diff", head=c1, base=repo.git("rev-parse", "HEAD~1"))
    first = repo.commit("docs(residue)")
    (repo.path / path).unlink()
    head = repo.commit("chore: remove evidence")
    assert repo.run(first, head) == 1
    assert "[G8]" in out(capsys)


def test_duplicate_event_id_fails_even_if_history_used_another_filename(repo, capsys):
    """Identity is the declared event_id, not the file name.

    Before 0.4 the name did not have to match the id, so reading only file names
    would miss a new artifact reusing the id of a legacy one.
    """
    shared = "eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f"
    repo.write("src/a.py", "one")
    c1 = repo.commit("feat")
    repo.artifact("diff", head=c1, base=repo.git("rev-parse", "HEAD~1"),
                  event_id=shared, name="legacy-name")
    first = repo.commit("docs(residue) with a pre-0.4 file name")

    repo.write("src/b.py", "two")
    c2 = repo.commit("feat 2")
    repo.artifact("diff", head=c2, base=first, event_id=shared)  # canonical name, reused id
    head = repo.commit("docs(residue) 2")
    assert repo.run(first, head) == 1
    assert "already exists" in out(capsys)


@pytest.mark.parametrize("variant", [
    "EEEEEEEE-1A2B-4C3D-8E5F-6A7B8C9D0E1F",
    "{eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f}",
    "urn:uuid:eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
    "eeeeeeee1a2b4c3d8e5f6a7b8c9d0e1f",
    " eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f ",
    # Both the URI scheme and the URN namespace are case insensitive, but
    # uuid.UUID only accepts the lower case prefix.
    "URN:UUID:eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
    "Urn:Uuid:EEEEEEEE-1A2B-4C3D-8E5F-6A7B8C9D0E1F",
])
def test_event_key_normalises_these_spellings_of_the_same_uuid(variant):
    """Unit test on purpose: `:` and case-insensitivity make several of these
    unrepresentable as file names on Windows, and the point is the identity
    comparison, not what the filesystem happens to allow."""
    assert event_key(variant) == event_key("eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f")


@pytest.mark.parametrize("historical_id", [
    "urn:uuid:eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f#x",
    "URN:UUID:eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f?=x",
    "eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f?+x",
])
def test_history_written_before_the_canonical_rule_still_blocks_reuse(historical_id):
    """RFC 8141 ignores the r-component, q-component and fragment for equivalence.

    A repository can hold ids written that way from before the rule existed; if
    they keyed differently, a new canonical artifact would reuse the identity.
    """
    assert event_key(historical_id) == event_key("eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f")


def test_event_key_keeps_different_uuids_apart():
    """The opposite error also matters: a false collision blocks a legitimate PR."""
    a = "eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f"
    b = "eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e20"
    assert event_key(a) != event_key(b)
    assert event_key("not-a-uuid-at-all") != event_key(a)


def test_two_artifacts_in_the_same_pr_cannot_share_an_id(repo, capsys):
    """History is not the only place an id can be reused: the PR itself is one."""
    shared = "ffffffff-1a2b-4c3d-8e5f-6a7b8c9d0e1f"
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/a.py", "one")
    code = repo.commit("feat")
    repo.artifact("diff", head=code, base=base, event_id=shared)
    repo.artifact("plan", head=code, event_id="{ffffffff-1a2b-4c3d-8e5f-6a7b8c9d0e1f}")
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 1
    assert "[G8]" in out(capsys)


@pytest.mark.parametrize("event_id", [
    "URN:UUID:eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f#x",  # RFC 8141 ignores `#`
    "urn:uuid:eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f",
    "EEEEEEEE-1A2B-4C3D-8E5F-6A7B8C9D0E1F",
    "eeeeeeee1a2b4c3d8e5f6a7b8c9d0e1f",
    # Fixed points of the fallback: `event_key(x) == x` for these, so a check
    # written that way would let them through. The parse has to be explicit.
    "not-a-uuid-at-all",
    "x",
])
def test_a_new_artifact_needs_a_canonical_event_id(repo, event_id, capsys):
    """One identity, one spelling.

    While the validator does not assert `format: uuid`, chasing every equivalent
    spelling is a losing game: demanding the canonical form closes all of them.
    """
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/a.py", "one")
    code = repo.commit("feat")
    repo.artifact("diff", head=code, base=base, event_id=event_id, name="artifact")
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 1
    assert "canonical UUID" in out(capsys)


def test_unreadable_historical_evidence_fails_closed(repo, capsys):
    """If a past artifact cannot be read, its id is unknown and could be reused."""
    repo.write(".residue/legacy.json", "{ this is not valid json")
    first = repo.commit("chore: unreadable evidence from another era")
    repo.write("src/a.py", "one")
    code = repo.commit("feat")
    repo.artifact("diff", head=code, base=first)
    head = repo.commit("docs(residue)")
    assert repo.run(first, head) == 1
    assert "cannot be read" in out(capsys)


@pytest.mark.parametrize("variant", ["{eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f}"])
def test_the_same_uuid_written_differently_still_collides(repo, variant, capsys):
    """Identity is the event, not its spelling.

    The schema declares `format: uuid` without the validator asserting it, so
    without normalisation the same id in another textual form gets another file
    name, validates, and the collision goes unnoticed.
    """
    original = "eeeeeeee-1a2b-4c3d-8e5f-6a7b8c9d0e1f"
    repo.write("src/a.py", "one")
    c1 = repo.commit("feat")
    repo.artifact("diff", head=c1, base=repo.git("rev-parse", "HEAD~1"), event_id=original)
    first = repo.commit("docs(residue)")

    repo.write("src/b.py", "two")
    c2 = repo.commit("feat 2")
    repo.artifact("diff", head=c2, base=first, event_id=variant)
    head = repo.commit("docs(residue) 2")
    assert repo.run(first, head) == 1
    assert "already exists" in out(capsys)


def test_filename_must_match_the_event_id(repo, capsys):
    repo.write("src/a.py", "one")
    c1 = repo.commit("feat")
    repo.artifact("diff", head=c1, base=repo.git("rev-parse", "HEAD~1"), name="whatever")
    head = repo.commit("docs(residue)")
    assert repo.run(repo.git("rev-parse", "HEAD~2"), head) == 1
    assert "[G8]" in out(capsys)


def test_code_hidden_in_the_evidence_directory_counts_as_code(repo, capsys):
    base = repo.git("rev-parse", "HEAD")
    repo.write(".residue/payload.py", "code parked in the exempt zone")
    repo.write(".residue/nested/deep.json", "{}")
    head = repo.commit("chore: park code in the evidence directory")
    assert repo.run(base, head) == 1


# --- range and identity -------------------------------------------------------

def test_missing_range_fails_closed(repo, capsys):
    repo.write("src/app.py", "code")
    repo.commit("feat")
    assert run_gate(directory=".residue", config_path="disensor.config.json",
                    base=None, head=None, repo_dir=repo.path, post=False) == 1
    assert "range" in out(capsys).lower()


def test_unknown_commit_fails_closed(repo, capsys):
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "code")
    head = repo.commit("feat")
    assert repo.run(base, "0" * 40) == 1
    assert repo.run("0" * 40, head) == 1


def test_diff_artifact_without_base_commit_fails(repo, capsys):
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "code")
    code = repo.commit("feat")
    repo.artifact("diff", head=code, base=None)
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 1
    assert "[G5]" in out(capsys)


def test_diff_artifact_with_wrong_base_commit_fails(repo, capsys):
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "code")
    code = repo.commit("feat")
    repo.artifact("diff", head=code, base="0" * 40)
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 1
    assert "[G5]" in out(capsys)


def test_abbreviated_base_commit_is_accepted(repo, capsys):
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "code")
    code = repo.commit("feat")
    repo.artifact("diff", head=code[:7], base=base[:7])
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 0


def test_reviewed_commit_outside_the_pr_fails(repo, capsys):
    base = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-q", "-b", "side")
    repo.write("side.txt", "unrelated")
    side = repo.commit("side commit")
    repo.git("checkout", "-q", "main")
    repo.write("src/app.py", "code")
    repo.commit("feat")
    repo.artifact("plan", head=side)
    head = repo.commit("docs(residue)")
    assert repo.run(base, head) == 1
    assert "[G5]" in out(capsys)


# --- configuration ------------------------------------------------------------

@pytest.mark.parametrize("directory", ["", ".", "/abs", "../escape", "a/../.."])
def test_invalid_evidence_directory_is_rejected(repo, directory, capsys):
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/app.py", "code")
    head = repo.commit("feat")
    assert repo.run(base, head, directory=directory) == 1


def test_working_tree_does_not_change_the_verdict(repo, capsys):
    repo.write("src/app.py", "code")
    code = repo.commit("feat")
    repo.artifact("diff", head=code, base=repo.git("rev-parse", "HEAD~1"))
    head = repo.commit("docs(residue)")
    (repo.path / "src" / "app.py").write_text("dirty, never committed", encoding="utf-8")
    (repo.path / "src" / "extra.py").write_text("untracked", encoding="utf-8")
    assert repo.run(repo.git("rev-parse", "HEAD~2"), head) == 0

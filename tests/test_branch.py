"""What the branch shows: merges that demanded a review and carry no declaration.

Real git repositories, real merges, dated on purpose: the period starts at the
oldest declaration's `created_at`, so commits are dated around it. Everything
the module reads comes from git objects at the tip, never from the working
tree, and the tests for the untracked file and the shallow clone exist to
keep it that way.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from disensor.branch import Coverage, branch_coverage
from disensor.report import branch_of_directory, build_html, read_directory, Source

EXAMPLES = Path(__file__).resolve().parents[1] / "spec" / "examples"
DIFF = json.loads((EXAMPLES / "example_2_diff_gate.json").read_text(encoding="utf-8"))  # created 2026-07-15
BEFORE, AFTER = "2026-06-01T12:00:00+00:00", "2026-08-01T12:00:00+00:00"


class Repo:
    def __init__(self, path: Path):
        self.path = path
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "branch@test")
        self.git("config", "user.name", "branch")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args: str, date: str | None = None) -> str:
        env = dict(os.environ)
        if date:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
        r = subprocess.run(["git", *args], cwd=self.path, capture_output=True, text=True, check=False, env=env)
        if r.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {r.stderr}")
        return r.stdout.strip()

    def write(self, relpath: str, content: str = "x") -> None:
        p = self.path / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def commit(self, message: str, date: str = AFTER) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message, date=date)
        return self.git("rev-parse", "HEAD")

    def artifact(self, head: str, name: str = "decl") -> None:
        data = json.loads(json.dumps(DIFF))
        data["event"]["event_id"] = f"{abs(hash((head, name))) % 10**8:08d}-1a2b-4c3d-8e5f-6a7b8c9d0e1f"
        data["event"]["head_commit"] = head
        data["event"]["base_commit"] = self.git("rev-parse", "main")
        self.write(f".residue/{name}.json", json.dumps(data, ensure_ascii=False))

    def branch_merge(self, name: str, message: str, date: str = AFTER, *, files: dict[str, str],
                     declare: str | None = None) -> str:
        """A side branch with `files`, optionally a declaration anchored to its
        code commit (`declare` names how the head is written: full or short),
        merged into main with a merge commit. Returns the merge oid."""
        self.git("switch", "-q", "-c", name)
        for path, content in files.items():
            self.write(path, content)
        code = self.commit(f"{name}: code", date)
        if declare:
            self.artifact(code if declare == "full" else code[:7], name=name)
            self.commit(f"{name}: declaration", date)
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", message, name, date=date)
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path) -> Repo:
    r = Repo(tmp_path / "repo")
    r.write("disensor.config.json", json.dumps({
        "criticality_level": "B", "level_A_enabled": False,
        "gate": {"required": True, "scope": [{"paths": ["docs/**"], "accepts": []}]},
    }))
    r.write("src/app.py", "print(1)")
    r.commit("start", BEFORE)
    return r


def coverage_of(repo: Repo, ref: str = "main", **kw) -> Coverage:
    return branch_coverage(ref, ".residue", "disensor.config.json", repo.path, **kw)


def test_each_kind_of_merge_lands_where_the_policy_and_the_declarations_put_it(repo):
    early = repo.branch_merge("early", "merge before any declaration", BEFORE, files={"src/a.py": "a"})
    covered = repo.branch_merge("covered", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    short = repo.branch_merge("short", "merge with an abbreviated head", files={"src/c.py": "c"}, declare="short")
    uncovered = repo.branch_merge("uncovered", "merge without a declaration", files={"src/d.py": "d"})
    exempt = repo.branch_merge("exempt", "merge of docs only", files={"docs/x.md": "x"})
    repo.write("src/direct.py", "direct")
    direct = repo.commit("direct push", AFTER)
    c = coverage_of(repo)
    assert c.error is None and c.tip == repo.git("rev-parse", "main")
    assert c.since.isoformat() == "2026-07-15"
    assert c.required and c.declarations == 2
    assert (c.merges, c.covered, c.exempt, c.before) == (3, 2, 1, 1)
    assert [row["oid"] for row in c.uncovered] == [uncovered]
    assert c.uncovered[0]["demanding"] == 1 and c.uncovered[0]["code"] == "scope_demands"
    assert (c.direct_demanding, c.direct_with_declaration, c.direct_exempt) == (1, 0, 0)
    assert [row["oid"] for row in c.direct_recent] == [direct]
    assert early not in {row["oid"] for row in c.uncovered} and covered != short


def test_a_merge_that_rewrites_evidence_is_counted_and_marked(repo):
    repo.branch_merge("first", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    decl = next((repo.path / ".residue").glob("*.json"))
    rewritten = repo.branch_merge("rewrite", "merge that edits the record", files={
        str(decl.relative_to(repo.path)).replace("\\", "/"): decl.read_text(encoding="utf-8") + "\n",
        "src/e.py": "e",
    })
    c = coverage_of(repo)
    assert c.mutated == 1
    assert [row["oid"] for row in c.uncovered] == [rewritten]
    assert c.uncovered[0]["mutations"] == 1


def test_an_untracked_declaration_in_the_working_tree_covers_nothing(repo):
    """The command displays the directory as it is on disk; the walk reads the
    tip. A shape-valid file dropped in the directory, anchored to the side
    commit of an uncovered merge, changes nothing in the panel."""
    repo.branch_merge("covered", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    uncovered = repo.branch_merge("uncovered", "merge without a declaration", files={"src/d.py": "d"})
    side = repo.git("rev-parse", f"{uncovered}^2")
    repo.artifact(side, name="untracked-and-uncommitted")
    assert repo.git("status", "--porcelain").startswith("??")
    c = coverage_of(repo)
    assert c.error is None and c.declarations == 1
    assert [row["oid"] for row in c.uncovered] == [uncovered]


def test_a_committed_file_that_does_not_validate_covers_nothing(repo):
    """The report admits any file with the shape of a declaration, on purpose;
    coverage does not. A committed JSON with a head_commit and nothing else
    of a declaration, anchored to the side commit of an uncovered merge,
    leaves the merge uncovered and is counted as a file that does not
    validate. Found by the reviewer of the round that declared this change."""
    repo.branch_merge("covered", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    uncovered = repo.branch_merge("uncovered", "merge without a declaration", files={"src/d.py": "d"})
    side = repo.git("rev-parse", f"{uncovered}^2")
    repo.write(".residue/bogus.json", json.dumps({
        "schema": "bogus", "event": {"created_at": "2026-01-01T00:00:00Z", "head_commit": side},
    }))
    bogus = repo.commit("direct push of a file that is not a declaration", AFTER)
    c = coverage_of(repo)
    assert c.error is None
    assert (c.declarations, c.invalid) == (1, 1)
    assert c.since.isoformat() == "2026-07-15"          # the bogus date moves nothing
    assert [row["oid"] for row in c.uncovered] == [uncovered]
    # The direct commit touched only the evidence directory: no path demanded a
    # review, so the gate's own function calls it exempt, and nothing counts it
    # as a declaration.
    assert bogus not in [row["oid"] for row in c.direct_recent]
    assert (c.direct_exempt, c.direct_with_declaration) == (1, 0)


def test_gate_not_required_lists_no_merge_as_missing(tmp_path):
    r = Repo(tmp_path / "relaxed")
    r.write("disensor.config.json", json.dumps({"criticality_level": "B", "level_A_enabled": False,
                                                "gate": {"required": False}}))
    r.commit("start", BEFORE)
    r.branch_merge("covered", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    r.branch_merge("uncovered", "merge without a declaration", files={"src/d.py": "d"})
    c = coverage_of(r)
    assert c.error is None and not c.required
    assert (c.merges, c.covered, c.uncovered) == (2, 1, [])


def test_a_range_with_no_common_gate_is_listed_with_its_code(tmp_path):
    r = Repo(tmp_path / "split")
    r.write("disensor.config.json", json.dumps({"criticality_level": "B", "level_A_enabled": False, "gate": {
        "required": True,
        "scope": [{"paths": ["plans/**"], "accepts": ["plan"]}, {"paths": ["src/**"], "accepts": ["diff"]}],
    }}))
    r.commit("start", BEFORE)
    r.branch_merge("covered", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    split = r.branch_merge("split", "merge across two gates", files={"plans/p.md": "p", "src/s.py": "s"})
    c = coverage_of(r)
    assert [(row["oid"], row["code"]) for row in c.uncovered] == [(split, "no_common_gate")]


def test_the_walk_asks_for_one_more_commit_than_it_keeps(repo):
    repo.branch_merge("covered", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    total = int(repo.git("rev-list", "--first-parent", "--count", "main"))
    assert total == 2
    assert coverage_of(repo, limit=2).truncated is False
    assert coverage_of(repo, limit=1).truncated is True


def test_what_cannot_be_computed_says_why_and_never_fakes_a_zero(repo, tmp_path):
    assert "no dated declaration" in coverage_of(repo).error         # no declaration yet: no period
    assert coverage_of(repo, ref="no-such-branch").error             # a ref git cannot resolve
    repo.branch_merge("covered", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", repo.path.as_uri(), str(shallow)], check=True)
    c = branch_coverage("HEAD", ".residue", "disensor.config.json", shallow)
    assert c.error and "shallow" in c.error
    assert branch_of_directory(tmp_path / "nowhere", "HEAD") is None


def test_the_board_shows_the_panel_and_the_fourth_figure(repo):
    repo.branch_merge("covered", "merge with a declaration", files={"src/b.py": "b"}, declare="full")
    uncovered = repo.branch_merge("uncovered", "merge without a declaration", files={"src/d.py": "d"})
    declarations, unreadable = read_directory(repo.path / ".residue")
    c = coverage_of(repo)
    page = build_html(declarations, unreadable, Source(directory=".residue"), c)
    board = page[page.index('id="v-tablero"'):page.index("</main>")]
    assert '<span class="rotulo">Merges sin declaración</span><span class="valor">1<small>de 2</small></span>' in board
    assert "Merges sin declaración en main" in board
    assert uncovered[:8] in board and "merge without a declaration" in board
    assert "Mide declaraciones, no corridas del gate" in board
    without = build_html(declarations, unreadable, Source(directory=".residue"))
    assert "sin calcular" in without[without.index('id="v-tablero"'):]

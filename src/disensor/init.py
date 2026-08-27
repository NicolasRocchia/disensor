"""Repository scaffolding: `disensor init`.

The package installs once (pipx install disensor); each repository is
initialized once with this command. Idempotent by design: running it again
respects what already exists and reports what it did, so nothing is ever
silently overwritten.

It writes four pieces, each optional by flag:
  1. disensor.config.json: the criticality level, versioned with the code.
  2. A CLAUDE.md section: the event-close trigger for Claude Code.
  3. A Claude Code skill with the full filling guide, loaded on demand
     (the same text `disensor guide` prints for any other agent).
  4. .github/workflows/disensor.yml: the CI gate. Written at this version's
     tag and immediately pinned to the commit SHA that tag points at, asking
     the canonical repository (`disensor pin`). A tag can be moved, so it is
     not a root of trust; if there is no network at init time, the tag stays
     and the report says to run `disensor pin` later.

After `pip install disensor` and `disensor init`, the user should not have
to touch anything by hand: Claude knows when (CLAUDE.md) and how (skill),
and CI enforces the result.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from . import __version__
from .guide import guide_text
from .pin import PinError, pin_text, resolve_tag_commit

# Los bloques que init escribe llevan version: sin eso, una instalacion vieja
# se queda con el procedimiento viejo para siempre, porque init conserva byte
# por byte lo que ya existe y actualizar el paquete no cambia lo que el agente
# lee. Con la marca, --upgrade sabe que reemplazar y que dejar quieto.
BLOCK_VERSION = "0.9"

CLAUDE_HEADING = "## disensor: residue declaration at event close"

CLAUDE_SECTION = f"""{CLAUDE_HEADING}

Before closing a plan, a diff or an architecture decision that crosses the
impact bar, run the round with `disensor round` and declare it with
`disensor new --round`. The full procedure, including what every exit code
means and when to stop and ask, is the disensor skill
(`.claude/skills/disensor/SKILL.md`); any other agent gets the same text from
`disensor guide`, which prints the runbook and the filling guide.

Two rules that do not depend on remembering the rest: the material is never
pasted between models by hand, and a tree that changed during a round is not
declared, it is reported.

<!-- disensor:block v{BLOCK_VERSION} -->
"""

GLOBAL_GUARD = (
    "The following applies ONLY inside repositories whose root contains "
    "`disensor.config.json`:\n\n"
)

SKILL_FRONTMATTER = """---
name: disensor
description: Run an adversarial review round and declare its residue. Use when closing a plan, a diff or an architecture decision, when `disensor round` returns something unexpected, or when filling the declaration it produced.
---

"""

RUNBOOK = f"""# Running a review event

`disensor` does the mechanical half: it decides whether a round is required,
builds the package, runs the reviewer, captures the report and anchors the
result. You do the half that needs judgement: checking findings against the
code, deciding what to incorporate, and telling the story in the pull request.

Never paste material between models by hand. If something cannot be automated,
say so instead of doing it manually and calling it a round.

## 1. Before the round

The tree has to be clean: a diff round reviews commits that already exist.
Commit your work first. The runner will not stash for you.

## 2. Run it

```
disensor round --gate diff --generator-family <your family> \\
  --base <target branch> --head HEAD \\
  --result <path outside the repository>
```

Read the exit code, do not guess from the text:

- `0`: the round ran. Its report and result are where you asked for them.
- `3`: no review required. The policy of this repository says these paths do
  not demand one. Go to the pull request; the gate will agree.
- `4`: no reviewer answered. Run `disensor reviewer suggest`. The catalogue is
  a shortcut, not the list of what is allowed: ANY assistant with a command
  line can review, whatever the vendor. Look at what this machine actually has,
  read its `--help`, and register it. An entry outside the catalogue needs the
  OWNER to approve it, so ask; do not approve it yourself.
- `5`: the tree changed during the round. Do NOT declare. Tell the user what
  appeared: a reviewer that writes is not a reviewer that only reads.
- `6`: could not decide whether a round was needed. Stop and report. This is
  never a green light.

For a plan or an architecture decision, pass `--gate plan --material <file>`:
that material does not live in the git range, and the scope cannot trigger it.
Deciding that a plan crosses the impact bar is your judgement.

## 3. Read the report and verify

Check EVERY finding against the actual code before accepting it. The reviewer
is decorrelated, not right, and an unverified finding is not a finding. Fix
what is real, refute what is not, with evidence.

## 4. If you changed anything, run the round again

The rule is the freshness of the material, not the verdict of the report. If
you incorporated even a minor finding, HEAD moved and the previous round no
longer covers what is going to be merged. `disensor new --round` will refuse
the stale result, which is the mechanism working, not an error to route around.

## 5. Declare

```
disensor new --gate diff --level <A|B|C> --round <result>
```

It arrives prefilled with what the runner observed: reviewer, anchors, hashes,
and the residue items that a degraded round owes. Fill in the findings with
their terminal states and the residue with what stayed open. `disensor guide`
explains every field. Do not invent findings or states: the artifact declares
what happened, not what should have happened.

Then `disensor validate` until it says VALID, and `disensor gate --no-comment`
green. The declaration goes in its own commit, never mixed with code.

## 6. The pull request

Its body tells the whole event: what changed, which reviewer attacked it, every
finding and what was done with it, and what stayed open. That is what the human
arbiter reads.

## When to stop and ask

- A risk that somebody has to accept (`owner_decision`).
- A finding escalated without resolution (`escalated_open`).
- No reviewer available, or an entry that needs approval.
- The tree changed during a round.

<!-- disensor:block v{BLOCK_VERSION} -->
"""


WORKFLOW = f"""# Generated by disensor init. The gate validates the declarations each PR adds.
#
# Before this workflow means anything, see "Deployment requirements" in the
# disensor README: a strict required check, CODEOWNERS over this file and over
# the configuration, and a ruleset defined outside this repository. The gate
# must be pinned by commit SHA: a tag can be moved, so it is not a root of
# trust for the code that decides whether a merge is allowed. init pins it
# automatically when it can reach the repository; if a tag reference is still
# below, run `disensor pin`.
name: disensor
on:
  pull_request:
permissions:
  contents: read
  pull-requests: write
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # the gate fails closed without the PR commit range
      - uses: NicolasRocchia/disensor@v{__version__}
"""

V01_CONFIG_KEYS = {"nivel_criticidad", "nivel_A_habilitado"}


def _is_git_repo(cwd: Path) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True, cwd=cwd, check=False,
    )
    return r.returncode == 0 and r.stdout.strip() == "true"


def _write_config(root: Path, level: str, report: list[str]) -> None:
    path = root / "disensor.config.json"
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if V01_CONFIG_KEYS & set(existing):
            report.append(
                f"WARNING {path.name}: kept, but it uses v0.1 Spanish keys; the gate will "
                "refuse them. Rename: nivel_criticidad -> criticality_level, "
                "nivel_A_habilitado -> level_A_enabled."
            )
        else:
            report.append(f"kept    {path.name} (already exists)")
        return
    config = {"criticality_level": level, "level_A_enabled": False}
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    report.append(f"created {path.name} (criticality_level={level})")


def _write_claude(path: Path, section: str, label: str, report: list[str]) -> None:
    if path.exists():
        content = path.read_text(encoding="utf-8")
        if CLAUDE_HEADING in content:
            report.append(f"kept    {label} (disensor section already present)")
            return
        joiner = "" if content.endswith("\n\n") else ("\n" if content.endswith("\n") else "\n\n")
        path.write_text(content + joiner + section, encoding="utf-8")
        report.append(f"updated {label} (disensor section appended)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(section, encoding="utf-8")
    report.append(f"created {label}")


def _write_skill(base: Path, label: str, report: list[str]) -> None:
    path = base / ".claude" / "skills" / "disensor" / "SKILL.md"
    if path.exists():
        report.append(f"kept    {label} (already exists)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SKILL_FRONTMATTER + RUNBOOK, encoding="utf-8")
    report.append(f"created {label}")


def _write_workflow(root: Path, report: list[str]) -> None:
    path = root / ".github" / "workflows" / "disensor.yml"
    rel = path.relative_to(root)
    if path.exists():
        report.append(f"kept    {rel} (already exists)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(WORKFLOW, encoding="utf-8")
    # The README requires pinning by SHA, so the scaffold should not leave the
    # user out of compliance with the tool's own doctrine. Resolution needs
    # network; without it the tag stays and the report says what is missing.
    try:
        sha = resolve_tag_commit(__version__)
    except PinError as exc:
        report.append(
            f"created {rel} (tag v{__version__}; could not resolve it to its commit SHA: "
            f"{exc} Run `disensor pin` to finish the pinning)"
        )
        return
    text = path.read_bytes().decode("utf-8")
    new, _ = pin_text(text, sha, __version__)
    path.write_bytes(new.encode("utf-8"))
    report.append(f"created {rel} (pinned to {sha}, the commit of tag v{__version__})")


def main_init(args) -> int:
    root = Path.cwd()
    if getattr(args, "upgrade", False) or getattr(args, "show", False):
        return upgrade(root, args)
    report: list[str] = []

    if not _is_git_repo(root):
        report.append("WARNING: this directory is not a git repository; scaffolding anyway")

    _write_config(root, args.level, report)

    if args.claude_global:
        home = Path.home()
        _write_claude(
            home / ".claude" / "CLAUDE.md",
            GLOBAL_GUARD + CLAUDE_SECTION,
            "~/.claude/CLAUDE.md (global)",
            report,
        )
        if not args.no_skill:
            _write_skill(home, "~/.claude/skills/disensor/SKILL.md (global)", report)
    elif getattr(args, "only_skill", False):
        # La seccion de CLAUDE.md le habla a Claude Code. Un repositorio cuyo
        # agente es otro quiere el runbook igual, y hasta ahora no habia forma
        # de pedirlo: --no-claude saltea las dos y --no-skill deja justo la que
        # no le sirve.
        report.append("skipped CLAUDE.md (--only-skill)")
        _write_skill(root, ".claude/skills/disensor/SKILL.md", report)
    elif not args.no_claude:
        _write_claude(root / "CLAUDE.md", CLAUDE_SECTION, "CLAUDE.md", report)
        if not args.no_skill:
            _write_skill(root, ".claude/skills/disensor/SKILL.md", report)
    else:
        report.append("skipped CLAUDE.md and skill (--no-claude)")

    if args.no_workflow:
        report.append("skipped .github/workflows/disensor.yml (--no-workflow)")
    else:
        _write_workflow(root, report)

    for line in report:
        print(line)
    print(
        "\nNext: `disensor prompt --gate <plan|diff|architecture>` prints the brief to "
        "reviewer from ANOTHER model family (rule R4; a free tier is enough). Then "
        "`disensor new` creates the declaration, the skill or `disensor guide` explains "
        "every field, and `disensor validate` checks it before committing."
    )
    return 0


# Lo que init escribio en versiones anteriores, por HASH del bloque completo.
# Buscar una frase adentro aceptaria un bloque que el usuario edito en otra
# linea, que es exactamente lo que no se puede pisar: el bloque tiene que ser
# lo que una version conocida escribio, entero. Los finales de linea se
# normalizan antes de hashear para que CRLF, autocrlf o un formateador no
# cuenten como una edicion del usuario.
KNOWN_BLOCKS = {
    "claude": {
        "efc57db2d88bbc34bc9455b99fdb6e93033cece2d65dc3de99ddc87fedfc2e4d": "0.7",
    },
}


def _block_hash(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").strip().encode("utf-8")).hexdigest()

UPGRADE_CONFLICT = 3


def _managed_version(text: str) -> str | None:
    """Which version wrote this block, if it still says so."""
    marca = re.search(r"<!-- disensor:block v([0-9.]+) -->", text)
    return marca.group(1) if marca else None


def _upgrade_claude(path: Path, section: str, label: str, report: list[str]) -> int:
    if not path.exists():
        report.append(f"absent {label} (run init without --upgrade to create it)")
        return 0
    content = path.read_text(encoding="utf-8")
    if CLAUDE_HEADING not in content:
        report.append(f"absent {label} (no disensor section to upgrade)")
        return 0

    inicio = content.index(CLAUDE_HEADING)
    fin = _section_end(content, inicio)
    actual = content[inicio:fin]
    version = _managed_version(actual)

    if version == BLOCK_VERSION:
        report.append(f"current {label} (block v{BLOCK_VERSION})")
        return 0

    esperado = _known_claude_block(actual, version)
    if esperado is None:
        report.append(
            f"CONFLICT {label}: the disensor section was edited, or comes from a version this "
            f"disensor does not recognise. Nothing was touched. See `disensor init --upgrade "
            f"--show` for the new text and replace it yourself if you want it"
        )
        return UPGRADE_CONFLICT

    path.write_text(content[:inicio] + section.rstrip("\n") + "\n" + content[fin:], encoding="utf-8")
    report.append(f"upgraded {label} (v{version or 'pre-0.8'} -> v{BLOCK_VERSION})")
    return 0


def _section_end(content: str, inicio: int) -> int:
    """Where the disensor section ends: the next heading of the same level, or EOF."""
    siguiente = content.find("\n## ", inicio + 1)
    return len(content) if siguiente == -1 else siguiente + 1


def _known_claude_block(actual: str, version: str | None) -> str | None:
    """Whether this block is, in full, something a known version wrote.

    A single line added by the user makes the hash differ, and then nothing is
    touched. That is the intended outcome: the safe answer to "I am not sure
    whose text this is" is to leave it alone and say so.
    """
    if version is not None:
        return None  # una version marcada que no es la actual: no conocemos su texto exacto
    return actual if _block_hash(actual) in KNOWN_BLOCKS["claude"] else None


def upgrade(root: Path, args) -> int:
    report: list[str] = []
    peor = 0

    if args.show:
        print("# CLAUDE.md section\n")
        print(CLAUDE_SECTION)
        print("\n# .claude/skills/disensor/SKILL.md\n")
        print(SKILL_FRONTMATTER + RUNBOOK)
        return 0

    if not args.no_claude:
        peor = max(peor, _upgrade_claude(root / "CLAUDE.md", CLAUDE_SECTION, "CLAUDE.md", report))
        if not args.no_skill:
            peor = max(peor, _upgrade_skill(root, report))

    if not args.no_workflow:
        _upgrade_workflow(root, report)

    for line in report:
        print(line)
    if peor == UPGRADE_CONFLICT:
        print(
            "\nSomething was edited and stayed as it is. That is the safe outcome, not a "
            "failure: nothing of yours was overwritten."
        )
    return peor


def _upgrade_skill(root: Path, report: list[str]) -> int:
    path = root / ".claude" / "skills" / "disensor" / "SKILL.md"
    if not path.exists():
        report.append("absent .claude/skills/disensor/SKILL.md")
        return 0
    actual = path.read_text(encoding="utf-8")
    if _managed_version(actual) == BLOCK_VERSION:
        report.append(f"current .claude/skills/disensor/SKILL.md (block v{BLOCK_VERSION})")
        return 0
    # La skill de 0.7 era la guia de llenado entera, reconocible por su titulo.
    if guide_text().split("\n", 1)[0] not in actual:
        report.append(
            "CONFLICT .claude/skills/disensor/SKILL.md: it was edited, or comes from a version "
            "this disensor does not recognise. Nothing was touched"
        )
        return UPGRADE_CONFLICT
    path.write_text(SKILL_FRONTMATTER + RUNBOOK, encoding="utf-8")
    report.append(f"upgraded .claude/skills/disensor/SKILL.md (guide -> runbook v{BLOCK_VERSION})")
    return 0


def _upgrade_workflow(root: Path, report: list[str]) -> None:
    """The pinned Action has to understand what the CLI now emits.

    A 0.8 CLI emitting residue/v0.4 against an Action still pinned to 0.7 gets
    the declaration rejected by a gate that never heard of that version, and the
    person finds out after doing all the work.
    """
    path = root / ".github" / "workflows" / "disensor.yml"
    if not path.exists():
        return
    texto = path.read_bytes().decode("utf-8")
    if f"@v{__version__}" in texto:
        report.append(f"current {path.relative_to(root)}")
        return
    try:
        sha = resolve_tag_commit(__version__)
    except PinError as exc:
        report.append(
            f"WARNING {path.relative_to(root)}: the pinned gate is older than this CLI, and it "
            f"will reject the schema this version emits. Could not resolve the new pin ({exc}) "
            f"Run `disensor pin` when you have network"
        )
        return
    nuevo, matches = pin_text(texto, sha, __version__)
    if matches:
        path.write_bytes(nuevo.encode("utf-8"))
        report.append(f"upgraded {path.relative_to(root)} (gate pinned to {__version__})")

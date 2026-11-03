# Changelog

What each version of disensor changed, newest first. The same log in Spanish
is [CHANGELOG.es.md](CHANGELOG.es.md).

Up to 0.10.0, each entry is the piece of the old `## Status` paragraph of the
README that described that version, transcribed as it was. Only the seams
changed: the opening "The previous version" is now "This version" (and in
0.7.0 the verb went from "added" to "adds"), a piece cut in the middle of a
sentence ends with a full stop, and the references to README sections became
links. The versions that paragraph did not describe (0.9.1, 0.6.5, 0.6.2,
0.3.0 and 0.1.0) have no entry, and there was no 0.8.0.

## 0.15.0 (2026-11-03)

This version closes what an external team reported after twelve days of real
use, plus what had been waiting on main since 0.14.0, still on residue/v0.4. A
reviewer that cannot run git now receives the change it reviews: each recipe of
the catalogue declares how it gets the material (`codex` is `agentic` and reads
the range with git; `claude`, `gemini` and `ollama` are `inline`), an entry
registered by hand is `inline` unless `reviewer add --material agentic` says
otherwise, and an `inline` reviewer in a diff round receives the diff at the
end of the package, written by `git diff-tree` with no dependence on the user's
diff configuration (`core.quotepath` and `GIT_DIFF_OPTS` are fixed), escaped
and announced when it is not UTF-8, with `material_hash` over the bytes git
wrote. The diff goes whole or not at all: `reviewer add --max-inline-bytes N`
caps any package with material inside (the diff, a plan, an architecture
decision), `ollama` and every entry registered by hand have no default and get
no such package until the owner sets one (`inline_limit_unset`), the limit of a
recipe that passes the package as an argument is measured on the real command
line before sending (32,767 UTF-16 units on Windows, 128 KiB per argument on
Linux, `ARG_MAX` on POSIX), a `.cmd` or `.bat` launcher that would take the
package as an argument on Windows is refused because `cmd.exe` cut it at its
first line break, and a reviewer that does not fit is skipped and the chain
moves on. The result of `round` becomes `disensor/round-result/v5`, where each
attempt says how it received the material, and `new --round` still reads v4;
`disensor pack --gate diff --inline` prints the same package
([#152](https://github.com/NicolasRocchia/disensor/issues/152),
[#159](https://github.com/NicolasRocchia/disensor/pull/159); recording the
delivery in the declaration waits for v0.5 in
[#160](https://github.com/NicolasRocchia/disensor/issues/160), and the context
windows of the hosted recipes are
[#158](https://github.com/NicolasRocchia/disensor/issues/158)). `reviewer
consent` records how it was given (UTC date, disensor version, and whether
standard input and output were a console, which on Windows also asks
`GetConsoleMode` because a pipe to NUL answers `isatty()` with true), `round`
prints that provenance each time it uses a consent and `new --round` carries it
into the declaration; a consent given before this version shows as "provenance
not recorded" ([#84](https://github.com/NicolasRocchia/disensor/issues/84)).
`reviewer add --yes` no longer claims to cover the repository, `consent` and
`round` resolve the repository the same way from a subdirectory,
`--generator-model` is documented, `round` warns when a reviewer of the
generator's family ran without it, and without it that reviewer is recorded as
`same_model_fresh_context`, the least independence a round can claim; the
`claude` and `gemini` recipes pass `--model {model}`, which they declared and
never sent ([#79](https://github.com/NicolasRocchia/disensor/issues/79),
[#151](https://github.com/NicolasRocchia/disensor/pull/151)). Pinning the
Action by SHA now freezes what it installs too: the actions it uses are pinned
by commit, and it installs from `requirements-action.txt`, a lock with the hash
of every file, as wheels only and into a venv of its own, with disensor built
by the locked setuptools, so nothing is resolved at run time
([#154](https://github.com/NicolasRocchia/disensor/issues/154),
[#161](https://github.com/NicolasRocchia/disensor/pull/161),
[#168](https://github.com/NicolasRocchia/disensor/pull/168)). `disensor gate`
exits with 6 when it could not decide (no range, a commit it cannot find, a
shallow clone without the merge base, a policy on the target it cannot read, or
a crash) and keeps 1 for a red verdict
([#153](https://github.com/NicolasRocchia/disensor/issues/153),
[#171](https://github.com/NicolasRocchia/disensor/pull/171)). The suite runs on
Windows and macOS as well as Linux
([#156](https://github.com/NicolasRocchia/disensor/issues/156)). The smoke of
this release, as the test asks: on 2026-11-03, on Windows 11 with Python 3.14.2
and the model gpt-5.6-sol, `tests/test_hardening.py` passed 29 tests with
codex-cli 0.153.4 and 29 with codex-cli 0.162.1, the binary the rounds use; in
both, with the canary `AGENTS.md` in the repository the recipe answered
`NINGUNO` and its control quoted the canary, with the canary in the isolated
home the recipe stopped as `context_unverified` before any inference and its
control quoted the canary, and with the canary skill in `~/.agents/skills` the
recipe answered `NINGUNA` and its control listed 41 skills, the canary among
them. The recipe of `codex` did not change, so an entry registered with 0.14.0
keeps working. What changes for whoever uses it: an entry for `claude` or
`gemini` registered with an earlier version is left out of the chain as
`stale_model_entry` and has to be registered again with `--model`; `ollama` and
the entries registered by hand need `--max-inline-bytes` before they review a
diff, a plan or an architecture decision; on Windows, `claude` and `gemini`
installed through npm resolve to a `.cmd` and no longer receive the package,
and `claude` by argument does not fit a diff of more than about 20 KB; the
Action leaves disensor out of the job's Python, so a later step that called
`disensor` or imported jsonschema relying on it no longer finds it, and CPython
3.13 free-threaded, 3.10 on Windows ARM and PyPy 3.10 cannot run it; a CI that
compares the exit code of `disensor gate` with 1 no longer sees red when the
gate could not decide; and the runbook block that `init` writes moved to 0.15,
so `disensor init --upgrade` brings it. Giving the consent again records its
provenance.

## 0.14.0 (2026-10-15)

This version is about what reaches the reviewer from the machine it runs on,
still on residue/v0.4. The `codex` recipe of the catalogue runs from an
isolated `CODEX_HOME` under the policy `codex_home/1`
(`~/.disensor/reviewers/codex/home`): its invariants are checked on disk before
every attempt, each attempt runs from its own private working directory under a
lock, the environment of the subprocess passes by allowlist, the recipe adds
`--disable` by name for plugins, apps, hooks, memories, multi_agent and
remote_plugin, turns off the bundled skills and carries the `skills.config`
built from the inventory of the disk, and the registry keeps in `executable`
the native binary behind the npm launcher (`reviewer add --executable` for a
launcher it cannot resolve); until now the owner's global `AGENTS.md` and
skills reached the reviewer with the three hardening flags on.
`disensor reviewer login codex` signs that home in once, with the owner's
terminal, and disensor never reads, copies or stores credentials.
`new --round` keeps `verified` only with the evidence of the policy and a
certified CLI version in the successful attempt, and declares anything else
`unverified` with its item; `verified` is worded as the neutralisation of
enumerated sources for concrete CLI versions and conditions, today codex-cli
0.153.4 and 0.162.1 on Windows, and the fallback reason keeps every failed
attempt with its detail instead of reporting a `quota_exhausted` the runner
never observed ([#108](https://github.com/NicolasRocchia/disensor/issues/108),
[#147](https://github.com/NicolasRocchia/disensor/pull/147)). The hostile test
of the recipe can no longer pass without the model answering: it reads only the
answer the CLI writes to a file, demands exit 0, takes `{model}` from
`DISENSOR_SMOKE_MODEL`, shares `fill_argv` with the runner and takes as the
verdict only the single word answered
([#92](https://github.com/NicolasRocchia/disensor/issues/92)); its three pairs
measure whether a source reaches the model, by the literal quote of a random
name, and not whether the model obeys an order planted in it,
`DISENSOR_SMOKE_CODEX` picks the binary, and the cleanup of each attempt
removes, under the lock, the trust entry that codex-cli 0.153.4 writes in the
home, only when it has that exact form
([#149](https://github.com/NicolasRocchia/disensor/pull/149)). The smoke of
this release, as the test asks: on 2026-10-15, on Windows 11 with Python 3.14.2
and the model gpt-5.6-sol, `tests/test_hardening.py` passed 28 tests with
codex-cli 0.153.4 and 28 with codex-cli 0.162.1; with the canary `AGENTS.md` in
the repository the recipe answered `NINGUNO` and its control quoted the canary,
with the canary in the isolated home the recipe stopped as
`context_unverified` before any inference and its control quoted the canary,
and with the canary skill in `~/.agents/skills` the recipe answered `NINGUNA`
and its control listed 41 skills, the canary among them; with the earlier
design of #92 for the repository the recipe had answered `LIMPIO` and its
control `COMPROMETIDO`, also 28 and 28, and the cleanup as published passed
again with 0.153.4, the version that writes the file it sweeps. Recorded as
debt: with codex-cli 0.153.4, on a Windows profile whose path carries an
apostrophe the cleanup would not recognise the trust entry and the next attempt
would fail closed (`confianza-clave-basica-con-escapes`). For whoever already
had `codex` registered: the entry built from the old recipe no longer matches
the catalogue, so `round` leaves it out of the chain with the instruction to
register it again; run `disensor reviewer remove codex`,
`disensor reviewer add codex --model <model> --yes`,
`disensor reviewer login codex` and, in each repository that runs rounds,
`disensor reviewer consent codex`, since the consent covers the recipe that
changed. A new entry whose home has not signed in ends its attempt as
`not_authenticated`, and the chain moves on to the next reviewer.

## 0.13.0 (2026-10-14)

This version is about what the reviewer may write, what `init` leaves in the
repository and what the README shows, still on residue/v0.4. The brief and the
pack say the same thing about writes: the suite runs so that it leaves nothing
new inside the repository, not even a file git ignores, and a write that
happened anyway is declared as an execution gap; the canonical text of the pack
changed, so the round result moves to v4, a v3 result is refused with the
reason and the `prompt_hash` of the three gates changes
([#88](https://github.com/NicolasRocchia/disensor/issues/88)). The `claude`
recipe of the catalogue starts with `--safe-mode`, still unverified, and a
registered entry whose command no longer matches today's recipe is left out of
the chain with the instruction to register it again
([#116](https://github.com/NicolasRocchia/disensor/issues/116)).
`reviewer suggest` prints the notes of each recipe it finds
([#112](https://github.com/NicolasRocchia/disensor/issues/112), in part), and
`round --check` and its exit codes 0, 3 and 6 enter what the README promises,
while the lines `round` prints on standard error stay without promise
([#78](https://github.com/NicolasRocchia/disensor/issues/78)). The runbook
`init` writes asks for the stopwatch of the cycle and defines `extra_time_sec`;
the block moves to v0.13 and the blocks with the v0.11 mark are registered by
hash so that `init --upgrade` replaces them; the README publishes the measured
cost of the corpus up to 2026-10-12, with a test that compares each number with
`.residue/`, and the examples of `spec/` drop the time and token figures the
corpus did not have
([#114](https://github.com/NicolasRocchia/disensor/issues/114)). The runbook no
longer runs a candidate reviewer before the owner's approval, closes with the
gate of the round and runs the gate with a range; the guide says that `init`
installs the runbook and that its manual round is the path without a runner;
`init --upgrade` pins the workflow left on the tag of the current version and,
without network, a SHA with this version's comment is warned about instead of
reported as current
([#121](https://github.com/NicolasRocchia/disensor/issues/121)). The two
READMEs show an extract of a real declaration from `.residue/` as the example
of the artifact, with a test that each value shown is the file's, in its order
([#111](https://github.com/NicolasRocchia/disensor/issues/111),
[#123](https://github.com/NicolasRocchia/disensor/pull/123)), and the honest
limit cites the Hide Pending experiment: in 71 of 100 records with a planted
gap the model declared that nothing was left open, and 69 of those 71 pass the
schema fragment and the four rules the experiment ran
([#137](https://github.com/NicolasRocchia/disensor/issues/137)). `tools/`
publishes the three measurement scripts behind the numbers cited to the W3C
community group
([#109](https://github.com/NicolasRocchia/disensor/pull/109)), the emitter of
the `.residue/` run as v0.1 reports and of the MUST-FAIL vectors as 5.5 records
([#119](https://github.com/NicolasRocchia/disensor/pull/119),
[#122](https://github.com/NicolasRocchia/disensor/pull/122),
[#124](https://github.com/NicolasRocchia/disensor/pull/124),
[#132](https://github.com/NicolasRocchia/disensor/pull/132)) and the script
behind the 37/24 (10) case
([#131](https://github.com/NicolasRocchia/disensor/pull/131)); `docs/notes/`
publishes the protocol, the runner and the scorer of the public-reading
measurement, with the runs of Codex and Claude
([#110](https://github.com/NicolasRocchia/disensor/issues/110), in part;
[#125](https://github.com/NicolasRocchia/disensor/issues/125)).

## 0.12.1 (2026-09-29)

This version changes wording only, still on residue/v0.4. The README, the
guide and the heading of the residue block in the gate comment no longer
describe the record as what the cycle could not close by itself: a finding
refuted with evidence closes and still enters the residue, so that phrase left
it out. They now say what the round leaves for a person to look at, and the
background essay asks what was left for a person to look at instead of what
could not be closed
([#104](https://github.com/NicolasRocchia/disensor/pull/104),
[#105](https://github.com/NicolasRocchia/disensor/pull/105)). The v0.4 schema
keeps its descriptions as published: the resource is frozen by content and
served byte for byte at its `$id`, so they are corrected in residue/v0.5, not
in place.

## 0.12.0 (2026-09-29)

This version is about reading what disensor produced, still on residue/v0.4.
The Abierto view of the report groups by what each row asks of the reader
instead of by the field of the schema it came from (waits for a decision, debt
recorded, could not be executed by the declared reason, about the reviewer,
rests on judgement, and the risks the owner accepted, folded because they ask
for nothing), opens with a digest and with what the latest declaration left
open, also when it left nothing, folds a finding into the residue item that
points at it, and the line the gate and the command print says the same digest
([#95](https://github.com/NicolasRocchia/disensor/pull/95)). A fifth view,
Tablero, is for whoever coordinates rather than reviews: decisions waiting and
since when, accepted risks, debts, what the declarations say of how each review
was conducted, declarations per week, execution gaps by reason, and what the
view cannot say; the anchor `#tablero` opens it and Abierto stays the first
view ([#97](https://github.com/NicolasRocchia/disensor/issues/97),
[#99](https://github.com/NicolasRocchia/disensor/pull/99)). The same view walks
the branch: of the merges since the commit that brought the first valid
declaration, which ones demanded a review under the policy at the tip and carry
no declaration the gate admits, judged with the gate's own functions (the checks
on a declaration a PR adds now live in `judge_artifact`, shared by the gate and
the walk, all but G9) and with the gate's reason on each row; it measures
declarations, not gate runs, and `disensor report` gains `--branch` and
`--config` ([#101](https://github.com/NicolasRocchia/disensor/pull/101)).
`disensor round` measures the reviewer's wall time and `new --round` carries it
as `reviewer_seconds` in the `dev.disensor.round` extension; the guides name
`extra_time_sec` as the end-to-end cycle and say that `token_cost` stays by
hand ([#98](https://github.com/NicolasRocchia/disensor/issues/98)). The brief's
rule against instructions in the material distinguishes their recipient, the
round's delivery says that the recipe does not load the instruction files of
the checkout, and the guide says how to refute the false positive of a reviewer
that reports the harness files as an injection
([#91](https://github.com/NicolasRocchia/disensor/issues/91)). The README and
the PyPI page put the residue first and keep the reviewers' vocabulary for
whoever searches ([#94](https://github.com/NicolasRocchia/disensor/pull/94)).

## 0.11.0 (2026-09-24)

This version hardens what disensor does on the machine that runs it and what the
pull request comment shows, still on residue/v0.4. The gate comment and the job
summary show the text of each declaration as it was written: GitHub no longer
reads it as markdown, so a declaration cannot bring emphasis, a link that says
something other than its destination, a formula or an HTML comment that hides
text, and `evidence.link` shows its destination
([#85](https://github.com/NicolasRocchia/disensor/issues/85)). `disensor round`
checks where its report and its result go before running any reviewer,
`--result -` writes to standard output, the report is never lost with the
round's temporary directory, and if something fails after the round the message
says where the report is
([#80](https://github.com/NicolasRocchia/disensor/issues/80)). Programs are run
by absolute path, git reads the repository without rewriting its index or asking
the filesystem monitor, and the README says how to run disensor over a checkout
that is not trusted
([#75](https://github.com/NicolasRocchia/disensor/issues/75),
[#77](https://github.com/NicolasRocchia/disensor/issues/77),
[#76](https://github.com/NicolasRocchia/disensor/issues/76)). `disensor new` and
`init` write LF, and a file that already exists keeps its line endings
([#82](https://github.com/NicolasRocchia/disensor/issues/82)). The `pack_hash`
of a round is canonical, so it can be recomputed away from the machine that ran
the round, and the round result moves to v2
([#73](https://github.com/NicolasRocchia/disensor/issues/73), phase 1). The
guide, the runbook and the `CLAUDE.md` section say that the consent to send
material out of the machine is the owner's to give, and `init --upgrade`
recognises every block 0.9 wrote
([#84](https://github.com/NicolasRocchia/disensor/issues/84), option 3). The
release log moves out of the README into this file, and the README says how to
run the gate outside GitHub
([#68](https://github.com/NicolasRocchia/disensor/issues/68),
[#72](https://github.com/NicolasRocchia/disensor/issues/72)). `tools/` publishes
the emitter of the 42 evidence objects reported to the W3C community group
([#67](https://github.com/NicolasRocchia/disensor/pull/67)), and the census of
`gap_reason` that measures the scope of residue/v0.5
([#83](https://github.com/NicolasRocchia/disensor/pull/83)).

## 0.10.0 (2026-09-16)

This version adds `disensor report`: one self-contained HTML file that reads
every declaration of the repository and answers what stayed open (declared open
on a date, with no later evidence of closure, because the artifact has no field
for closure), each declaration with its residue first, the corpus as declared,
and the critical and major findings that changed the code. It reads without
validating, loads nothing from the network, and is a pure function of the
declarations: two runs over the same commit give identical bytes. Nobody types
it: when `disensor gate` reaches a green verdict it writes
`informe-residuo.html` at the repository root from the git objects it judged,
only if git ignores the file, and `disensor init` leaves that line in
`.gitignore`.

## 0.9.6 (2026-09-08)

This version fixes the gate comment for the two reviewer classes v0.4 added: a
declaration carrying `reviewer_correlation` or `reviewer_hardening_gap`, which
R11 and R12 require when a reviewer is declared with degraded independence or
unverified hardening, validated and then aborted the gate with a `KeyError`
while the comment was being rendered, also with `--no-comment`, so the degraded
mode v0.4 made declarable broke the gate the first time anyone declared it
honestly ([#56](https://github.com/NicolasRocchia/disensor/issues/56)). The
comment now names both classes and the reviewer each item is about, next to the
finding when there is one, and a test keeps the render's table equal to the
schema's enum. The opening line and the PyPI summary say what this is with the
vocabulary people search for (adversarial, cross-model AI code review with a
residue declaration), and a new section says how it relates to other approaches
and to Adversarial Review (arXiv 2608.18167).

## 0.9.5 (2026-08-31)

This version carries what the first independent reproduction left: an external
reader cloned the v0.9.4 tag, verified the frozen hashes and ran both
implementations cold, with zero divergences, and found that the evidence-plane
README claimed a stale count. The count is fixed with its breakdown said out
loud, every numeric claim in these documents is now compared in CI against the
thing it counts, `disensor --version` exists (it exited with a usage error, and
the first command a stranger types deserves better), and the version literal is
tied to the packaging metadata by test.

## 0.9.4 (2026-08-29)

This version closes residue/v0.4: the TypeScript port validates v0.2, v0.3 and
v0.4, so the two-independent-implementations claim covers the version the CLI
emits; conformance runs 89 vectors across three suites plus 28 shared cases
fixing the form of a schema identifier and which rules reach which declaration,
and it fails when a known version has no vectors declaring it; the Level A floor
is enforced; referential integrity enters as R13, guarded so it does not reach
frozen versions; the frozen resources are verified by content and not only by
name; and which rules reach which declaration stopped depending on the order the
lines happen to be written in.

## 0.9.3 (2026-08-27)

This version writes down when the gate Action's own pin goes up: it travels in
the next PR of real work, except when the release fixes gate security or changes
the schema version, and it says out loud that this is a convention rather than a
control ([#17](https://github.com/NicolasRocchia/disensor/issues/17)).

## 0.9.2 (2026-08-27)

This version makes `disensor guide` hand over the event runbook as well as the
artifact filling guide, so an agent that is not Claude Code gets from one
command the same material the Claude Code skill carries, which is what the
documentation had been promising since the round became orchestrated
([#30](https://github.com/NicolasRocchia/disensor/issues/30)). `--runbook` and
`--filling` ask for one of the two, and `init --only-skill` writes that runbook
without the `CLAUDE.md` section, for a repository whose agent is another one.

## 0.9.0 (2026-08-27)

This version orchestrates the round: `disensor round` packages the material,
runs a reviewer registered on your machine, captures the report and anchors the
result to the commits it actually reviewed, and `disensor new --round` builds
the declaration from it. Any assistant with a command line can be the reviewer;
the packaged catalogue is a shortcut, not a list of what is allowed.
residue/v0.4 makes a round without a second model family declarable as the
degraded mode it is, instead of impossible to declare at all, and each schema
version is now validated under its own rules. `disensor init --upgrade` brings
an older installation up to this procedure without touching anything you edited.

## 0.7.0 (2026-08-24)

This version adds `disensor pin`, which freezes the Action to the commit SHA of
its release tag.

## 0.6.4 (2026-08-23)

This version makes the packaged Spanish guide reachable with
`disensor guide --lang es`.

## 0.6.3 (2026-08-21)

The long-form documentation is bilingual since v0.6.3: `README.md` is the
English one that PyPI renders, `README.es.md` is the Spanish, and the filling
guide ships in both languages.

## 0.6.1 (2026-08-20)

Releases are published to PyPI via Trusted Publishing (OIDC, `release.yml`): no
tokens on any machine.

## 0.6.0 (2026-08-15)

The move to residue/v0.3 hardens three points of the artifact, closing issues
[#5](https://github.com/NicolasRocchia/disensor/issues/5),
[#7](https://github.com/NicolasRocchia/disensor/issues/7) and
[#8](https://github.com/NicolasRocchia/disensor/issues/8). See
["Schema migration: residue/v0.2 to residue/v0.3"](README.md#schema-migration-residuev02-to-residuev03).

## 0.5.0 (2026-08-13)

v0.5 ships the packaged adversarial brief with a reproducible hash.

## 0.4.0 (2026-08-13)

v0.4 rewrote the gate so that it derives the PR scope from git (see
["What the gate enforces"](README.md#what-the-gate-enforces)).

## 0.2.0 (2026-08-11)

Decision closed in v0.2: schema keys and CLI in English (Spanish remains as CLI
aliases).

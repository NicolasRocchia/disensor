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

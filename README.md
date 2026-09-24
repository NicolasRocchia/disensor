# disensor

Your AI wrote the code. Another AI reviewed it. What happened in that review
ends up as a JSON file in your repo, next to the code it judges.

[![PyPI](https://img.shields.io/pypi/v/disensor)](https://pypi.org/project/disensor/)
[![CI](https://github.com/NicolasRocchia/disensor/actions/workflows/ci.yml/badge.svg)](https://github.com/NicolasRocchia/disensor/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/disensor)](https://pypi.org/project/disensor/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/NicolasRocchia/disensor/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21633495.svg)](https://doi.org/10.5281/zenodo.21633495)

*Este documento también está [en español](https://github.com/NicolasRocchia/disensor/blob/main/README.es.md).*

Adversarial, cross-model AI code review that ends in a residue declaration: a
CLI and a CI gate that validate the record the review leaves behind. Reference
implementation of the artifact defined by the **controlled disagreement**
method: one model generates, a model from another family attacks, the
generator verifies every finding, and the cycle ends when each finding has been
resolved, refuted with evidence, or escalated to a human.

The artifact this repo defines and enforces records how each review event ended:
the findings with their terminal state, and the **residue**: what the cycle
could not close by itself and rests on someone's judgement. The declaration
lists residue, not coverage: it aims the human reviewer's scrutiny instead of
reading as a seal of quality.

Method paper: Rocchia, N. (2026), *Desacuerdo controlado: revisión adversarial
automatizada con un segundo asistente de código en el desarrollo de software*,
DOI [10.5281/zenodo.21633495](https://doi.org/10.5281/zenodo.21633495). The
paper is in Spanish; the glossary at the end maps its terminology to the schema.

## What is here

- `spec/residue.schema.json`: the artifact schema (JSON Schema 2020-12), version residue/v0.4. Superseded versions keep their own frozen resource next to it.
- `spec/examples/`: three example artifacts, including a real anonymised event and the minimized profile with no free text.
- `src/disensor/`: Python package with the validator (rules R0 to R13), the CI gate (checks G1 to G9), the PR comment rendering, the HTML residue report (`report`), artifact and repository scaffolding (`init`), and the packaged filling guide (`GUIDE.md`).
- `action.yml`: composite GitHub Action, ready to use.
- `docs/integracion-claude-code.md` (Spanish only): how the real flow (Claude Code plus a reviewer from another family) emits the artifact at the close of each event.
- `docs/antecedentes.md` (Spanish only): where the method sits relative to the literature (residual doubt and defeaters, design rationale and its capture bottleneck, multi-agent adversarial review, governance runtimes, supply chain provenance), with the verification status of each reference.

## Quick start

The package is installed once (globally); each repository is initialised once:

```bash
pip install disensor        # or pipx install disensor, recommended for CLIs

disensor init               # at the repo root: config, CLAUDE.md, filling skill and CI workflow
disensor pin                # the gate Action, frozen to the commit SHA of the release tag

disensor reviewer suggest              # which reviewers this machine has, offline
disensor round --gate diff --generator-family anthropic --base main --head HEAD --result ../result.json
disensor new --gate diff --level B --round ../result.json   # declaration from that round

disensor prompt --gate diff            # the adversarial brief, to hand to a reviewer from another family
disensor pack --gate diff --base main --head HEAD          # the full package, if you drive the round yourself
disensor new --gate diff --level B     # template prefilled in .residue/
disensor validate .residue/<id>.json   # schema + rules R0 to R13
disensor gate --no-comment --base main --head HEAD   # what CI will run, locally; green writes the report
disensor report --open                 # the residue report, in the system browser

disensor guide                         # the filling guide, for any agent or human
disensor guide --lang es               # the same guide in Spanish
disensor prompt --gate diff --hash     # the sha256: of the packaged brief, which is what prompt_hash wants
disensor hash consigna.md              # or the hash of yours, if you wrote it
```

The brief ships inside the package, so its hash is reproducible: anyone can
recompute it from the same version and see what the reviewer was actually asked.
If you edit it, the hash changes and the artifact declares that a different
brief was used, which is exactly what the field is for.

## Trying it without touching your CI

There are two modes and it pays not to mix them. To **try it**, you need no
workflow, no required checks and no organisation permissions: the gate runs the
same on your machine and says exactly what it would say in CI.

```bash
disensor init --no-workflow          # config, CLAUDE.md and skill; without touching .github/
disensor prompt --gate diff          # the brief, to the reviewer from another family
disensor new --gate diff --level B   # and you fill the declaration with what happened
disensor validate .residue/<id>.json
disensor gate --no-comment --base <base-sha> --head HEAD
```

Only when you want it to **enforce** do you run the full `disensor init` (which
writes the workflow) and apply the deployment requirements below. Before that it
is a tool that tells you how you would do; after that it is a control that
blocks.

The Spanish v0.1 subcommands and flags (`nuevo`, `validar`, `--compuerta`,
`--nivel`, `--directorio`, `--sin-comentario`) still work as aliases.

`disensor init` writes, idempotently, the `disensor.config.json` (the level
travels with the code, in a versioned file), the event-close section in
`CLAUDE.md`, the Claude Code skill with the event runbook
(`.claude/skills/disensor/SKILL.md`, loaded on demand at the close of each
round) and the gate workflow; whatever already exists is respected and reported.
The principle is that after `pip install disensor` and `disensor init` the user
touches nothing by hand: Claude knows when (CLAUDE.md) and how (the skill), any
other agent gets the same from `disensor guide`, which prints that runbook and
the filling guide, and CI enforces the result.
Resulting config:

```json
{
  "criticality_level": "B",
  "level_A_enabled": false
}
```

And the workflow (see `docs/ejemplo-workflow.yml`):

```yaml
on: pull_request
permissions:
  contents: read
  pull-requests: write
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: NicolasRocchia/disensor@v0.11.0
```

The gate validates the declarations **the PR adds**, applies the policy and
posts the result as a comment (updated in place on every push). Everything it
decides comes from git objects in the `merge-base..head` range, never from the
working tree: on a `pull_request` event the checkout leaves the synthetic merge
commit while `head.sha` points at the real head, so reading from disk would
classify one tree and validate another.

## The orchestrated round

The round used to be the part you did by hand: package the material, hand it to
another assistant, bring the report back, remember to check the tree afterwards.
`disensor round` does the mechanical half, so nothing is ever pasted between
models by hand.

```bash
disensor reviewer suggest          # what this machine has, offline
disensor reviewer add codex --model <model> --yes  # once per machine, with a model your account runs

disensor round --gate diff --generator-family anthropic \
  --base main --head HEAD --result ../result.json
disensor new --gate diff --level B --round ../result.json
```

**Any assistant can be the reviewer.** We happen to run Claude Code with Codex
attacking, because that is what we have; the tool is not tied to either. Any
command line that takes a text and returns a text works: another vendor's CLI,
a local model through Ollama, whatever you already pay for. The packaged
catalogue is a shortcut for the cases we already tested, not a list of what is
allowed. If yours is not in it, your assistant reads its `--help`, proposes the
entry, and you approve it once.

Two things are worth knowing about that approval. The reviewers live on your
machine (`~/.disensor/reviewers.json`), never in the repository: an entry is
executable code, and a pull request that could add one would run commands on the
machine of whoever reviews it. And what your assistant proposes is not
registered until you say yes, because a repository can carry instructions
addressed to your assistant, and registering an executable that will later
receive your private code is your decision, not its.

**What runs alone, and where you come in.** The runner asks the policy whether a
round is required at all (a change that only touches exempt paths does not spend
a token), refuses to run on a dirty tree, picks the most independent reviewer
available, runs it, captures the report and emits a result anchored to the exact
commits reviewed. It never reads the report: judging what the reviewer said is
your assistant's work. You appear when you consent to material leaving your
machine, when a risk needs an owner, when something is escalated without
resolution, and at the pull request.

**When there is no second family.** The method wants a reviewer from another
model family, and that is still what the policy demands at Level A. Below that,
a round with the same model and no context is a declarable degraded mode: the
declaration records the independence it actually had, why it settled for less,
and a residue item saying that the errors the model shares with itself were not
covered. Worse than the real thing, and infinitely better than not being able to
declare what happened.

## The residue report

`disensor report` reads the declarations and writes one self-contained HTML
file: CSS and JS inline, no network, a Content-Security-Policy that forbids
loading anything, system fonts. It opens with a double click, travels by mail
and works on a machine without internet. It reads, it does not validate: a file
that is not the shape of a declaration is listed at the end and the rest goes
on. The residue comes first and the coverage goes in grey: the incorporated
findings describe the record, not the quality of the code, and nothing in the
page can be read as a seal of approval. The first view, Abierto, gathers
everything that asked for a decision across the whole repository, oldest
first. The artifact has no field to say that something closed, so the view
does not say "open": it says "declared open on <date>, no later evidence of
closure", and explains why at the top (issue #6). The report is a pure function
of the declarations: no generation timestamp, the footer names the commit it
was read from, and two runs over the same commit give identical bytes.

Nobody has to type the command for the report to exist. When `disensor gate`
reaches a green verdict it writes `informe-residuo.html` at the repository
root, read from the same git objects it judged, and the last line of its output
is the path. It writes it only when git ignores the file (`disensor init` and
`init --upgrade` add the line to `.gitignore`), because `disensor round` demands
a clean tree. Best effort and never silent: a failure of the report never
changes the verdict, and ends in a `[gate] report: FAILED` line. `--report-out`
picks another destination and `--no-report` skips it. The command itself is
for the rest: the directory as it is on disk, a date range, another file.

```bash
disensor report --open                                       # every declaration, in the system browser
disensor report --since 2026-09-01 --out /tmp/residuo.html   # recent ones only, somewhere else
```

## What the gate enforces

Per artifact (rules R0 to R13): coherence between findings and residue, counts
that add up, family decorrelation between generator and reviewer, mandatory
material evidence in verifiable refutations (`text`, `link` or `hash`) against a
verifiable target (`verification.against` other than `none`), mandatory human
attention in interpretive refutations, a fix verified before closing a finding
in a diff gate, rejection of generic markers (in English and in Spanish), and a
minimized profile with the free text R9 covers stripped. From residue/v0.4 they
also cover the coherence between declared independence and the families and
models the declaration names (R4), the minimums of the degraded mode per level
(R11) and its per-reviewer correlation residue (R12), and from this version the
integrity of local identifiers: unique, and every reference to a reviewer
resolves against the declared ones (R13).

Per artifact, against the PR: level equal to the repository's declared one (G2),
Level A blocked while governance is not validated (G3), reviewer confinement
policy per level (G4), and membership of the reviewed commit in the PR (G5),
which for the diff gate also requires `base_commit`, because a diff review
identifies the pair (reviewed base, reviewed head) and not a loose head.

Per PR:

- **G1**: if the PR touches paths that require review, it adds at least one valid declaration.
- **G6, coverage**: every changed path is covered by a declaration whose gate the scope policy accepts for that path, and which **qualifies** for it, meaning the path did not change between the reviewed commit and the head. A stale declaration covers nothing.
- **G7, integration witness**: some declaration saw the complete final tree. Path-by-path coverage is not enough: two side branches reviewed separately and later merged cover every path between them while nobody reviewed the integration.
- **G8, evidence is append-only**: a PR cannot modify, delete or rename declarations that were already there, nor reuse an existing `event_id`.
- **G9, new declarations state the current version**: a declaration the PR adds has to declare `residue/v0.4`. Superseded versions are still read so that history is not rewritten; that readability is not a permit to keep emitting under the weaker rules. The evidence plane applies the same criterion at ingestion.

The gate **fails closed**: if it cannot resolve the PR range, it does not go
green. A compliance control that cannot decide does not approve.

Honest limit, inherited from the protocol: the machine detects the empty field
and the generic marker, not the false declaration. Human sampling of merged PRs
remains the only real defence against cosmetic compliance.

## Scope policy

Which gate is accepted for each path is declared in the config, and **is always
read from the current tip of the target branch**, never from the PR checkout.
From the target and not from the merge-base, which is a different question: the
merge-base is as old as the branch, so a branch created before the repository
hardened its policy would drag the old one along. The PR scope is measured
against the merge-base; the policy that governs is the one the target has today.
That is why a PR that changes the policy is judged by the previous policy, which
is correct and also avoids the mutual deadlock of the naive design, where the PR
that loosens the configuration is rejected by the very rule it wants to change
and no transition is possible.

```json
{
  "criticality_level": "B",
  "level_A_enabled": false,
  "gate": {
    "required": true,
    "scope": [
      { "paths": ["docs/adr/**"], "accepts": ["architecture", "diff"] },
      { "paths": ["CHANGELOG.md"], "accepts": [] },
      { "paths": ["**"], "accepts": ["diff"] }
    ]
  }
}
```

The first matching entry wins. `accepts: []` is an explicit exemption, which is
the governed way out for changelogs or automated PRs. Patterns are anchored at
the root, `*` does not cross `/`, `**` matches zero or more complete segments,
and matching is **case sensitive byte by byte** so that the same policy means
the same thing on any runner. A path that matches nothing requires `diff`: the
absence of policy is not a permit.

**Non-relaxable floor**: the effective configuration path,
`.github/workflows/**` and the evidence directory always require `diff`,
whatever `scope` says. Without that floor, an innocent-looking policy such as
`**/*.yml` with `architecture` would downgrade the workflows, which are the
source of the control itself.

## Deployment requirements

This is a requirement, not a suggestion. The gate runs inside the workflow it
audits, so there is a boundary no code of its own can cross and the platform has
to resolve:

- **Strict required check** (or merge queue) on `pull_request`, so that the check has to correspond to the latest head.
- **CODEOWNERS** over the effective configuration path (it may not be called `disensor.config.json` if `--config` is used) and over `.github/workflows/`.
- **Organisation ruleset or required workflow**, defined outside the audited repository.
- **Pin the Action by SHA**, not by tag: a tag is movable and is not a root of trust. `disensor init` resolves the tag of the installed version to the commit it points at and writes the workflow already frozen; without network at init time the tag stays and `disensor pin` finishes the job. The command resolves annotated tags to the commit they wrap, never to the tag object, which is the classic trap of doing it by hand. This repository's documentation still uses the tag, because it documents which version corresponds; the frozen SHA is produced by whoever deploys.
- **Secret scanning with push protection** on the repository that hosts `.residue/`: evidence quotes real material and lives in git forever, and the validator checks shape, not meaning, so nothing of disensor's own will catch a pasted credential. Detection belongs to the platform; the remedy for a leaked secret is rotation, not deletion ([#14](https://github.com/NicolasRocchia/disensor/issues/14)).
- **Bootstrap**: the first PR that adds the config and the workflow cannot make itself the root of trust. Initial activation is an administrative step, prior to the gate meaning anything.
- **When the pin goes up**: the workflow sits in the non-relaxable floor, so raising the pin through a PR costs an adversarial round for a change whose correctness a `git rev-parse` verifies better than any model. The convention in this repository is that a new pin **travels in the next PR of real work**, with its declaration, rather than in a PR of its own. **Exception**: if the release fixes gate security or changes the schema version, the pin goes up immediately, because the window in which the repository judges itself with the previous version stops being harmless: an old gate does not know the new contract and rejects what the freshly published CLI emits. This is a convention, not a control: as long as the branch does not require pull requests with bypass disabled for administrators too, nothing prevents pushing the pin directly ([#17](https://github.com/NicolasRocchia/disensor/issues/17)).

Explicit limit: reading the policy from the base turns a one-step bypass into a
two-step one, it does not eliminate it. Whoever can merge a relaxation uses it
on the next PR. And none of this protects against a workflow that was modified,
skipped or replaced. Only the platform resolves that.

### Outside GitHub

The verdict does not depend on GitHub; the comment does. With `--base`,
`--head` and `--no-comment`, the gate needs no `GITHUB_*` variable and makes no
network call: it decides from the git objects of the range, so any CI that can
run Python over a checkout of the repository can host it. It takes four things:

- **The range, from the CI's own variables.** `--base` is the tip of the target
  branch, where the policy is read from, and `--head` is the last commit of the
  change. In a GitLab merge request pipeline, the target branch is fetched by
  name (`git fetch origin "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"`) and `--base`
  is `FETCH_HEAD`; `--head` is `CI_COMMIT_SHA`, or
  `CI_MERGE_REQUEST_SOURCE_BRANCH_SHA` in a merged results pipeline, where
  `CI_COMMIT_SHA` is the temporary merge commit. Not
  `CI_MERGE_REQUEST_DIFF_BASE_SHA`: that is the merge base, and the policy would
  be read from an older commit than the tip of the target.
- **The whole history**, the equivalent of `fetch-depth: 0`: without it there
  is no merge base and the gate fails closed. In GitLab, `GIT_DEPTH: "0"`.
- **`--no-comment`, and the verdict by exit code**: 0 is green, and 1 is red or
  a gate that could not decide. The body the comment would carry goes to
  stdout, and on a green verdict `--report-out <file>` writes the HTML report
  where the CI can archive it.
- **The same deployment requirements, under the names each platform gives
  them**: a required check that runs on the head of every change, the
  configuration and the pipeline definition owned outside the audited
  repository, and the executable pinned to an exact version of the package,
  run the way `action.yml` runs it (`python -I -m`), because the working
  directory is the checkout being judged.

What does not travel is the pull request comment and the job summary, which
write to GitHub; whoever wants them on another platform builds them from
stdout. A minimal GitLab CI job is in
[`docs/ejemplo-gitlab-ci.yml`](https://github.com/NicolasRocchia/disensor/blob/main/docs/ejemplo-gitlab-ci.yml).

## What it does not do

The CI gate runs no models, asks for no API keys and sends no code to any
service: it validates a JSON that is already versioned in the repo. Running the
round is optional and stays on your machine: `disensor round` drives a reviewer
CLI you registered yourself, and a cloud reviewer needs scoped consent before
any material leaves. The artifact's `minimized` profile is meant for
environments where the text of the findings cannot leave.

In the `minimized` profile, R9 strips the finding fields the protocol defines,
`text` and `link` from every piece of evidence, the residue item `description`,
and a `repository` that starts with `http`. The schema also requires every value under
`extensions` to be opaque (a `sha256:` hash, a number, a boolean, `null`, or
containers of those) and every key to have the shape of an identifier: a name,
not a message.

**The profile narrows the leak channel; it does not close it.** R9 does not
reach every string in the artifact. `residue.declaration`, `event.pr`,
`verification.detail`, `human_arbiter.id` and `lead_acceptance` are some of the
fields that still admit free prose, and the list is not meant to be exhaustive:
read the schema for the current surface. Note that a hashed `repository` does
not help if `event.pr` carries the URL. The schema says as much about the
extension space: an identifier-shaped key can still carry a message. Treat
`minimized` as a reduction of surface, not as a guarantee that nothing leaves.

**On a checkout you do not trust**, run disensor with the full path of an
interpreter you trust and `-I`: `/path/to/venv/bin/python -I -m disensor ...`
(on Windows, `C:\path\to\venv\Scripts\python.exe -I -m disensor ...`). The
`disensor` command that pip installs starts Python without isolation, so
`PYTHONPATH` and `PYTHONUSERBASE` decide what gets imported before disensor
runs, and a relative value points into the directory you are in; `-I` turns
that off, as it does in the Action. The full path matters on Windows: `cmd.exe`
looks for a bare `python` or `disensor` in the current directory before the
PATH. `-I` also ignores the user site, so disensor has to be installed in that
environment, not with `pip install --user`. And clone the repository yourself:
a directory that arrives with its `.git` inside brings a git configuration that
every git command obeys there, disensor's included.

## How this relates to other approaches

Most of the vocabulary people use to search this space describes the
**review**: who reviews, with how many models, in what order. disensor sits one
step later. It defines and validates the **record** the review ends with, and
enforces it on the pull request. So it shares the review side with each of
these terms and differs in what it adds.

- **Cross-model, multi-model code review.** The method requires it: the reviewer has to come from a model family other than the generator's (R4), and since residue/v0.4 the declaration states the independence the round actually had. What disensor adds is that the outcome is written down, versioned and gated, whichever models took part.
- **Maker-checker.** The same separation between who builds and who certifies, with one difference in what the checker signs: not "approved" but the list of what was not closed. The human arbiter (R0) is the last checker, and without one the artifact does not validate.
- **Second-opinion review.** A reviewer from another family is a second opinion by construction. disensor does not stop at the opinion: every finding has to reach a terminal state, and a refutation needs evidence, not a rebuttal.
- **AI reviewing AI-generated code.** The case the method was written for. Its known limit is stated above: the gate detects the empty field and the generic marker, not the false declaration, so human sampling of merged pull requests stays part of the design.
- **Model diversity, decorrelated reviewer.** The reason behind R4 is decorrelation: two models of the same lineage tend to fail in the same places. The size of that effect is not measured, and [`docs/antecedentes.md`](docs/antecedentes.md) says so; the rule is a plausible design, not a demonstrated result.

Existing tools cover the review side well: Augment Code's guide to adversarial
code review, the
[`alecnielsen/adversarial-review`](https://github.com/alecnielsen/adversarial-review)
loop between Claude and Codex, and the review features of assistants such as
GitHub Copilot. Any of them can feed a residue declaration; none of them
replaces it, because none leaves a versioned, gated record of what the review
could not close.

### Relation to Adversarial Review (arXiv 2608.18167)

Qiu, E. S. and Gill, J. (2026), *Adversarial Review: Structured Disagreement
for Grounded Agentic Code Review*,
[arXiv:2608.18167](https://arxiv.org/abs/2608.18167). The names overlap and the
concerns are close, so the difference is worth stating.

AR is an **orchestration protocol**: a main coding agent works with a reviewer
and a critic, the critic audits the review through structured disagreement
before the main agent edits, and the result is measured by pass rate and F1 on
benchmarks. The gate neither orchestrates nor runs models: disensor defines
the **artifact** any review cycle ends with, validates it, and enforces it in
CI. The optional `disensor round` does run the reviewer step, with a reviewer
installed on your machine, and never judges what it returns; the dialogue
between reviewer and critic that AR orchestrates is not something disensor
does.

AR reports a **false-consensus** failure mode, agents converging on agreement
without sufficient evidence, and addresses it inside the protocol by making the
critic ground its disagreement in evidence. disensor attacks the same problem
from the other side: the declaration lists **residue, not coverage**, a human
arbiter is mandatory (R0), and generator and reviewer must come from
**different families** (R4). Disagreement is not a step of the protocol here:
it is what stays recorded when the cycle does not close by itself.

The two are complementary: an AR cycle can end in a residue declaration, and
what the critic could not settle with evidence is exactly what the declaration
carries to a human. Reading notes, with the abstract and the BibTeX entry, in
[`docs/notes/arxiv-2608.18167.md`](docs/notes/arxiv-2608.18167.md).

## What each number promises

The package and the schema are numbered separately, and they promise different
things.

**Stable within a major series of the package.** The exit codes of
`disensor round` (`0` reviewed, `1` error, `3` no round required, `4` chain
exhausted, `5` tree modified during the round, `6` could not decide whether a
round was required); the subcommands and flags documented in this file; the four
inputs of the Action (`github-token`, `directory`, `config`, `python-version`);
and the keys of `disensor.config.json`, which already fail closed on anything
unknown. Breaking these needs a major.

**Versioned on their own.** The declaration schema (`residue/vX.Y`, stated inside
every artifact) and the result of `disensor round` (`result_version`). Neither
follows the package numbering, and a change in them is not a package major.

**No promise.** The reviewer registry on your machine, the recipe catalogue, and
the ingestion API of the evidence plane. The catalogue is the one surface that
depends on third-party CLIs: the Codex recipe changed the day an account stopped
offering the model it named.

**One asymmetry worth knowing before you pin.** The gate demands that a
declaration a PR adds states the current schema version, and it rejects both
superseded and *newer* ones. The Action installs the CLI from its own checkout,
so the SHA you pin fixes which schema version your gate accepts. A schema change
therefore requires updating that pin before declarations under the new version
can merge.

## Conformance between implementations

`spec/vectors/` holds the conformance vectors, one suite per schema version: 11 artifacts for v0.2, 35 for v0.3 and 43 for v0.4, each with its expected
verdict (valid or not, and the rule labels that must fire). Every validator
implementation has to pass them identically: the Python reference runs them in
its suite (`tests/test_vectors.py`) and the TypeScript port of the evidence
plane runs them with `npm run conformidad`. Labels are compared, not messages.
The vectors are regenerated with `python -m disensor.vectors <directory>`. The generator produces the current schema version and refuses to write over a suite that declares another one: overwriting a historical suite would erase the only negative coverage those rules have. The runner fails if a known version has no vectors declaring it, because otherwise a version can be claimed as supported without anything checking it, which is exactly how v0.2 got here. `spec/version_ordinality.json` carries the other shared vectors: the form of a schema identifier and which rules reach which declaration, both verified by both implementations. In total, conformance runs 89 vectors across three suites plus 28 shared cases.

Each vector is validated under the schema of the version it declares. The
TypeScript port implements the rules of **v0.2, v0.3 and v0.4**, so the
two-independent-implementations claim covers the version the CLI emits. Handed a
version it does not implement it says so and refuses, rather than returning a
verdict without having run the rules that version added.

`plano-evidencia/` holds the ingestion Worker (Cloudflare Workers plus D1) with
the TypeScript port of the validator and the append-only integrity receipt. See
its README for verification status and deployment.

## Glossary EN-ES

The contract (schema keys and enums, CLI) has been English since v0.2. The
method paper is in Spanish, so this maps the contract you read here to the
terminology you will find there:

| Schema/CLI (EN) | Paper (ES) |
|---|---|
| residue | residuo |
| finding | hallazgo |
| gate (plan, diff, architecture) | compuerta (plan, diff, arquitectura) |
| criticality_level | nivel de criticidad |
| profile full / minimized | perfil completo / minimizado |
| actors: generator, reviewers, human_arbiter | actores: generador, revisores, árbitro humano |
| family | familia (de modelo) |
| confinement (permissions, sandbox, read_only_by_instruction, no_confinement) | confinamiento (permisos, sandbox, solo lectura por instrucción, sin confinamiento) |
| prompt_hash | consigna (hash de la consigna adversarial) |
| final_state: incorporated, debt_recorded, owner_decision, refuted_verifiable, refuted_interpretive, escalated_open | estado final: incorporado, deuda registrada, decisión del dueño, refutado verificable, refutado interpretativo, escalado abierto |
| residue classes: escalation_without_decision, principal_refutation, execution_gap | clases de residuo: escalado sin decisión, refutación del principal, gap de ejecución |
| abbreviated_path / protected_cases_touched | ruta abreviada / casos protegidos |
| fix_verification | verificación de la corrección |
| lead_acceptance | aceptación de referente |
| declared_absence / declaration | ausencia declarada / declaración |
| metrics: counts, valid, false_positives | métricas: conteos, válidos, falsos positivos |

Migrating from v0.1: rename `.residuo/` to `.residue/`, the config keys
(`nivel_criticidad` to `criticality_level`, `nivel_A_habilitado` to
`level_A_enabled`) and the artifact keys according to the glossary. The
validator recognises v0.1 artifacts and says so explicitly; the gate loudly
rejects a config with old keys instead of applying defaults in silence.

## Schema migration: residue/v0.2 to residue/v0.3

Mind the ambiguity: this section is about the version **of the schema**; the
next one is about versions **of the package**. They are two different numberings.

v0.3 renames no keys and adds none. It hardens the points where the declared
guarantee was stronger than the implemented one (three found before the round
and two that v0.3's own adversarial round added), and adds one value to an enum:

| Used to be valid | Now rejected | Why |
|---|---|---|
| `refuted_verifiable` with `evidence: {}` | The evidence object has to carry `text`, `link` or `hash` | v0.2 required the object to be present, not its content: a finding could be closed without touching the code by declaring empty evidence ([#5](https://github.com/NicolasRocchia/disensor/issues/5)) |
| `refuted_verifiable` with `verification.against: "none"` | `against` has to be `repository`, `execution` or `external_source` | Refuting without having verified anything is a contradiction, not a refutation ([#5](https://github.com/NicolasRocchia/disensor/issues/5)) |
| `minimized` profile with free text in `extensions` | Every value under `extensions` has to be opaque: `sha256:` hash, number, boolean, `null`, or containers of those | The extension space is not interpreted by the rules, so text parked there left the environment while the profile claimed nothing left ([#8](https://github.com/NicolasRocchia/disensor/issues/8)) |
| `refuted_verifiable` with evidence present but blank (`link: ""`, `text` of pure whitespace) | `text` and `link` have to carry at least one non-blank character | Presence without content reopened the [#5](https://github.com/NicolasRocchia/disensor/issues/5) hole through the weakest leg of the `anyOf`; v0.3's own adversarial round caught it |
| `minimized` profile with free text in the **keys** of `extensions` | Every key under an opaque object has the shape of an identifier (`[A-Za-z0-9._:-]`, at most 128) | An opaque value is not enough if the message travels in the name: [#8](https://github.com/NicolasRocchia/disensor/issues/8) closed the values and left the keys |

And `verification.against` now accepts **`external_source`**: literature,
third-party specifications, advisories or external documentation. In v0.2 a
verification against an external source had no truthful category available and
had to be declared as `repository`
([#7](https://github.com/NicolasRocchia/disensor/issues/7)).

**How to migrate**: set the `schema` field to `residue/v0.3` (the key stays; its value changes). If the artifact
already satisfies the invariants in the table, there is nothing else to do: no
fixture of this repository that was valid under v0.2 needed correcting. The
conformance vectors do include artifacts that violate them, on purpose, as
negative cases. The validator
recognises a v0.2 artifact and explains what v0.3 hardened instead of merely
saying the `const` failed.

**Why the identifier was raised instead of hardening v0.2 in place**: not for
compatibility, of which there was none to protect. It was because the whole
product rests on a schema identifier meaning one thing; if v0.2 meant something
different depending on when it was read, the tool would contradict itself in its
own repository.

The original v0.2 contract stays frozen, byte for byte as published, in
`spec/residue.schema.v0.2.json`: the current schema still reads v0.2, but the
document that identifier points at no longer depends on a reconstruction.

## Schema migration: residue/v0.3 to residue/v0.4

Historical declarations do not change. Each version now has its own frozen
resource and is validated under its own rules, so a v0.3 declaration keeps
validating exactly as it did: reading old records was never a permit to keep
emitting under weaker rules, and it is not a reason to rewrite them either.
What changes is what a NEW declaration has to say.

| What v0.4 adds | Why |
|---|---|
| `reviewers[].independence` (required) | R4 used to demand a different model family, full stop, so a round without a second model could not be declared at all, even truthfully. Now independence is declared and the rule checks that it matches the families declared: `cross_family` with two reviewers of the same family is rejected, and so is claiming a degraded mode while actually having another family. |
| `reviewers[].fallback_reason` | Required below `cross_family`. An enumerated code, not prose: free text becomes boilerplate on the second event, and then the chain is an excuse to always take the cheap path. |
| `reviewers[].hardening` | `verified` when the reviewer ran through an adapter whose neutralisation of project instructions was tested against a hostile repository. It is derived, not chosen. |
| Residue classes `reviewer_correlation` and `reviewer_hardening_gap` | One per degraded reviewer, naming it. Correlation is what the reviewer could not see; hardening is what the reviewed material could tell it. Different risks, different items. |

**How to migrate**: nothing, for what is already written. For what you write
from now on, `disensor new` emits v0.4 and prefills these fields from the round;
`disensor validate` will tell you exactly what is missing if you write one by
hand. Level A does not admit independence below `cross_family`: declarable is
not the same as admissible at the level the protocol reserves for what cannot
be undone.

**One rollout detail**: a 0.9 CLI emits v0.4, and a gate still pinned to an
older release does not know that version. `disensor init --upgrade` moves the
pin, or says so before you generate a declaration your own CI would reject.

## Migrating from v0.3 to v0.4 (package versions)

The artifact schema does not change and already-versioned declarations remain
valid: what changes is which PRs the gate approves. Updating without reading
this leaves CI red with messages that do explain the cause, but it is worth
knowing beforehand.

**What starts failing and why:**

| Used to pass | Now fails | What to do |
|---|---|---|
| Checkout without `fetch-depth: 0` (the gate warned and approved anyway) | The gate cannot resolve the PR range and **fails closed** | Add `fetch-depth: 0` to the checkout. A control that cannot decide does not approve. |
| A `diff` gate declaration without `base_commit` | Rejected | Fill it in. A diff review identifies the pair (reviewed base, reviewed head), not a loose head. |
| An artifact with any file name | Rejected | The file is called `<event_id>.json` and the `event_id` has to be a canonical UUID. `disensor new` already generates them that way. |
| A config with unknown keys or of the wrong type | Rejected | The configuration is validated against a closed schema. `level_A_enabled: "false"` in quotes no longer enables Level A by being a non-empty string. |
| A declaration from an earlier PR was enough to approve the current one | Rejected | Each PR declares its own. The gate only evaluates what the PR adds. |
| Declaring `plan` to approve a code change | Rejected | The scope policy says which gate each path accepts, and by default everything requires `diff`. |
| Reviewing a commit and then continuing to add code | Rejected | The declaration has to cover every path in the state it will be merged in. |

**What fixes itself, with nothing to do:** the gate stopped working from the
second PR onwards, because it also evaluated artifacts from earlier PRs and
their reviewed commit fell outside the new range. If you were living with that,
it goes away.

**Before updating**, if the repository already has `.residue/` with history, it
is worth running `disensor gate --no-comment` locally on an open PR to see what
it says.

## Status

v0.11.0, on **residue/v0.4**. What each version changed is in
[CHANGELOG.md](https://github.com/NicolasRocchia/disensor/blob/main/CHANGELOG.md),
newest first.

The schema may change; each version from residue/v0.2 onwards is frozen under
its own identifier, and a declaration keeps being validated under the rules
that judged it when it was emitted. The Spanish-keyed residuo/v0.1 is
recognised and refused with migration instructions, not validated. No version
is committed to as the point where the schema stabilises: when there is a
contract ratified as stable, it will be said here. Open decision: the
definitive licence (MIT today; Apache-2.0 under consideration for its patent
grant).

## Licence

MIT.

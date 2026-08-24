# disensor

[![PyPI](https://img.shields.io/pypi/v/disensor)](https://pypi.org/project/disensor/)
[![CI](https://github.com/NicolasRocchia/disensor/actions/workflows/ci.yml/badge.svg)](https://github.com/NicolasRocchia/disensor/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/disensor)](https://pypi.org/project/disensor/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21633495.svg)](https://doi.org/10.5281/zenodo.21633495)

Adversarial plan & code review with a declared residue.

*Este documento también está [en español](https://github.com/NicolasRocchia/disensor/blob/main/README.es.md).*

Residue declaration of adversarial review, with validation and a CI gate.
Reference implementation of the artifact defined by the **controlled
disagreement** method: one model generates, a model from another family attacks,
the generator verifies every finding, and the cycle ends when each finding has
been resolved, refuted with evidence, or escalated to a human.

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

- `spec/residue.schema.json`: the artifact schema (JSON Schema 2020-12), version residue/v0.3.
- `spec/examples/`: three example artifacts, including a real anonymised event and the minimized profile with no free text.
- `src/disensor/`: Python package with the validator (rules R0 to R10), the CI gate (checks G1 to G9), the PR comment rendering, artifact and repository scaffolding (`init`), and the packaged filling guide (`GUIDE.md`).
- `action.yml`: composite GitHub Action, ready to use.
- `docs/integracion-claude-code.md` (Spanish only): how the real flow (Claude Code plus a reviewer from another family) emits the artifact at the close of each event.
- `docs/antecedentes.md` (Spanish only): where the method sits relative to the literature (residual doubt and defeaters, design rationale and its capture bottleneck, multi-agent adversarial review, governance runtimes, supply chain provenance), with the verification status of each reference.

## Quick start

The package is installed once (globally); each repository is initialised once:

```bash
pip install disensor        # or pipx install disensor, recommended for CLIs

disensor init               # at the repo root: config, CLAUDE.md, filling skill and CI workflow

disensor prompt --gate diff            # the adversarial brief, to hand to a reviewer from another family
disensor new --gate diff --level B     # template prefilled in .residue/
disensor validate .residue/<id>.json   # schema + rules R0 to R10
disensor gate --no-comment             # what CI will run, locally

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
`CLAUDE.md`, the Claude Code skill with the full filling guide
(`.claude/skills/disensor/SKILL.md`, loaded on demand at the close of each
round) and the gate workflow; whatever already exists is respected and reported.
The principle is that after `pip install disensor` and `disensor init` the user
touches nothing by hand: Claude knows when (CLAUDE.md) and how (the skill), any
other agent gets the same with `disensor guide`, and CI enforces the result.
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
      - uses: NicolasRocchia/disensor@v0.6.4
```

The gate validates the declarations **the PR adds**, applies the policy and
posts the result as a comment (updated in place on every push). Everything it
decides comes from git objects in the `merge-base..head` range, never from the
working tree: on a `pull_request` event the checkout leaves the synthetic merge
commit while `head.sha` points at the real head, so reading from disk would
classify one tree and validate another.

## What the gate enforces

Per artifact (rules R0 to R10): coherence between findings and residue, counts
that add up, family decorrelation between generator and reviewer, mandatory
material evidence in verifiable refutations (`text`, `link` or `hash`) against a
verifiable target (`verification.against` other than `none`), mandatory human
attention in interpretive refutations, a fix verified before closing a finding
in a diff gate, rejection of generic markers (in English and in Spanish), and a
minimized profile with the free text R9 covers stripped.

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
- **G9, new declarations state the current version**: a declaration the PR adds has to declare `residue/v0.3`. Superseded versions are still read so that history is not rewritten; that readability is not a permit to keep emitting under the weaker rules. The evidence plane applies the same criterion at ingestion.

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
- **Pin the Action by SHA**, not by tag: a tag is movable and is not a root of trust. `disensor init` writes the tag of the installed version for convenience, and the generated workflow itself warns that it has to be replaced by the SHA that tag points at. This repository's documentation also uses the tag, because it documents which version corresponds; the SHA is put there by whoever deploys.
- **Bootstrap**: the first PR that adds the config and the workflow cannot make itself the root of trust. Initial activation is an administrative step, prior to the gate meaning anything.

Explicit limit: reading the policy from the base turns a one-step bypass into a
two-step one, it does not eliminate it. Whoever can merge a relaxation uses it
on the next PR. And none of this protects against a workflow that was modified,
skipped or replaced. Only the platform resolves that.

## What it does not do

It runs no models, asks for no API keys in CI, and no code travels to any
service: it validates a JSON that is already versioned in the repo. Orchestrating
the loop lives where the team already works; the artifact's `minimized` profile
is meant for environments where the text of the findings cannot leave.

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

## Conformance between implementations

`spec/vectors/` holds the conformance vectors: 31 artifacts with their expected
verdict (valid or not, and the rule labels that must fire). Every validator
implementation has to pass them identically: the Python reference runs them in
its suite (`tests/test_vectors.py`) and the TypeScript port of the evidence
plane runs them with `npm run conformidad`. Labels are compared, not messages.
The vectors are regenerated with `python -m disensor.vectors spec/vectors`.

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

v0.6.4, on **residue/v0.3**. The long-form documentation is bilingual
since v0.6.3: `README.md` is the English one that PyPI renders, `README.es.md`
is the Spanish, and the filling guide ships in both languages. This version
makes the packaged Spanish guide reachable with `disensor guide --lang es`.
Releases are published to PyPI via Trusted
Publishing (OIDC, `release.yml`): no tokens on any machine. v0.4 rewrote the
gate so that it derives the PR scope from git (see "What the gate enforces") and
v0.5 ships the packaged adversarial brief with a reproducible hash; the move to
residue/v0.3 hardens three points of the artifact, closing issues
[#5](https://github.com/NicolasRocchia/disensor/issues/5),
[#7](https://github.com/NicolasRocchia/disensor/issues/7) and
[#8](https://github.com/NicolasRocchia/disensor/issues/8). See "Schema
migration: residue/v0.2 to residue/v0.3". Decision closed in v0.2: schema keys
and CLI in English (Spanish remains as CLI aliases). The schema may change up to
v1.0; changes are declared in the schema itself. Decision open before v1.0: the
definitive licence (MIT today; Apache-2.0 under consideration for its patent
grant).

## Licence

MIT.

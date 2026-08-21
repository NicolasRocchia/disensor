# How to fill a residue declaration (residue/v0.3)

This guide is the single source of truth for filling the artifact that
`disensor new` creates under `.residue/`. It ships inside the package:
`disensor guide` prints it for any coding agent, and `disensor init` installs
it as a Claude Code skill.

The validator (`disensor validate`) and the CI gate enforce much of what is
described here, but not all of it: where a rule exists, this guide names it.
What is not named is the method's obligation and nobody checks it for you.
Filling the artifact correctly the first time is cheaper than iterating against
their errors.

## The round, and then the declaration

1. `disensor prompt --gate <plan|diff|architecture>` prints the adversarial brief. Hand it,
   together with the plan or the diff, to a reviewer from ANOTHER model family.
   A free tier is enough. Same family as the generator does not count, and rule
   R4 rejects the declaration if you try.
2. Verify every finding against the actual code before accepting it. The
   reviewer is decorrelated, not right, and an unverified finding is not a
   finding.
3. `disensor new --gate <plan|diff|architecture> --level <A|B|C>` creates the template,
   prefilled with what git knows (repository, commits, timestamp, uuid).
4. Fill in every `FILL_IN` marker and the findings of the round. The template
   does not validate while markers remain: that is intentional.
5. `disensor validate .residue/<id>.json`. Fix until it prints VALID.
6. Commit the artifact alone: `docs(residue): declare event <short-id>`.
   Never mixed with code changes.

Declare what happened, not what should have happened. An event without
findings and with an express declaration of absence is valid data, not a
failure.

## The three gates

`event.gate` says what was submitted to review, and it changes what the rules
demand afterwards. Each one has its own packaged brief.

- **`plan`**: the plan before implementing. The cheapest moment to be wrong.
  An `incorporated` finding here may close with `fix_verification` of type
  `pending_in_diff_gate`, because the fix has not been written yet.
- **`diff`**: the change before merging. This is the one the CI gate demands for
  code, and the only one where `incorporated` requires the fix to have passed
  its own verification (`diff_gate` or `specific_test`, rule R7). Applying the
  fix is not closing the finding; verifying it is.
- **`architecture`**: a design decision or a comparison of alternatives, when
  the question is not whether the code is right but whether the shape is. Same
  contract as the others; what changes is the brief and the horizon of the
  findings.

A repository declares in its configuration which gate it accepts for which
paths. By default everything demands `diff`.

## Actors

- `generator`: the assistant that produced the plan or diff. `family` is its
  model family (anthropic, openai, google, meta, mistral, other).
- `reviewers[]`: the attacking assistants. Each needs `reviewer_id` (r1,
  r2...), `family`, `model`, and `confinement`. Rule R4 rejects any reviewer
  whose family equals the generator's: decorrelation is the point of the
  method, not an option.
- `reviewers[].prompt_hash`: hash of the adversarial brief given to the
  reviewer. If you used the packaged brief, it is
  `disensor prompt --gate <plan|diff|architecture> --hash`, and anyone can recompute that
  value from the same version to check what you actually asked for. If you
  wrote or edited your own brief, hash the file you really used with
  `disensor hash <brief-file>`. Either way, paste the full `sha256:...`.
- `confinement.mode`: how it was guaranteed that the reviewer only reads
  (permissions, sandbox, read_only_by_instruction, no_confinement). Declare
  the real mode; the gate makes gaps visible instead of hiding them.
- `confinement.verified`: true ONLY if you ran `git status` after the
  reviewer's run and the tree was clean. Otherwise leave false.
- `human_arbiter.present`: must be true; an event without a human arbiter
  does not comply with the protocol (R0).

Delegation inside an actor is invisible to this contract, on purpose. A
generator or a reviewer may fan out into agents, subagents, scripts or any
other internal tooling: the artifact declares principals, not processes, and
the principal answers for the delegated output as if it were its own work.
No rule inspects how an actor produced what it signed, and none should; the
confinement verification over the working tree already covers whatever the
actor's internal processes did there, and `extensions` is the place to
volunteer internal delegation when disclosing it matters. One honest nuance
comes with this: R4 decorrelates the declared principals. An actor that
internally leans on the same family as its counterpart keeps the declaration
formally true while weakening the statistical decorrelation, and the machine
cannot see that. It belongs to the protocol's honest limit: the gate reads
declarations; human sampling reads reality.

## Findings

One entry per point the reviewer raised. Fields: `id` (h1, h2...), `origin`
(the reviewer_id that produced it), `severity` (critical, major, minor,
info), `title`, `description`, `location` (full profile only), and:

- `verification.against`: what the generator checked the finding against
  before accepting or refuting it: `repository` (code, config, contracts),
  `execution` (running tests or the program), `external_source` (literature,
  third-party specifications, advisories, external documentation), or `none`.
  Do not take the reviewer's word: verify, then decide. Pick the class the
  verification actually had. If none of them is true of what you did, that is
  a defect of this vocabulary and it should be reported, not approximated.
- `final_state`, the terminal outcome. Decision table:
  - `incorporated`: the finding changed the plan or the code. In the diff
    gate you MUST add `fix_verification` with type `diff_gate` or
    `specific_test` (R7); `pending_in_diff_gate` is not legal there. R7 fires
    only in the diff gate, so plan and architecture both accept it. If the reviewer's remedy was wrong and you fixed it, record
    `remedy_adjustment`.
  - `debt_recorded`: valid, deferred; requires `debt_id` (schema).
  - `owner_decision`: valid, the owner changed scope, behavior or accepted
    risk; requires `risk_record` (schema).
  - `refuted_verifiable`: false positive with proof. This is the state that
    closes a finding **without touching the code**, so it is the one that
    deserves the most resistance from you. It requires `evidence` carrying
    material content (`text`, `link` or `hash`; neither the empty object nor
    a blank string counts, and `text` needs at least 10 characters) and a `verification.against` other than `none`:
    refuting something
    without having checked anything is a contradiction, not a refutation.
    Note what the evidence does and does not establish. "The test passed" can
    be fully verifiable while "therefore the defect does not exist" is not
    deduced from it; when that is the case, say so in `verification.detail`.
  - `refuted_interpretive`: false positive by judgment; it MUST also appear
    as a residue item (R1) with `requires_human_attention: true` (R8).
  - `escalated_open`: no decision yet; it MUST also appear as a residue
    item (R1).

## Residue

The heart of the declaration: what the cycle could not close by itself.
Either `items` or the express absence, never an empty field.

- `items[]`: `id` (r1, r2...), `class`, `finding_ref` when it comes from a
  finding, `requires_human_attention`.
  - `escalation_without_decision`: from every `escalated_open` finding.
  - `principal_refutation`: from every refuted finding; add
    `refutation_type` (`verifiable` or `interpretive`; interpretive forces
    `requires_human_attention: true`).
  - `execution_gap`: behavior execution could not arbitrate; add
    `gap_reason`. In Level A an execution gap blocks the merge until a
    technical lead accepts it in writing (`lead_acceptance`, R5).
- Absence: `"declared_absence": true` plus `declaration`, minimum 30
  characters of concrete text. Generic markers (none, n/a, all resolved,
  ninguno, todo resuelto...) are rejected by R2. Its list is closed and covers
  English and Spanish: an equivalent marker in another language gets through.

## Metrics

`counts` must add up exactly against the findings list (R6): each
`valid.*` and `false_positives.*` bucket equals the number of findings in
that state, `escalated_open` likewise, `total_findings` equals the list
length. Count, do not estimate.

In the `minimized` profile the findings list may be absent. Then the counts
stand on their own and R6 has nothing to compare them against, which is one more
reason to count instead of estimating.

## Minimized profile

R9 strips the free text it covers: no titles, descriptions or locations in
findings; no descriptions in items; evidence only as `hash`; and it rejects a
`repository` that starts with `http`. Note the literal: that check does not
catch `HTTPS://`, `ssh://`, `git://` or `git@host:repo`, all of which are clear
locators that pass today.

**It narrows the leak channel; it does not close it.** R9 does not reach every
string in the artifact: `residue.declaration`, `event.pr`, `verification.detail`,
`human_arbiter.id` and `lead_acceptance`, among others, still admit free prose.
Treat `minimized` as a reduction of surface, not as a guarantee that nothing
leaves the environment.

`extensions` is not exempt. In the full profile it takes anything; in the
minimized one every value must be opaque (a `sha256:` hash, a number, a
boolean, `null`, or containers of those) and every key must be identifier-shaped:
a name, not a message. The extension space is deliberately not interpreted
by the rules, which is exactly why free text parked there leaves the
environment as readily as anywhere else the profile does not reach.

## Quick map of validator labels

R0 human arbiter absent; R1 residue/finding coherence; R2 generic or
template markers; R3 abbreviated path over protected cases; R4 reviewer
shares the generator's family; R5 Level A execution gap without lead
acceptance; R6 counts that do not add up; R7 incorporated without verified
fix in the diff gate; R8 interpretive refutation without human attention;
R9 text leaks in the minimized profile; R10 full profile without findings;
`schema` shape errors (missing required fields, wrong enums, bad patterns).

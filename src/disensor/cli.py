"""Command line interface: disensor {init, new, validate, gate}.

v0.1 was published with Spanish subcommands and flags; they remain as
aliases (nuevo, validar, and the Spanish long flags) so existing scripts
and muscle memory keep working.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .brief import GATES, main_prompt
from .gate import main_gate
from .guide import main_guide, main_hash
from .init import main_init
from .pack import main_pack
from .pin import main_pin
from .reviewers import main_reviewer
from .round import main_round
from .rules import validate_artifact
from .template import main_new


HELP_AFTER_INVALID = """
What to do next:
  disensor guide                     what every field expects, rule by rule
  disensor prompt --gate <plan|diff|architecture>
                                     the brief for the reviewer, if the round has not happened yet

A freshly created template is invalid on purpose: it is a form to fill with what
actually happened in the round, not a file to commit as it comes."""


def main_validate(args) -> int:
    # Sin esquema fijo: cada declaracion se valida contra la version que
    # declara. Cargar uno solo aca hacia que una declaracion historica valida
    # fuera rechazada por no tener campos que su version no conocia, que es
    # justo lo contrario de lo que el versionado promete.
    failed = False
    invalid_artifact = False
    for path in args.files:
        try:
            with open(path, encoding="utf-8") as f:
                artifact = json.load(f)
        except OSError as exc:
            print(f"{path}: cannot read ({exc.strerror or exc})")
            failed = True
            continue
        except json.JSONDecodeError as exc:
            print(f"{path}: not valid JSON ({exc})")
            failed = True
            continue
        errors = validate_artifact(artifact)
        print(f"{path}: {'VALID' if not errors else 'INVALID'}")
        for msg in errors:
            print(f"  {msg}")
        failed = failed or bool(errors)
        invalid_artifact = invalid_artifact or bool(errors)
    if invalid_artifact:
        # The rule labels say what is wrong and nothing about where to look. For
        # someone on their first artifact that is a dead end, and the first
        # rejection is where people give up. Only shown for an artifact that was
        # read and rejected: after a missing file it would be noise.
        print(HELP_AFTER_INVALID)
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="disensor",
        description="Residue declaration of adversarial review (controlled disagreement).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Scaffold a repository: config, CLAUDE.md section, filling skill and CI workflow.")
    init.add_argument("--level", "--nivel", choices=["A", "B", "C"], default="B")
    init.add_argument("--no-claude", action="store_true", help="Do not touch CLAUDE.md nor the skill.")
    init.add_argument("--no-skill", action="store_true", help="Write the CLAUDE.md section but not the skill.")
    init.add_argument("--claude-global", action="store_true",
                      help="Write the Claude Code section and skill to ~/.claude instead of the repo.")
    init.add_argument("--no-workflow", action="store_true", help="Do not write the CI workflow.")
    init.set_defaults(func=main_init)

    new = sub.add_parser("new", aliases=["nuevo"],
                         help="Create an artifact template for the current event.")
    new.add_argument("--directory", "--directorio", default=".residue")
    new.add_argument("--gate", "--compuerta", choices=["plan", "diff", "architecture"], default="diff")
    new.add_argument("--level", "--nivel", choices=["A", "B", "C"], default="B")
    new.add_argument("--profile", "--perfil", choices=["full", "minimized"], default="full")
    new.set_defaults(func=main_new)

    validate = sub.add_parser("validate", aliases=["validar"],
                              help="Validate artifacts against the schema and rules R0 to R10.")
    validate.add_argument("files", nargs="+")
    validate.set_defaults(func=main_validate)

    gate = sub.add_parser(
        "gate",
        help="CI gate: validates the declarations this PR adds and applies policy G1 to G9.",
        # `help` solo se ve en el listado de `disensor --help`; `description` es lo
        # que muestra `disensor gate --help`, que es donde alguien mira cuando
        # quiere saber que hace este subcomando.
        description=(
            "CI gate: validates the residue declarations this PR adds and applies policy "
            "G1 to G9. Everything it decides comes from git objects in the merge-base..head "
            "range, never from the working tree."
        ),
    )
    gate.add_argument("--directory", "--directorio", default=".residue")
    gate.add_argument("--config", default="disensor.config.json")
    gate.add_argument("--base", default=None, help="Base SHA of the PR (defaults to the GitHub event).")
    gate.add_argument("--head", "--cabeza", default=None, help="Head SHA of the PR (defaults to the GitHub event).")
    gate.add_argument("--no-comment", "--sin-comentario", action="store_true",
                      help="Do not post a comment on the PR.")
    gate.set_defaults(func=main_gate)

    prompt = sub.add_parser(
        "prompt",
        help="Print the adversarial brief to hand to the reviewer from another model family.",
    )
    prompt.add_argument("--gate", "--compuerta", choices=list(GATES), default="diff")
    prompt.add_argument("--hash", action="store_true",
                        help="Print only the sha256: of the brief, the value prompt_hash expects.")
    prompt.add_argument("--output", "--salida", metavar="FILE",
                        help="Write the brief to a file, keeping the bytes the hash is computed over. "
                             "Safer than shell redirection, which on some shells re-encodes the output.")
    prompt.set_defaults(func=main_prompt)

    pin = sub.add_parser(
        "pin",
        help="Pin the gate Action to the commit SHA of its release tag, rewriting the workflows in place.",
        description=(
            "Asks the canonical repository which commit the release tag points at and "
            "rewrites every .github/workflows/ file that uses the Action to that SHA. "
            "A tag can be moved, so it is not a root of trust for the code that decides "
            "whether a merge is allowed; the commit SHA is. Annotated tags are resolved "
            "to the commit they wrap, never to the tag object."
        ),
    )
    pin.add_argument(
        "version", nargs="?", default=None,
        help="Release to pin, with or without the leading v (default: the installed version).",
    )
    pin.set_defaults(func=main_pin)

    pack = sub.add_parser(
        "pack",
        help="Print the full package for the reviewer: confinement, material and the brief.",
        description=(
            "The operational package of a round: the confinement rules, which repository and "
            "which material, where the report goes, and the packaged brief verbatim. A diff "
            "gate takes --base and --head; a plan or architecture gate takes --material, "
            "because that material usually does not live in the git range."
        ),
    )
    pack.add_argument("--gate", "--compuerta", choices=list(GATES), default="diff")
    pack.add_argument("--base", default=None, help="Base of the range (a diff gate needs it).")
    pack.add_argument("--head", "--cabeza", default=None, help="Head of the range (a diff gate needs it).")
    pack.add_argument("--material", default=None,
                      help="File with the plan or decision under review, or - for standard input.")
    pack.add_argument("--branch", default=None, help="Branch name, for the reviewer's context.")
    pack.add_argument("--report", default=None,
                      help="Absolute path, outside the repository, where the reviewer must write.")
    pack.add_argument("--repository", default=None, help="Repository path (defaults to the working directory).")
    pack.add_argument("--output", "--salida", metavar="FILE",
                      help="Write the package to a file, keeping the bytes its hash is computed over.")
    pack.set_defaults(func=main_pack)

    rnd = sub.add_parser(
        "round",
        help="Run the adversarial round: package, reviewer, report and structured result.",
        description=(
            "Orchestrates the mechanical half of a round. It asks the policy whether a round "
            "is required at all, refuses to run on a dirty tree (a diff round reviews commits "
            "that already exist), picks the best reviewer registered on this machine, runs it, "
            "captures the report and emits a result anchored to the commits reviewed. It never "
            "reads the report: judging what the reviewer said is the assistant's work."
        ),
    )
    rnd.add_argument("--gate", "--compuerta", choices=list(GATES), default="diff")
    rnd.add_argument("--generator-family", required=True,
                     choices=["anthropic", "openai", "google", "meta", "mistral", "other"],
                     help="Family of the assistant that produced the material, to keep R4.")
    rnd.add_argument("--generator-model", default=None,
                     help="Model of the generator, to tell same-model from same-family.")
    rnd.add_argument("--base", default=None)
    rnd.add_argument("--head", "--cabeza", default=None)
    rnd.add_argument("--material", default=None,
                     help="Plan or decision under review (plan and architecture gates).")
    rnd.add_argument("--config", default="disensor.config.json")
    rnd.add_argument("--directory", "--directorio", default=".residue")
    rnd.add_argument("--repository", default=None)
    rnd.add_argument("--report", default=None, help="Where to leave the reviewer's report.")
    rnd.add_argument("--result", default=None,
                     help="File for the structured result. Outside the repository, or use a pipe.")
    rnd.add_argument("--timeout", type=int, default=900)
    rnd.add_argument("--check", action="store_true",
                     help="Only answer whether a round is required, without running one.")
    rnd.set_defaults(func=main_round)

    reviewer = sub.add_parser(
        "reviewer",
        help="Register and list the reviewers this machine can run.",
        description=(
            "The reviewers live on the machine, never in the repository: an entry is "
            "executable code, and a pull request that could add one would run commands on "
            "the machine of whoever reviews it. The assistant discovers and proposes; an "
            "entry outside the packaged catalogue needs the owner to approve it."
        ),
    )
    racc = reviewer.add_subparsers(dest="reviewer_action", required=True)

    rsug = racc.add_parser("suggest", help="Which catalogued reviewers this machine has (offline).")
    rsug.set_defaults(func=main_reviewer)

    rlist = racc.add_parser("list", help="Reviewers already registered.")
    rlist.set_defaults(func=main_reviewer)

    radd = racc.add_parser("add", help="Register a reviewer.")
    radd.add_argument("id")
    radd.add_argument("--family", choices=["anthropic", "openai", "google", "meta", "mistral", "other"])
    radd.add_argument("--model")
    radd.add_argument("--stdin", choices=["pack"], default=None,
                      help="Pass the package on standard input instead of as an argument.")
    radd.add_argument("--egress", choices=["local", "cloud", "unknown"], default="unknown")
    radd.add_argument("--yes", action="store_true",
                      help="Approve exactly what the command prints before writing it.")
    # REMAINDER y no nargs=+: el argv de un revisor esta lleno de cosas que
    # parecen flags nuestros (-c, --model), y argparse las reclamaria para si.
    # Todo lo que sigue a --command es del revisor.
    radd.add_argument("--command", nargs=argparse.REMAINDER,
                      help="argv of the reviewer, everything after this flag. "
                           "Placeholders: {pack}, {report}.")
    radd.set_defaults(func=main_reviewer)

    rrm = racc.add_parser("remove", help="Remove a registered reviewer.")
    rrm.add_argument("id")
    rrm.set_defaults(func=main_reviewer)

    guide = sub.add_parser("guide", help="Print the artifact filling guide (for any coding agent or human).")
    guide.add_argument("--lang", "--idioma", choices=["en", "es"], default="en",
                       help="Language of the guide. The English text is the normative one.")
    guide.set_defaults(func=main_guide)

    hash_ = sub.add_parser("hash", help="Compute the sha256:<hex> value for prompt_hash from a file or text.")
    src = hash_.add_mutually_exclusive_group(required=True)
    src.add_argument("file", nargs="?", help="File to hash (e.g. the adversarial brief).")
    src.add_argument("--text", help="Hash this literal text instead of a file.")
    hash_.set_defaults(func=main_hash)
    return p


def main() -> None:
    args = build_parser().parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

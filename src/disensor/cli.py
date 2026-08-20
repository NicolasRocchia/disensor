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
from .rules import load_schema, validate_artifact
from .template import main_new


HELP_AFTER_INVALID = """
What to do next:
  disensor guide                     what every field expects, rule by rule
  disensor prompt --gate <plan|diff|architecture>
                                     the brief for the reviewer, if the round has not happened yet

A freshly created template is invalid on purpose: it is a form to fill with what
actually happened in the round, not a file to commit as it comes."""


def main_validate(args) -> int:
    schema = load_schema()
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
        errors = validate_artifact(artifact, schema)
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

    guide = sub.add_parser("guide", help="Print the artifact filling guide (for any coding agent or human).")
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

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

from .gate import main_gate
from .guide import main_guide, main_hash
from .init import main_init
from .rules import load_schema, validate_artifact
from .template import main_new


def main_validate(args) -> int:
    schema = load_schema()
    failed = False
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            artifact = json.load(f)
        errors = validate_artifact(artifact, schema)
        print(f"{path}: {'VALID' if not errors else 'INVALID'}")
        for msg in errors:
            print(f"  {msg}")
        failed = failed or bool(errors)
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

    gate = sub.add_parser("gate", help="CI gate: validates the whole PR and applies policy G1 to G5.")
    gate.add_argument("--directory", "--directorio", default=".residue")
    gate.add_argument("--config", default="disensor.config.json")
    gate.add_argument("--base", default=None, help="Base SHA of the PR (defaults to the GitHub event).")
    gate.add_argument("--head", "--cabeza", default=None, help="Head SHA of the PR (defaults to the GitHub event).")
    gate.add_argument("--no-comment", "--sin-comentario", action="store_true",
                      help="Do not post a comment on the PR.")
    gate.set_defaults(func=main_gate)

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

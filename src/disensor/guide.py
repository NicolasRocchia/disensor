"""Packaged filling guide and hash helper: `disensor guide` and `disensor hash`.

The guide (GUIDE.md, shipped inside the package) is the single source of
truth on how to fill a residue declaration. `disensor init` installs it as a
Claude Code skill; `disensor guide` prints it for any other coding agent or
for a human. `disensor hash` computes the `sha256:...` value the schema
expects in `prompt_hash`, so nobody hashes the adversarial brief by hand.
"""
from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path


def guide_text() -> str:
    """The packaged guide, verbatim."""
    return resources.files("disensor").joinpath("GUIDE.md").read_text(encoding="utf-8")


def main_guide(args) -> int:
    print(guide_text(), end="")
    return 0


def main_hash(args) -> int:
    if args.text is not None:
        data = args.text.encode("utf-8")
    else:
        data = Path(args.file).read_bytes()
    print("sha256:" + hashlib.sha256(data).hexdigest())
    return 0

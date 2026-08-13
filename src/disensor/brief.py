"""Packaged adversarial briefs: `disensor prompt`.

The schema asks for `prompt_hash`, the hash of the adversarial brief that was
used, and until now the tool asked for that hash without ever handing out a
brief: whoever installed it had to invent one and hash it. That left the hardest
part of the method, getting a second model to attack in earnest, entirely on the
user, and made the run impossible for anyone else to reproduce.

Shipping the brief closes both holes. The text travels inside the package, so
`disensor prompt --gate diff --hash` gives a value anybody can recompute from
the same version. Editing the brief is expected and fine: the hash changes and
the declaration then records that a different brief was used, which is exactly
what the field is for.
"""
from __future__ import annotations

import hashlib
import sys
from importlib import resources

GATES = ("plan", "diff", "architecture")


def brief_text(gate: str) -> str:
    """The packaged brief for a gate, verbatim."""
    if gate not in GATES:
        raise ValueError(f"unknown gate '{gate}' (expected one of {', '.join(GATES)})")
    return resources.files("disensor").joinpath("prompts", f"{gate}.md").read_text(encoding="utf-8")


def brief_hash(gate: str) -> str:
    """The `sha256:<hex>` of the packaged brief, ready for `prompt_hash`."""
    return "sha256:" + hashlib.sha256(brief_text(gate).encode("utf-8")).hexdigest()


def main_prompt(args) -> int:
    if args.hash:
        print(brief_hash(args.gate))
        return 0
    # Written as bytes so that `disensor prompt > brief.md` produces a file whose
    # hash is the canonical one. Printing as text lets the platform rewrite the
    # line endings, and on Windows the redirected file hashes differently from
    # the packaged brief: whoever saved it would declare a prompt_hash nobody
    # else could recompute, which defeats the point of the field.
    data = brief_text(args.gate).encode("utf-8")
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:  # stdout replaced, as pytest does when capturing
        sys.stdout.write(data.decode("utf-8"))
    else:
        buffer.write(data)
        buffer.flush()
    return 0

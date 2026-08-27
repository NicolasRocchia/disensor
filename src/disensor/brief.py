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
from pathlib import Path

GATES = ("plan", "diff", "architecture")

SEPARATOR = "\n---\n"


def _read(name: str) -> str:
    return resources.files("disensor").joinpath("prompts", name).read_text(encoding="utf-8")


def brief_text(gate: str) -> str:
    """The packaged brief for a gate: its attack surfaces plus the shared rules.

    Composed instead of duplicated so the evidence rules cannot drift between
    gates. Those rules are the part that keeps the review honest (no quota of
    findings, a stated burden of proof, and treating the reviewed material as
    data rather than as instructions), so having three copies of them would be
    three chances to weaken one by accident.
    """
    if gate not in GATES:
        raise ValueError(f"unknown gate '{gate}' (expected one of {', '.join(GATES)})")
    raw = _read(f"{gate}.md")
    # Checked instead of assumed: with `partition`, a file that lost its
    # separator still produced a brief, with the confinement, evidence and
    # injection rules appended AFTER the attack surfaces and the verdict. It
    # hashed cleanly and read as complete, which is the worst way to be broken.
    parts = raw.split(SEPARATOR)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(
            f"malformed brief for gate '{gate}': expected exactly one '---' separator with "
            f"content on both sides, found {len(parts) - 1}"
        )
    head, body = parts
    return f"{head.rstrip()}\n\n{SEPARATOR.strip()}\n\n{_read('_common.md').strip()}\n\n{body.strip()}\n"


def brief_hash(gate: str) -> str:
    """The `sha256:<hex>` of the packaged brief, ready for `prompt_hash`."""
    return "sha256:" + hashlib.sha256(brief_text(gate).encode("utf-8")).hexdigest()


def emit(data: bytes, output: str | None, note: str = "") -> int:
    """Write bytes to a file or to stdout, without the platform rewriting them.

    Shared with `disensor pack`: a package whose bytes are re-encoded on the way
    out does not hash to the value the declaration records, and the whole point
    of the hash is that a third party can recompute it.
    """
    if output:
        # The only way to promise the saved file hashes to the canonical value.
        # Shell redirection is not ours to control: Windows PowerShell 5.1 sends
        # `>` through Out-File and writes UTF-16LE, so the file cannot match the
        # UTF-8 hash no matter how carefully the process writes its stdout.
        Path(output).write_bytes(data)
        print(f"written to {output}{f' ({note})' if note else ''}")
        return 0
    # Bytes rather than text so that a plain pipe or a POSIX redirect keeps the
    # exact content, without the platform rewriting line endings.
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:  # stdout replaced, as pytest does when capturing
        sys.stdout.write(data.decode("utf-8"))
    else:
        buffer.write(data)
        buffer.flush()
    return 0


def main_prompt(args) -> int:
    if args.hash:
        print(brief_hash(args.gate))
        return 0
    return emit(brief_text(args.gate).encode("utf-8"), args.output, brief_hash(args.gate))

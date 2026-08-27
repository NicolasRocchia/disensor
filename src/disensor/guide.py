"""Packaged filling guide and hash helper: `disensor guide` and `disensor hash`.

Two texts come out of here, because an agent needs both and only one of them
is a Claude Code skill. The RUNBOOK says how an event is run: when a round is
required, the commit-first contract, what each exit code means, when to stop
and ask. The filling guide says how the artifact that comes out of it is
completed. `disensor init` installs the runbook as a Claude Code skill, and
`disensor guide` prints both so that an agent which is not Claude Code gets the
same material from one command, which is what the README has been promising.

The guide ships inside the package in two renditions: GUIDE.md (English, the
normative one) and GUIDE.es.md (Spanish). The runbook is English only, and
`--lang es` says so instead of pretending otherwise. A sync test keeps their structure and rule labels aligned,
and says out loud what it cannot check: whether two texts in different languages
mean the same thing. `disensor hash` computes the `sha256:...` value the schema
expects in `prompt_hash`, so nobody hashes the adversarial brief by hand.
"""
from __future__ import annotations

import hashlib
import sys
from importlib import resources
from pathlib import Path


GUIDES = {"en": "GUIDE.md", "es": "GUIDE.es.md"}


def guide_text(lang: str = "en") -> str:
    """The packaged guide, verbatim, in the requested language."""
    if lang not in GUIDES:
        raise ValueError(f"unknown guide language '{lang}' (expected one of {', '.join(GUIDES)})")
    return resources.files("disensor").joinpath(GUIDES[lang]).read_text(encoding="utf-8")


RUNBOOK_IS_ENGLISH_ONLY = (
    "> Nota: el runbook del evento existe solo en ingles. La guia de llenado que\n"
    "> sigue abajo si esta en castellano.\n"
)


def runbook_text() -> str:
    """The event runbook: the same text `init` installs as a Claude Code skill.

    Imported here and not at module level because `init` already imports this
    module, and the pair would be a cycle. One text, one source: if the runbook
    is edited, both the installed skill and this command move together.
    """
    from .init import RUNBOOK

    return RUNBOOK


def guide_output(lang: str = "en", *, part: str = "both") -> str:
    """What the command prints, assembled.

    Default is both parts, in the order they are needed: how the event is run,
    then how the artifact that comes out of it is filled in.
    """
    if part == "runbook":
        return runbook_text()
    if part == "filling":
        return guide_text(lang)
    aviso = RUNBOOK_IS_ENGLISH_ONLY if lang == "es" else ""
    return f"{aviso}{runbook_text().rstrip()}\n\n---\n\n{guide_text(lang)}"


def main_guide(args) -> int:
    # Bytes UTF-8 por el buffer, no print(): la guia castellana tiene acentos y
    # el encoding de la consola no es nuestro. En Windows, stdout puede ser
    # CP1252 (la salida llega corrompida a quien la capture como UTF-8) o algo
    # peor via PYTHONIOENCODING, donde print() directamente revienta con
    # UnicodeEncodeError y el subcomando termina 1 sin guia. Mismo patron que
    # main_prompt en brief.py, y por el mismo motivo.
    parte = "runbook" if getattr(args, "runbook", False) else (
        "filling" if getattr(args, "filling", False) else "both"
    )
    data = guide_output(getattr(args, "lang", "en"), part=parte).encode("utf-8")
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:  # stdout sustituido, como hace pytest al capturar
        sys.stdout.write(data.decode("utf-8"))
    else:
        buffer.write(data)
        buffer.flush()
    return 0


def main_hash(args) -> int:
    if args.text is not None:
        data = args.text.encode("utf-8")
    else:
        try:
            data = Path(args.file).read_bytes()
        except OSError as exc:
            print(f"cannot read {args.file}: {exc.strerror or exc}")
            print(
                "If you used the packaged brief, its hash is "
                "`disensor prompt --gate <plan|diff|architecture> --hash`."
            )
            return 1
    print("sha256:" + hashlib.sha256(data).hexdigest())
    return 0

"""Packaged filling guide and hash helper: `disensor guide` and `disensor hash`.

The guide ships inside the package in two renditions: GUIDE.md (English, the
normative one) and GUIDE.es.md (Spanish). `disensor init` installs the English
one as a Claude Code skill; `disensor guide` prints either for any other coding
agent or for a human. A sync test keeps their structure and rule labels aligned,
and says out loud what it cannot check: whether two texts in different languages
mean the same thing. `disensor hash` computes the `sha256:...` value the schema
expects in `prompt_hash`, so nobody hashes the adversarial brief by hand.
"""
from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path


GUIDES = {"en": "GUIDE.md", "es": "GUIDE.es.md"}


def guide_text(lang: str = "en") -> str:
    """The packaged guide, verbatim, in the requested language."""
    if lang not in GUIDES:
        raise ValueError(f"unknown guide language '{lang}' (expected one of {', '.join(GUIDES)})")
    return resources.files("disensor").joinpath(GUIDES[lang]).read_text(encoding="utf-8")


def main_guide(args) -> int:
    print(guide_text(getattr(args, "lang", "en")), end="")
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

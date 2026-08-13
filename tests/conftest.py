"""Make the suite test this working tree, not whatever is installed.

Without this, `pytest` from a checkout imports `disensor` from site-packages, so
a green suite says nothing about the code being edited. CI installs the package
in editable mode and lands on the same files, so this only removes a difference
between running the tests locally and running them in CI.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The gate falls back to the GitHub event when it gets no explicit range, and it
# writes to the step summary when the runner offers one. Inside Actions those
# variables exist and point at the real pull request of this repository, so a
# test that means "no range available" would silently read that event and fail
# for a different reason than the one it is asserting. This keeps the suite
# testing the gate instead of the environment it happens to run in.
GITHUB_ENV = (
    "GITHUB_EVENT_PATH",
    "GITHUB_STEP_SUMMARY",
    "GITHUB_TOKEN",
    "GITHUB_REPOSITORY",
    "GITHUB_API_URL",
)


@pytest.fixture(autouse=True)
def isolate_from_the_runner(monkeypatch):
    for name in GITHUB_ENV:
        monkeypatch.delenv(name, raising=False)

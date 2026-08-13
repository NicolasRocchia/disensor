"""Make the suite test this working tree, not whatever is installed.

Without this, `pytest` from a checkout imports `disensor` from site-packages, so
a green suite says nothing about the code being edited. CI installs the package
in editable mode and lands on the same files, so this only removes a difference
between running the tests locally and running them in CI.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

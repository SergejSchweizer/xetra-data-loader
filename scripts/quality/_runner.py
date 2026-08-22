"""Shared helpers for repository quality commands."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence


def run_module(module: str, args: Sequence[str]) -> int:
    """Run a Python module using the active interpreter and return its exit code."""
    completed = subprocess.run([sys.executable, "-m", module, *args], check=False)
    return completed.returncode


def run_pytest(args: Sequence[str]) -> int:
    """Run pytest, treating an empty test root as a successful bootstrap state."""
    code = run_module("pytest", args)
    return 0 if code == 5 else code

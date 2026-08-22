"""Canonical repository lint command."""

from __future__ import annotations

import sys

from _runner import run_module


if __name__ == "__main__":
    raise SystemExit(run_module("ruff", ["check", "."]))

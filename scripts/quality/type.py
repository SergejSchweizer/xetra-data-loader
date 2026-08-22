"""Canonical repository type-check command."""

from __future__ import annotations

from _runner import run_module


if __name__ == "__main__":
    raise SystemExit(run_module("mypy", []))

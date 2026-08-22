"""Canonical repository integration-test command."""

from __future__ import annotations

from _runner import run_pytest


if __name__ == "__main__":
    raise SystemExit(run_pytest(["tests/integration", "-m", "integration"]))

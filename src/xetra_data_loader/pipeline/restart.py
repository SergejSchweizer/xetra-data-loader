"""Single-run locking and restart checkpoints for the weekly loader."""

from __future__ import annotations

import fcntl
import json
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import TextIO

from xetra_data_loader.pipeline.orchestrator import (
    PipelineStages,
    PipelineSummary,
    run_weekly_pipeline,
)
from xetra_data_loader.sync.core import JSONValue

type RestartStage = Callable[[], Mapping[str, JSONValue] | None]
type WrappedStage = Callable[[], dict[str, JSONValue]]

_STAGE_NAMES = (
    "listings",
    "quotes",
    "dividends",
    "splits",
    "gold_validation",
    "postgres_listings_sync",
    "postgres_quotes_sync",
    "postgres_dividends_sync",
    "postgres_splits_sync",
    "verification",
)


class ConcurrentLoaderRunError(RuntimeError):
    """Raised when another loader process already owns the run lock."""


@dataclass(slots=True)
class LoaderLock(AbstractContextManager["LoaderLock"]):
    """Advisory process lock automatically released on exit or process death."""

    path: Path
    _handle: TextIO | None = None

    def __enter__(self) -> LoaderLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise ConcurrentLoaderRunError(f"loader lock is already held: {self.path}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write("locked\n")
        handle.flush()
        self._handle = handle
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        handle = self._handle
        if handle is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
            self._handle = None
        return None


def run_restartable_pipeline(
    stages: PipelineStages,
    *,
    lock_path: Path,
    checkpoint_path: Path,
) -> PipelineSummary:
    """Run once, resume after the last completed stage, and clear checkpoints on success."""

    with LoaderLock(lock_path):
        completed = _read_checkpoint(checkpoint_path)
        wrapped = _wrap_stages(stages, completed, checkpoint_path)
        summary = run_weekly_pipeline(wrapped)
        checkpoint_path.unlink(missing_ok=True)
        return summary


def _wrap_stages(
    stages: PipelineStages,
    completed: set[str],
    checkpoint_path: Path,
) -> PipelineStages:
    def wrap(name: str, stage: RestartStage) -> WrappedStage:
        def run() -> dict[str, JSONValue]:
            if name in completed:
                return {"restart": "checkpoint-skip"}
            details = stage()
            completed.add(name)
            _write_checkpoint(checkpoint_path, completed)
            return {} if details is None else dict(details)

        return run

    return PipelineStages(
        listings=wrap("listings", stages.listings),
        quotes=wrap("quotes", stages.quotes),
        dividends=wrap("dividends", stages.dividends),
        splits=wrap("splits", stages.splits),
        gold_validation=wrap("gold_validation", stages.gold_validation),
        postgres_listings_sync=wrap("postgres_listings_sync", stages.postgres_listings_sync),
        postgres_quotes_sync=wrap("postgres_quotes_sync", stages.postgres_quotes_sync),
        postgres_dividends_sync=wrap("postgres_dividends_sync", stages.postgres_dividends_sync),
        postgres_splits_sync=wrap("postgres_splits_sync", stages.postgres_splits_sync),
        verification=wrap("verification", stages.verification),
    )


def _read_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("invalid loader checkpoint")
    raw_completed = payload.get("completed")
    if not isinstance(raw_completed, list) or not all(
        isinstance(item, str) for item in raw_completed
    ):
        raise ValueError("invalid loader checkpoint completed stages")
    completed = set(raw_completed)
    if not completed.issubset(_STAGE_NAMES):
        raise ValueError("loader checkpoint contains unknown stage")
    expected_prefix = set(_STAGE_NAMES[: len(completed)])
    if completed != expected_prefix:
        raise ValueError("loader checkpoint stages must form an ordered prefix")
    return completed


def _write_checkpoint(path: Path, completed: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = [name for name in _STAGE_NAMES if name in completed]
    payload = {"version": 1, "completed": ordered}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)

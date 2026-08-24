"""Non-interactive guarded production entry point for the weekly pipeline."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

from xetra_loader.config import resolve_medallion_root
from xetra_loader.pipeline.orchestrator import PipelineStageError, PipelineStages
from xetra_loader.pipeline.restart import ConcurrentLoaderRunError, run_restartable_pipeline
from xetra_loader.pipeline.runtime import build_weekly_stages

type StagesFactory = Callable[[], PipelineStages]


def main(
    argv: Sequence[str] | None = None,
    *,
    stages_factory: StagesFactory = build_weekly_stages,
    medallion_root: Path | None = None,
) -> int:
    """Run exactly one locked weekly pipeline using paths beneath the Medallion root."""

    if argv:
        raise ValueError("xdl-weekly does not accept command-line arguments")
    root = (medallion_root or Path(resolve_medallion_root())).resolve()
    try:
        summary = run_restartable_pipeline(
            stages_factory(),
            lock_path=root / "weekly.lock",
            checkpoint_path=root / "weekly.checkpoint.json",
        )
    except ConcurrentLoaderRunError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, sort_keys=True))
        return 2
    except PipelineStageError as exc:
        print(json.dumps(exc.summary.as_dict(), sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(summary.as_dict(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from collections.abc import Callable

import pytest

from xetra_loader.pipeline.orchestrator import (
    PipelineStageError,
    PipelineStages,
    run_weekly_pipeline,
)
from xetra_loader.sync.core import JSONValue

EXPECTED_ORDER = [
    "listings",
    "dividends",
    "splits",
    "quotes",
    "gold_validation",
    "postgres_listings_sync",
    "postgres_quotes_sync",
    "postgres_dividends_sync",
    "postgres_splits_sync",
    "verification",
]


def _stages(calls: list[str], *, fail_at: str | None = None) -> PipelineStages:
    def stage(name: str) -> Callable[[], dict[str, JSONValue]]:
        def run() -> dict[str, JSONValue]:
            calls.append(name)
            if name == fail_at:
                raise RuntimeError(f"boom-{name}")
            return {"stage": name}

        return run

    return PipelineStages(
        listings=stage("listings"),
        quotes=stage("quotes"),
        dividends=stage("dividends"),
        splits=stage("splits"),
        gold_validation=stage("gold_validation"),
        postgres_listings_sync=stage("postgres_listings_sync"),
        postgres_quotes_sync=stage("postgres_quotes_sync"),
        postgres_dividends_sync=stage("postgres_dividends_sync"),
        postgres_splits_sync=stage("postgres_splits_sync"),
        verification=stage("verification"),
    )


def test_weekly_pipeline_executes_exact_order_and_reports_every_stage() -> None:
    calls: list[str] = []
    summary = run_weekly_pipeline(_stages(calls))

    assert calls == EXPECTED_ORDER
    assert summary.succeeded
    assert [report.name for report in summary.reports] == EXPECTED_ORDER
    assert [report.status for report in summary.reports] == ["success"] * len(EXPECTED_ORDER)
    assert summary.as_dict()["status"] == "success"


def test_weekly_pipeline_failure_blocks_every_downstream_stage() -> None:
    calls: list[str] = []

    with pytest.raises(PipelineStageError) as exc_info:
        run_weekly_pipeline(_stages(calls, fail_at="gold_validation"))

    assert calls == EXPECTED_ORDER[:5]
    assert exc_info.value.stage == "gold_validation"
    assert [report.name for report in exc_info.value.summary.reports] == EXPECTED_ORDER[:5]
    assert exc_info.value.summary.reports[-1].status == "failed"
    assert exc_info.value.summary.as_dict()["status"] == "failed"

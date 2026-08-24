"""Incremental weekly refresh keeps history outside the authoritative overlap."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from xetra_loader.contracts.listings import ListingRecord
from xetra_loader.contracts.quotes import QuoteRecord
from xetra_loader.gold.listings import build_listing_gold
from xetra_loader.medallion.core import Layer, MedallionLayout, canonical_json
from xetra_loader.ops.bootstrap import FetchBatch, FetchMetrics
from xetra_loader.pipeline.runtime import _WeeklyState


def _quote(day: int, close: str) -> QuoteRecord:
    return QuoteRecord(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        trade_date=date(2026, 8, day),
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        adjusted_close=Decimal(close),
        volume=100,
    )


class _Runtime:
    def __init__(self, root: Path) -> None:
        self._layout = MedallionLayout(root)
        self.calls: list[tuple[date | None, tuple[QuoteRecord, ...]]] = []
        self.persisted_silver: list[dict[str, object]] = []

    def fetch_quotes(
        self,
        listing: ListingRecord,
        *,
        last_business_date: date | None = None,
        previous_records: tuple[QuoteRecord, ...] = (),
    ) -> FetchBatch[QuoteRecord]:
        del listing
        self.calls.append((last_business_date, previous_records))
        return FetchBatch(
            (_quote(20, "12"), _quote(22, "13")),
            FetchMetrics(logical_requests=1, attempts=1, rows=2),
        )

    def persist_gold(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def persist_silver(self, dataset: str, rows: list[dict[str, object]]) -> None:
        assert dataset == "eod_quotes"
        self.persisted_silver = rows


def test_incremental_quote_refresh_replaces_only_requested_overlap(tmp_path: Path) -> None:
    runtime = _Runtime(tmp_path)
    old_history = (_quote(14, "10"), _quote(18, "11"), _quote(20, "10"), _quote(22, "12"))
    silver_path = runtime._layout.dataset_path(Layer.SILVER, "eod_quotes") / "data.json"
    silver_path.parent.mkdir(parents=True)
    silver_path.write_text(
        canonical_json([record.semantic_dict() for record in old_history]), encoding="utf-8"
    )
    state = _WeeklyState(runtime)  # type: ignore[arg-type]
    state.listings = build_listing_gold([ListingRecord("DE0000000001", "XETRA", "AAA")])

    details = state.ingest_quotes()

    assert runtime.calls[0][0] == date(2026, 8, 22)
    assert [record.trade_date for record in runtime.calls[0][1]] == [
        date(2026, 8, 14),
        date(2026, 8, 18),
        date(2026, 8, 20),
        date(2026, 8, 22),
    ]
    assert [row["trade_date"] for row in runtime.persisted_silver] == [
        "2026-08-14",
        "2026-08-20",
        "2026-08-22",
    ]
    assert runtime.persisted_silver[1]["close"] == "12"
    assert details["requests"] == 1

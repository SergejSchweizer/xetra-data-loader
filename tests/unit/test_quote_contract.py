from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from xetra_loader.contracts.quotes import (
    QuoteRecord,
    QuoteRunMetadata,
    overlap_start,
    serialize_quotes,
    validate_unique_quotes,
)


def _quote(trade_date: date = date(2026, 8, 22), close: str = "10.0") -> QuoteRecord:
    return QuoteRecord(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        trade_date=trade_date,
        open=Decimal("9.5"),
        high=Decimal("10.5"),
        low=Decimal("9.0"),
        close=Decimal(close),
        adjusted_close=Decimal(close),
        volume=100,
    )


def test_timestamp_eod_is_utc_midnight_not_close_time() -> None:
    quote = _quote()
    assert quote.timestamp_eod == datetime(2026, 8, 22, 0, 0, tzinfo=UTC)


def test_overlap_boundary_is_seven_calendar_days() -> None:
    assert overlap_start(date(2026, 8, 22)) == date(2026, 8, 15)


def test_duplicate_quote_key_fails() -> None:
    quote = _quote()
    with pytest.raises(ValueError, match="duplicate quote key"):
        validate_unique_quotes([quote, quote])


def test_run_metadata_cannot_change_quote_semantics() -> None:
    quote = _quote()
    semantic = serialize_quotes([quote])
    QuoteRunMetadata("run-a", datetime(2026, 8, 22, 10, 0, tzinfo=UTC))
    QuoteRunMetadata("run-b", datetime(2026, 8, 22, 11, 0, tzinfo=UTC))
    assert serialize_quotes([quote]) == semantic


def test_run_metadata_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        QuoteRunMetadata("run-a", datetime(2026, 8, 22, 10, 0))

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from xetra_loader.market import DividendRow, ListingRow, QuoteRow

UTC_NOW = datetime(2026, 8, 22, 20, 0, tzinfo=UTC)


def test_listing_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ListingRow(
            isin="DE0000000001",
            exchange="XETRA",
            code="AAA",
            fetched_at_utc=datetime(2026, 8, 22, 20, 0),
            published_at_utc=UTC_NOW,
        )


def test_quote_requires_utc_midnight_anchor() -> None:
    with pytest.raises(ValueError, match="00:00:00 UTC"):
        QuoteRow(
            isin="DE0000000001",
            exchange="XETRA",
            code="AAA",
            trade_date=date(2026, 8, 22),
            timestamp_eod=datetime(2026, 8, 22, 17, 30, tzinfo=UTC),
            close=Decimal("10.25"),
            fetched_at_utc=UTC_NOW,
            published_at_utc=UTC_NOW,
        )


def test_event_key_must_be_sha256_hex() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        DividendRow(
            isin="DE0000000001",
            exchange="XETRA",
            code="AAA",
            event_key="not-a-hash",
            event_date=date(2026, 8, 1),
            value=Decimal("1.25"),
            fetched_at_utc=UTC_NOW,
            published_at_utc=UTC_NOW,
        )

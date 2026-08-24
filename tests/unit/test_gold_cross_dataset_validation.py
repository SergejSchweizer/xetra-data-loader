from datetime import date
from decimal import Decimal

import pytest

from xetra_loader.contracts.corporate_actions import DividendEvent, SplitEvent
from xetra_loader.contracts.listings import ListingRecord
from xetra_loader.contracts.quotes import QuoteRecord
from xetra_loader.gold.dividends import build_dividend_gold
from xetra_loader.gold.listings import build_listing_gold
from xetra_loader.gold.quotes import build_quote_gold
from xetra_loader.gold.splits import build_split_gold
from xetra_loader.gold.validation import validate_complete_gold


def _listing(code: str = "AAA") -> ListingRecord:
    return ListingRecord("DE0000000001", "XETRA", code)


def _quote(code: str = "AAA") -> QuoteRecord:
    return QuoteRecord(
        isin="DE0000000001",
        exchange="XETRA",
        code=code,
        trade_date=date(2026, 8, 21),
        open=Decimal("10"),
        high=Decimal("12"),
        low=Decimal("9"),
        close=Decimal("11"),
        adjusted_close=Decimal("11"),
        volume=100,
    )


def _dividend(code: str = "AAA") -> DividendEvent:
    return DividendEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code=code,
        event_date=date(2026, 8, 20),
        value=Decimal("1.25"),
    )


def _split(code: str = "AAA") -> SplitEvent:
    return SplitEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code=code,
        event_date=date(2026, 8, 19),
        split_ratio="2:1",
        split_factor=Decimal("2"),
    )


def _validated(*, child_code: str = "AAA") -> object:
    return validate_complete_gold(
        build_listing_gold([_listing()]),
        build_quote_gold([_quote(child_code)]),
        build_dividend_gold([_dividend(child_code)]),
        build_split_gold([_split(child_code)]),
    )


def test_complete_gold_reports_all_counts_and_fingerprints() -> None:
    summary = _validated()

    assert summary.row_counts == {
        "listings": 1,
        "eod_quotes": 1,
        "dividends": 1,
        "splits": 1,
    }
    assert set(summary.semantic_fingerprints) == set(summary.row_counts)


@pytest.mark.parametrize("dataset", ("eod_quotes", "dividends", "splits"))
def test_orphan_child_identity_fails_closed(dataset: str) -> None:
    listing = build_listing_gold([_listing()])
    quotes = build_quote_gold([_quote("ORPHAN") if dataset == "eod_quotes" else _quote()])
    dividends = build_dividend_gold(
        [_dividend("ORPHAN") if dataset == "dividends" else _dividend()]
    )
    splits = build_split_gold([_split("ORPHAN") if dataset == "splits" else _split()])

    with pytest.raises(ValueError, match=f"Gold {dataset} contains orphan"):
        validate_complete_gold(listing, quotes, dividends, splits)

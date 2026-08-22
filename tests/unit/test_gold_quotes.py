from datetime import date
from decimal import Decimal

import pytest

from xetra_data_loader.contracts.quotes import QuoteRecord
from xetra_data_loader.gold.quotes import build_quote_gold


def _quote(day: int, close: str = "10") -> QuoteRecord:
    return QuoteRecord(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        trade_date=date(2026, 8, day),
        open=Decimal("9"),
        high=Decimal("11"),
        low=Decimal("8"),
        close=Decimal(close),
        adjusted_close=Decimal(close),
        volume=100,
    )


def test_gold_quote_result_is_deterministic() -> None:
    rows = [_quote(22), _quote(21)]
    result = build_quote_gold(rows)
    assert [row.trade_date for row in result.rows] == [date(2026, 8, 21), date(2026, 8, 22)]
    assert result.row_count == 2
    assert len(result.semantic_fingerprint) == 64
    assert result.semantic_fingerprint == build_quote_gold(reversed(rows)).semantic_fingerprint


def test_duplicate_key_fails() -> None:
    quote = _quote(22)
    with pytest.raises(ValueError, match="duplicate quote key"):
        build_quote_gold([quote, quote])


def test_semantic_change_changes_fingerprint() -> None:
    assert build_quote_gold([_quote(22, "10")]).semantic_fingerprint != build_quote_gold(
        [_quote(22, "10.5")]
    ).semantic_fingerprint

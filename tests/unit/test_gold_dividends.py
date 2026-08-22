from datetime import date
from decimal import Decimal

import pytest

from xetra_data_loader.contracts.corporate_actions import DividendEvent, retract_dividend
from xetra_data_loader.gold.dividends import build_dividend_gold


def _event(value: str = "1.25") -> DividendEvent:
    return DividendEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        event_date=date(2026, 8, 20),
        value=Decimal(value),
        currency="EUR",
    )


def test_active_event_is_serving_row() -> None:
    result = build_dividend_gold([_event()])
    assert result.row_count == 1
    assert result.retracted_keys == ()
    assert result.semantic_rows()[0]["event_key"] == _event().event_key


def test_retracted_event_is_removed_from_serving_rows() -> None:
    event = _event()
    result = build_dividend_gold([retract_dividend(event)])
    assert result.rows == ()
    assert result.row_count == 0
    assert result.retracted_keys == (event.key,)


def test_correction_contains_new_active_and_old_retraction() -> None:
    old = _event("1.25")
    new = _event("1.30")
    result = build_dividend_gold([new, retract_dividend(old)])
    assert result.rows == (new,)
    assert result.retracted_keys == (old.key,)
    assert len(result.semantic_fingerprint) == 64


def test_duplicate_event_key_fails() -> None:
    event = _event()
    with pytest.raises(ValueError, match="duplicate Gold dividend key"):
        build_dividend_gold([event, event])


def test_replay_fingerprint_is_stable_under_input_order() -> None:
    old = _event("1.25")
    new = _event("1.30")
    records = [new, retract_dividend(old)]
    assert build_dividend_gold(records).semantic_fingerprint == build_dividend_gold(
        reversed(records)
    ).semantic_fingerprint

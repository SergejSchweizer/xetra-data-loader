from datetime import date
from decimal import Decimal

import pytest

from xetra_loader.contracts.corporate_actions import SplitEvent, retract_split
from xetra_loader.gold.splits import build_split_gold


def _event(ratio: str = "2:1") -> SplitEvent:
    return SplitEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        event_date=date(2026, 8, 20),
        split_ratio=ratio,
        split_factor=Decimal(ratio.split(":", 1)[0]) / Decimal(ratio.split(":", 1)[1]),
    )


def test_active_split_is_serving_row() -> None:
    event = _event()
    result = build_split_gold([event])
    assert result.rows == (event,)
    assert result.retracted_keys == ()
    assert result.row_count == 1


def test_retracted_split_is_removed_from_serving_rows() -> None:
    event = _event()
    result = build_split_gold([retract_split(event)])
    assert result.rows == ()
    assert result.retracted_keys == (event.key,)


def test_correction_contains_new_active_and_old_retraction() -> None:
    old = _event("2:1")
    new = _event("3:1")
    result = build_split_gold([new, retract_split(old)])
    assert result.rows == (new,)
    assert result.retracted_keys == (old.key,)
    assert len(result.semantic_fingerprint) == 64


def test_duplicate_event_key_fails() -> None:
    event = _event()
    with pytest.raises(ValueError, match="duplicate Gold split key"):
        build_split_gold([event, event])


def test_replay_fingerprint_is_stable_under_input_order() -> None:
    old = _event("2:1")
    new = _event("3:1")
    records = [new, retract_split(old)]
    assert build_split_gold(records).semantic_fingerprint == build_split_gold(
        reversed(records)
    ).semantic_fingerprint

import pytest

from xetra_loader.contracts.listings import ListingRecord
from xetra_loader.gold.listings import build_listing_gold


def test_gold_listing_rows_are_deterministic_and_load_compatible() -> None:
    rows = [
        ListingRecord("DE0000000002", "XETRA", "BBB", name="B"),
        ListingRecord("DE0000000001", "XETRA", "AAA", name="A"),
    ]
    result = build_listing_gold(rows)
    assert [row.key for row in result.rows] == [
        ("DE0000000001", "XETRA", "AAA"),
        ("DE0000000002", "XETRA", "BBB"),
    ]
    assert result.row_count == 2
    assert len(result.semantic_fingerprint) == 64
    assert tuple(result.semantic_rows()[0]) == (
        "isin",
        "exchange",
        "code",
        "name",
        "instrument_type",
        "currency",
        "country",
        "is_active",
    )
    assert result.semantic_rows()[0]["is_active"] is True


def test_replay_fingerprint_is_stable_under_input_order() -> None:
    rows = [
        ListingRecord("DE0000000002", "XETRA", "BBB"),
        ListingRecord("DE0000000001", "XETRA", "AAA"),
    ]
    assert build_listing_gold(rows).semantic_fingerprint == build_listing_gold(
        reversed(rows)
    ).semantic_fingerprint


def test_duplicate_business_key_fails() -> None:
    duplicate = ListingRecord("DE0000000001", "XETRA", "AAA")
    with pytest.raises(ValueError, match="duplicate Gold listing key"):
        build_listing_gold([duplicate, duplicate])

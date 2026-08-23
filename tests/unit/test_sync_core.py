from datetime import UTC, datetime

import pytest

from xetra_loader.sync import SyncCounters, semantic_fingerprint


def test_semantic_fingerprint_is_order_independent() -> None:
    left, left_count = semantic_fingerprint(
        [{"id": 2, "value": "b"}, {"id": 1, "value": "a"}]
    )
    right, right_count = semantic_fingerprint(
        [{"value": "a", "id": 1}, {"value": "b", "id": 2}]
    )
    assert left == right
    assert left_count == right_count == 2


def test_run_metadata_is_not_part_of_semantic_fingerprint() -> None:
    rows = [{"id": 1, "value": "a"}]
    fingerprint, _ = semantic_fingerprint(rows)
    run_a = {"run_id": "a", "fetched_at": datetime(2026, 8, 22, 10, 0, tzinfo=UTC)}
    run_b = {"run_id": "b", "fetched_at": datetime(2026, 8, 22, 11, 0, tzinfo=UTC)}
    assert run_a != run_b
    assert semantic_fingerprint(rows)[0] == fingerprint


def test_counters_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        SyncCounters(updated=-1)


def test_counters_total_all_generic_mutations() -> None:
    counters = SyncCounters(inserted=1, updated=2, deleted=3, retracted=4)
    assert counters.total_mutations == 10

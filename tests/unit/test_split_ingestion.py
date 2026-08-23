from collections.abc import Mapping
from datetime import date

from xetra_loader.contracts.corporate_actions import ActionStatus
from xetra_loader.contracts.listings import ListingRecord
from xetra_loader.ingestion.splits import JSONValue, ingest_splits


class FixtureTransport:
    def __init__(self, payload: JSONValue) -> None:
        self.payload = payload
        self.calls: list[tuple[str, Mapping[str, str | int | float] | None]] = []

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> JSONValue:
        self.calls.append((path, params))
        return self.payload


def _listing() -> ListingRecord:
    return ListingRecord("DE0000000001", "XETRA", "AAA")


def _payload(ratio: str = "2:1") -> JSONValue:
    return [{"date": "2026-08-20", "split": ratio}]


def test_full_history_and_overlap_requests() -> None:
    full_transport = FixtureTransport(_payload())
    ingest_splits(full_transport, _listing())
    assert full_transport.calls == [("splits/AAA.XETRA", None)]

    overlap_transport = FixtureTransport(_payload())
    ingest_splits(overlap_transport, _listing(), last_event_date=date(2026, 8, 22))
    assert overlap_transport.calls == [("splits/AAA.XETRA", {"from": "2026-08-15"})]


def test_ratio_derives_split_factor() -> None:
    result = ingest_splits(FixtureTransport(_payload("3:2")), _listing())
    assert str(result.silver_records[0].split_factor) == "1.5"


def test_unchanged_replay_is_stable() -> None:
    first = ingest_splits(FixtureTransport(_payload()), _listing())
    replay = ingest_splits(
        FixtureTransport(_payload()),
        _listing(),
        previous_records=first.silver_records,
    )
    assert replay.correction_count == 0
    assert replay.retraction_count == 0
    assert replay.silver_records == first.silver_records
    assert replay.bronze_payload == first.bronze_payload


def test_correction_is_reconciled_once() -> None:
    first = ingest_splits(FixtureTransport(_payload("2:1")), _listing())
    corrected = ingest_splits(
        FixtureTransport(_payload("3:1")),
        _listing(),
        previous_records=first.silver_records,
    )
    assert corrected.correction_count == 1
    assert corrected.retraction_count == 0
    assert len(corrected.silver_records) == 2
    assert sum(record.status is ActionStatus.RETRACTED for record in corrected.silver_records) == 1


def test_removed_overlap_event_is_retracted() -> None:
    first = ingest_splits(FixtureTransport(_payload()), _listing())
    removed = ingest_splits(
        FixtureTransport([]),
        _listing(),
        previous_records=first.silver_records,
    )
    assert removed.correction_count == 0
    assert removed.retraction_count == 1
    assert removed.silver_records[0].status is ActionStatus.RETRACTED

from collections.abc import Mapping
from datetime import UTC, date

from xetra_loader.contracts.listings import ListingRecord
from xetra_loader.ingestion.quotes import JSONValue, ingest_quotes


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


def _payload(close: float = 10.0, extra: bool = False) -> JSONValue:
    rows: list[JSONValue] = [
        {
            "date": "2026-08-21",
            "open": 9.0,
            "high": 11.0,
            "low": 8.5,
            "close": close,
            "adjusted_close": close,
            "volume": 100,
        }
    ]
    if extra:
        rows.append(
            {
                "date": "2026-08-22",
                "open": 10.0,
                "high": 12.0,
                "low": 9.5,
                "close": 11.0,
                "adjusted_close": 11.0,
                "volume": 200,
            }
        )
    return rows


def test_full_history_has_no_from_parameter_and_utc_timestamps() -> None:
    transport = FixtureTransport(_payload())
    result = ingest_quotes(transport, _listing())
    assert transport.calls == [("eod/AAA.XETRA", None)]
    assert result.silver_records[0].timestamp_eod.tzinfo is UTC
    assert result.inserted_keys == (("DE0000000001", "XETRA", "AAA", date(2026, 8, 21)),)


def test_incremental_fetch_starts_seven_calendar_days_before_last_date() -> None:
    transport = FixtureTransport(_payload())
    ingest_quotes(transport, _listing(), last_business_date=date(2026, 8, 22))
    assert transport.calls == [("eod/AAA.XETRA", {"from": "2026-08-15"})]


def test_unchanged_replay_has_no_semantic_delta() -> None:
    first = ingest_quotes(FixtureTransport(_payload()), _listing())
    replay = ingest_quotes(
        FixtureTransport(_payload()),
        _listing(),
        previous_records=first.silver_records,
    )
    assert replay.inserted_keys == ()
    assert replay.corrected_keys == ()
    assert replay.bronze_payload == first.bronze_payload


def test_correction_is_detected_once() -> None:
    first = ingest_quotes(FixtureTransport(_payload(10.0)), _listing())
    corrected = ingest_quotes(
        FixtureTransport(_payload(10.5)),
        _listing(),
        previous_records=first.silver_records,
    )
    assert corrected.inserted_keys == ()
    assert corrected.corrected_keys == (("DE0000000001", "XETRA", "AAA", date(2026, 8, 21)),)


def test_new_date_is_exactly_one_new_key() -> None:
    first = ingest_quotes(FixtureTransport(_payload()), _listing())
    updated = ingest_quotes(
        FixtureTransport(_payload(extra=True)),
        _listing(),
        previous_records=first.silver_records,
    )
    assert updated.corrected_keys == ()
    assert updated.inserted_keys == (("DE0000000001", "XETRA", "AAA", date(2026, 8, 22)),)


def test_all_zero_ohlc_with_valid_close_is_a_missing_provider_sentinel() -> None:
    payload = _payload()
    row = payload[0]
    assert isinstance(row, dict)
    row.update({"open": 0, "high": 0, "low": 0, "close": 20.15})

    result = ingest_quotes(FixtureTransport(payload), _listing())

    quote = result.silver_records[0]
    assert quote.open is None
    assert quote.high is None
    assert quote.low is None
    assert str(quote.close) == "20.15"

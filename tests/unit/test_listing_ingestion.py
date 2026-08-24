from collections.abc import Mapping

from xetra_loader.ingestion.listings import JSONValue, ingest_xetra_listings


class FixtureTransport:
    def __init__(self, active: JSONValue, delisted: JSONValue | None = None) -> None:
        self.active = active
        self.delisted: JSONValue = [] if delisted is None else delisted
        self.calls: list[tuple[str, Mapping[str, str | int | float] | None]] = []

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> JSONValue:
        self.calls.append((path, params))
        return self.delisted if params == {"delisted": 1} else self.active


def test_mixed_fixture_keeps_every_non_empty_isin_without_instrument_filters() -> None:
    fixture: JSONValue = [
        {"Code": "ETF", "Exchange": "XETRA", "ISIN": "DE0000000001", "Type": "ETF"},
        {
            "Code": "STOCK",
            "Exchange": "XETRA",
            "ISIN": "DE0000000002",
            "Type": "Common Stock",
        },
        {"Code": "FUND", "Exchange": "XETRA", "ISIN": "DE0000000003", "Type": "Fund"},
        {"Code": "EMPTY", "Exchange": "XETRA", "ISIN": ""},
        {"Code": "NONE", "Exchange": "XETRA", "ISIN": None},
    ]
    transport = FixtureTransport(fixture)
    result = ingest_xetra_listings(transport)
    assert transport.calls == [
        ("exchange-symbol-list/XETRA", None),
        ("exchange-symbol-list/XETRA", {"delisted": 1}),
    ]
    assert [record.code for record in result.silver_records] == ["ETF", "STOCK", "FUND"]


def test_replay_is_deterministic_even_if_provider_order_changes() -> None:
    first: JSONValue = [
        {"Code": "BBB", "Exchange": "XETRA", "ISIN": "DE0000000002"},
        {"Code": "AAA", "Exchange": "XETRA", "ISIN": "DE0000000001"},
    ]
    second: JSONValue = list(reversed(first))
    left = ingest_xetra_listings(FixtureTransport(first))
    right = ingest_xetra_listings(FixtureTransport(second))
    assert left.bronze_payload == right.bronze_payload
    assert left.silver_records == right.silver_records


def test_active_delisted_and_missing_identities_have_explicit_lifecycle() -> None:
    active: JSONValue = [{"Code": "ACTIVE", "Exchange": "XETRA", "ISIN": "DE0000000001"}]
    delisted: JSONValue = [{"Code": "OLD", "Exchange": "XETRA", "ISIN": "DE0000000002"}]
    previous = ingest_xetra_listings(FixtureTransport(active, delisted)).silver_records
    refreshed = ingest_xetra_listings(
        FixtureTransport(active, []),
        previous_records=previous,
    )

    assert [(record.code, record.is_active) for record in previous] == [
        ("ACTIVE", True),
        ("OLD", False),
    ]
    assert [(record.code, record.is_active) for record in refreshed.silver_records] == [
        ("ACTIVE", True),
        ("OLD", False),
    ]

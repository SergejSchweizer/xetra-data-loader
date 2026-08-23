from collections.abc import Mapping

from xetra_loader.ingestion.listings import JSONValue, ingest_xetra_listings


class FixtureTransport:
    def __init__(self, payload: JSONValue) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> JSONValue:
        assert params is None
        self.calls.append(path)
        return self.payload


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
    assert transport.calls == ["exchange-symbol-list/XETRA"]
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

"""XETRA listing ingestion from EODHD into deterministic Bronze/Silver state."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from xetra_data_loader.contracts.listings import ListingRecord, normalize_listings

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


class JsonTransport(Protocol):
    """Provider seam required by listing ingestion."""

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> JSONValue: ...


@dataclass(frozen=True, slots=True)
class ListingIngestionResult:
    """Deterministic Bronze payload plus normalized Silver listing rows."""

    bronze_payload: str
    silver_records: tuple[ListingRecord, ...]


def ingest_xetra_listings(transport: JsonTransport) -> ListingIngestionResult:
    """Fetch every XETRA symbol and exclude only rows without a usable ISIN."""

    payload = transport.get_json("exchange-symbol-list/XETRA")
    if not isinstance(payload, list):
        raise ValueError("EODHD XETRA listing response must be a JSON array")

    rows: list[dict[str, object]] = []
    bronze_rows: list[dict[str, JSONValue]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each EODHD XETRA listing must be a JSON object")
        typed_item = cast(dict[str, JSONValue], item)
        bronze_rows.append(typed_item)
        rows.append(cast(dict[str, object], item))

    bronze_rows.sort(key=_canonical_row)
    bronze_payload = json.dumps(
        bronze_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ListingIngestionResult(
        bronze_payload=bronze_payload,
        silver_records=normalize_listings(rows),
    )


def _canonical_row(row: dict[str, JSONValue]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

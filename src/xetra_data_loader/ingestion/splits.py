"""Split ingestion with deterministic correction and retraction reconciliation."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol, cast

from xetra_data_loader.contracts.corporate_actions import ActionStatus, SplitEvent, retract_split
from xetra_data_loader.contracts.listings import ListingRecord

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]

_OVERLAP_DAYS = 7


class JsonTransport(Protocol):
    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> JSONValue: ...


@dataclass(frozen=True, slots=True)
class SplitIngestionResult:
    bronze_payload: str
    silver_records: tuple[SplitEvent, ...]
    correction_count: int
    retraction_count: int


def ingest_splits(
    transport: JsonTransport,
    listing: ListingRecord,
    *,
    last_event_date: date | None = None,
    previous_records: Iterable[SplitEvent] = (),
) -> SplitIngestionResult:
    """Fetch full history or overlap and reconcile corrections/retractions by event date."""

    params: dict[str, str | int | float] = {}
    if last_event_date is not None:
        params["from"] = (last_event_date - timedelta(days=_OVERLAP_DAYS)).isoformat()
    payload = transport.get_json(f"splits/{listing.code}.{listing.exchange}", params or None)
    if not isinstance(payload, list):
        raise ValueError("EODHD split response must be a JSON array")

    bronze_rows: list[dict[str, JSONValue]] = []
    current: list[SplitEvent] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each EODHD split must be a JSON object")
        row = cast(dict[str, JSONValue], item)
        bronze_rows.append(row)
        current.append(_normalize_split(listing, row))

    active_previous = tuple(record for record in previous_records if record.status is ActionStatus.ACTIVE)
    previous_by_date = _unique_by_date(active_previous)
    current_by_date = _unique_by_date(current)
    reconciled: list[SplitEvent] = list(current_by_date.values())
    corrections = 0
    retractions = 0

    for event_date, previous in previous_by_date.items():
        current_event = current_by_date.get(event_date)
        if current_event is None:
            reconciled.append(retract_split(previous))
            retractions += 1
        elif current_event.event_key != previous.event_key:
            reconciled.append(retract_split(previous))
            corrections += 1

    bronze_rows.sort(key=_canonical_row)
    reconciled.sort(key=lambda event: (event.event_date, event.event_key, event.status.value))
    return SplitIngestionResult(
        bronze_payload=json.dumps(
            bronze_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        silver_records=tuple(reconciled),
        correction_count=corrections,
        retraction_count=retractions,
    )


def _normalize_split(listing: ListingRecord, row: Mapping[str, JSONValue]) -> SplitEvent:
    ratio = _required_text(row, "split")
    return SplitEvent(
        isin=listing.isin,
        exchange=listing.exchange,
        code=listing.code,
        event_date=date.fromisoformat(_required_text(row, "date")),
        split_ratio=ratio,
        split_factor=_split_factor(row.get("split_factor", row.get("splitFactor")), ratio),
    )


def _unique_by_date(records: Iterable[SplitEvent]) -> dict[date, SplitEvent]:
    result: dict[date, SplitEvent] = {}
    for record in records:
        if record.event_date in result:
            raise ValueError(f"multiple split events share date {record.event_date}")
        result[record.event_date] = record
    return result


def _required_text(row: Mapping[str, JSONValue], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"split field {key} must be non-empty text")
    return value.strip()


def _split_factor(value: JSONValue, ratio: str) -> Decimal | None:
    if value is not None and value != "":
        if isinstance(value, (bool, list, dict)):
            raise ValueError("split factor must be numeric")
        return Decimal(str(value))
    if ":" not in ratio:
        return None
    numerator, denominator = ratio.split(":", 1)
    denominator_decimal = Decimal(denominator.strip())
    if denominator_decimal == 0:
        raise ValueError("split ratio denominator must not be zero")
    return Decimal(numerator.strip()) / denominator_decimal


def _canonical_row(row: dict[str, JSONValue]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

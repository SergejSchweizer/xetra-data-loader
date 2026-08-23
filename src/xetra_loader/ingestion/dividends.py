"""Dividend ingestion with deterministic correction and retraction reconciliation."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol

from xetra_loader.contracts.corporate_actions import (
    ActionStatus,
    DividendEvent,
    retract_dividend,
)
from xetra_loader.contracts.listings import ListingRecord

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]

_OVERLAP_DAYS = 7


class JsonTransport(Protocol):
    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> JSONValue: ...


@dataclass(frozen=True, slots=True)
class DividendIngestionResult:
    bronze_payload: str
    silver_records: tuple[DividendEvent, ...]
    correction_count: int
    retraction_count: int


def ingest_dividends(
    transport: JsonTransport,
    listing: ListingRecord,
    *,
    last_event_date: date | None = None,
    previous_records: Iterable[DividendEvent] = (),
) -> DividendIngestionResult:
    """Fetch full history or overlap and reconcile corrections/retractions by event date."""

    params: dict[str, str | int | float] = {}
    if last_event_date is not None:
        params["from"] = (last_event_date - timedelta(days=_OVERLAP_DAYS)).isoformat()
    payload = transport.get_json(f"div/{listing.code}.{listing.exchange}", params or None)
    if not isinstance(payload, list):
        raise ValueError("EODHD dividend response must be a JSON array")

    bronze_rows: list[dict[str, JSONValue]] = []
    current: list[DividendEvent] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each EODHD dividend must be a JSON object")
        bronze_rows.append(item)
        current.append(_normalize_dividend(listing, item))

    active_previous = tuple(
        record for record in previous_records if record.status is ActionStatus.ACTIVE
    )
    previous_by_date = _unique_by_date(active_previous)
    current_by_date = _unique_by_date(current)
    reconciled: list[DividendEvent] = list(current_by_date.values())
    corrections = 0
    retractions = 0

    for event_date, previous in previous_by_date.items():
        current_event = current_by_date.get(event_date)
        if current_event is None:
            reconciled.append(retract_dividend(previous))
            retractions += 1
        elif current_event.event_key != previous.event_key:
            reconciled.append(retract_dividend(previous))
            corrections += 1

    bronze_rows.sort(key=_canonical_row)
    reconciled.sort(key=lambda event: (event.event_date, event.event_key, event.status.value))
    return DividendIngestionResult(
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


def _normalize_dividend(
    listing: ListingRecord,
    row: Mapping[str, JSONValue],
) -> DividendEvent:
    return DividendEvent(
        isin=listing.isin,
        exchange=listing.exchange,
        code=listing.code,
        event_date=date.fromisoformat(_required_text(row, "date")),
        value=_required_decimal(row, "value"),
        currency=_optional_text(row.get("currency")),
        period=_optional_text(row.get("period")),
        declaration_date=_optional_date(row.get("declarationDate")),
        record_date=_optional_date(row.get("recordDate")),
        payment_date=_optional_date(row.get("paymentDate")),
    )


def _unique_by_date(records: Iterable[DividendEvent]) -> dict[date, DividendEvent]:
    result: dict[date, DividendEvent] = {}
    for record in records:
        if record.event_date in result:
            raise ValueError(f"multiple dividend events share date {record.event_date}")
        result[record.event_date] = record
    return result


def _required_text(row: Mapping[str, JSONValue], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"dividend field {key} must be non-empty text")
    return value.strip()


def _required_decimal(row: Mapping[str, JSONValue], key: str) -> Decimal:
    value = row.get(key)
    if value is None or value == "" or isinstance(value, (bool, list, dict)):
        raise ValueError(f"dividend field {key} must be numeric")
    return Decimal(str(value))


def _optional_text(value: JSONValue) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (list, dict)):
        raise ValueError("dividend text field must be scalar")
    return str(value).strip() or None


def _optional_date(value: JSONValue) -> date | None:
    text = _optional_text(value)
    return None if text is None else date.fromisoformat(text)


def _canonical_row(row: dict[str, JSONValue]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

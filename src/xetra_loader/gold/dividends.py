"""Validated deterministic Gold builder for dividend events."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from xetra_loader.contracts.corporate_actions import ActionStatus, DividendEvent

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class DividendGoldResult:
    """Active serving rows plus deterministic retraction metadata."""

    rows: tuple[DividendEvent, ...]
    retracted_keys: tuple[tuple[str, str, str, str], ...]
    row_count: int
    semantic_fingerprint: str

    def semantic_rows(self) -> tuple[dict[str, JSONValue], ...]:
        return tuple(_serving_row(row) for row in self.rows)


def build_dividend_gold(records: Iterable[DividendEvent]) -> DividendGoldResult:
    """Validate event keys, separate active rows from retractions, and fingerprint final state."""

    ordered = tuple(sorted(records, key=lambda event: (event.key, event.status.value)))
    seen: set[tuple[str, str, str, str]] = set()
    active: list[DividendEvent] = []
    retracted: list[tuple[str, str, str, str]] = []
    for event in ordered:
        if event.key in seen:
            raise ValueError(f"duplicate Gold dividend key: {event.key}")
        seen.add(event.key)
        if len(event.event_key) != 64:
            raise ValueError("Gold dividend event_key must be SHA-256")
        if event.status is ActionStatus.ACTIVE:
            active.append(event)
        else:
            retracted.append(event.key)

    active_rows = tuple(active)
    retracted_keys = tuple(sorted(retracted))
    payload: dict[str, JSONValue] = {
        "rows": [_serving_row(row) for row in active_rows],
        "retracted_keys": [list(key) for key in retracted_keys],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return DividendGoldResult(
        rows=active_rows,
        retracted_keys=retracted_keys,
        row_count=len(active_rows),
        semantic_fingerprint=hashlib.sha256(encoded).hexdigest(),
    )


def _serving_row(event: DividendEvent) -> dict[str, JSONValue]:
    return {
        "isin": event.isin,
        "exchange": event.exchange,
        "code": event.code,
        "event_key": event.event_key,
        "event_date": event.event_date.isoformat(),
        "declaration_date": _date_text(event.declaration_date),
        "record_date": _date_text(event.record_date),
        "payment_date": _date_text(event.payment_date),
        "value": str(event.value),
        "currency": event.currency,
        "period": event.period,
    }


def _date_text(value: object) -> str | None:
    return None if value is None else str(value)

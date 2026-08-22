"""Validated deterministic Gold builder for XETRA listings."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

from xetra_data_loader.contracts.listings import ListingRecord

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class ListingGoldResult:
    """Validated Gold rows plus deterministic validation metadata."""

    rows: tuple[ListingRecord, ...]
    row_count: int
    semantic_fingerprint: str

    def semantic_rows(self) -> tuple[dict[str, JSONValue], ...]:
        return tuple(row.semantic_dict() for row in self.rows)


def build_listing_gold(records: Iterable[ListingRecord]) -> ListingGoldResult:
    """Validate the serving key and produce deterministic Gold metadata."""

    ordered = tuple(sorted(records, key=lambda record: record.key))
    seen: set[tuple[str, str, str]] = set()
    for record in ordered:
        if not record.isin.strip() or not record.exchange.strip() or not record.code.strip():
            raise ValueError("Gold listing identity fields must be non-empty")
        if record.key in seen:
            raise ValueError(f"duplicate Gold listing key: {record.key}")
        seen.add(record.key)

    semantic_rows = [record.semantic_dict() for record in ordered]
    encoded = json.dumps(
        semantic_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ListingGoldResult(
        rows=ordered,
        row_count=len(ordered),
        semantic_fingerprint=hashlib.sha256(encoded).hexdigest(),
    )

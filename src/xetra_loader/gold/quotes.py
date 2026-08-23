"""Validated deterministic Gold builder for EOD quotes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from xetra_loader.contracts.quotes import QuoteRecord, validate_unique_quotes

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class QuoteGoldResult:
    """Validated Gold quote rows and stable semantic metadata."""

    rows: tuple[QuoteRecord, ...]
    row_count: int
    semantic_fingerprint: str

    def semantic_rows(self) -> tuple[dict[str, JSONValue], ...]:
        return tuple(row.semantic_dict() for row in self.rows)


def build_quote_gold(records: Iterable[QuoteRecord]) -> QuoteGoldResult:
    """Validate serving keys and UTC-midnight timestamp anchors."""

    ordered = validate_unique_quotes(records)
    for record in ordered:
        expected = datetime.combine(record.trade_date, datetime.min.time(), tzinfo=UTC)
        if record.timestamp_eod != expected:
            raise ValueError("Gold quote timestamp_eod must equal trade_date at UTC midnight")
        if record.volume is not None and record.volume < 0:
            raise ValueError("Gold quote volume must be non-negative")

    semantic_rows = [record.semantic_dict() for record in ordered]
    encoded = json.dumps(
        semantic_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return QuoteGoldResult(
        rows=ordered,
        row_count=len(ordered),
        semantic_fingerprint=hashlib.sha256(encoded).hexdigest(),
    )

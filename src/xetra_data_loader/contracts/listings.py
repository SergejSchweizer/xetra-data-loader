"""Deterministic Bronze/Silver/Gold listing dataset contract."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import cast

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class ListingRecord:
    """Normalized listing retained whenever the provider supplies a non-empty ISIN."""

    isin: str
    exchange: str
    code: str
    name: str | None = None
    instrument_type: str | None = None
    currency: str | None = None
    country: str | None = None

    @property
    def key(self) -> tuple[str, str, str]:
        return self.isin, self.exchange, self.code

    def semantic_dict(self) -> dict[str, JSONValue]:
        return {
            "isin": self.isin,
            "exchange": self.exchange,
            "code": self.code,
            "name": self.name,
            "instrument_type": self.instrument_type,
            "currency": self.currency,
            "country": self.country,
        }


def normalize_listing(provider_row: Mapping[str, object]) -> ListingRecord | None:
    """Normalize one EODHD listing; only a missing/empty ISIN causes exclusion."""

    isin = _optional_text(provider_row.get("ISIN"))
    if isin is None:
        isin = _optional_text(provider_row.get("Isin"))
    if isin is None:
        return None
    exchange = _required_text("Exchange", provider_row.get("Exchange"))
    code = _required_text("Code", provider_row.get("Code"))
    return ListingRecord(
        isin=isin.upper(),
        exchange=exchange.upper(),
        code=code,
        name=_optional_text(provider_row.get("Name")),
        instrument_type=_optional_text(provider_row.get("Type")),
        currency=_optional_text(provider_row.get("Currency")),
        country=_optional_text(provider_row.get("Country")),
    )


def normalize_listings(provider_rows: Iterable[Mapping[str, object]]) -> tuple[ListingRecord, ...]:
    """Normalize and deterministically order the complete retained listing universe."""

    records = [record for row in provider_rows if (record := normalize_listing(row)) is not None]
    return tuple(sorted(records, key=lambda record: record.key))


def serialize_listings(records: Iterable[ListingRecord]) -> str:
    """Serialize semantic listing rows in deterministic key order."""

    ordered = sorted(records, key=lambda record: record.key)
    return json.dumps(
        [record.semantic_dict() for record in ordered],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def deserialize_listings(payload: str) -> tuple[ListingRecord, ...]:
    """Round-trip the deterministic semantic representation."""

    decoded = cast(list[dict[str, JSONValue]], json.loads(payload))
    records = (
        ListingRecord(
            isin=_decoded_required(row, "isin"),
            exchange=_decoded_required(row, "exchange"),
            code=_decoded_required(row, "code"),
            name=_decoded_optional(row, "name"),
            instrument_type=_decoded_optional(row, "instrument_type"),
            currency=_decoded_optional(row, "currency"),
            country=_decoded_optional(row, "country"),
        )
        for row in decoded
    )
    return tuple(sorted(records, key=lambda record: record.key))


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(name: str, value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError(f"provider listing field {name} must be non-empty")
    return text


def _decoded_required(row: Mapping[str, JSONValue], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"serialized listing field {key} must be non-empty text")
    return value


def _decoded_optional(row: Mapping[str, JSONValue], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"serialized listing field {key} must be text or null")
    return value

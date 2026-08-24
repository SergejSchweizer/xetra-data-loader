"""Deterministic dividend and split event contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from xetra_loader.contracts.numeric import canonical_decimal, require_finite

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


class ActionStatus(StrEnum):
    """Reconciliation state for a provider event inside the correction window."""

    ACTIVE = "active"
    RETRACTED = "retracted"


@dataclass(frozen=True, slots=True)
class CorporateActionRunMetadata:
    """Execution metadata excluded from deterministic event keys."""

    run_id: str
    fetched_at_utc: datetime

    def __post_init__(self) -> None:
        if self.fetched_at_utc.tzinfo is None or self.fetched_at_utc.utcoffset() is None:
            raise ValueError("fetched_at_utc must be timezone-aware")
        if self.fetched_at_utc.utcoffset() != timedelta(0):
            raise ValueError("fetched_at_utc must use UTC")


@dataclass(frozen=True, slots=True)
class DividendEvent:
    """Dividend schema with a content-addressed provider business key."""

    isin: str
    exchange: str
    code: str
    event_date: date
    value: Decimal
    currency: str | None = None
    period: str | None = None
    declaration_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None
    status: ActionStatus = ActionStatus.ACTIVE

    def __post_init__(self) -> None:
        require_finite(self.value, field="dividend value")

    @property
    def event_key(self) -> str:
        return _event_key("dividend", self.business_fields())

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.isin, self.exchange, self.code, self.event_key

    def business_fields(self) -> dict[str, JSONValue]:
        return {
            "isin": self.isin,
            "exchange": self.exchange,
            "code": self.code,
            "event_date": self.event_date.isoformat(),
            "value": canonical_decimal(self.value),
            "currency": self.currency,
            "period": self.period,
            "declaration_date": _date_text(self.declaration_date),
            "record_date": _date_text(self.record_date),
            "payment_date": _date_text(self.payment_date),
        }


@dataclass(frozen=True, slots=True)
class SplitEvent:
    """Split schema kept distinct from dividends."""

    isin: str
    exchange: str
    code: str
    event_date: date
    split_ratio: str
    split_factor: Decimal | None = None
    status: ActionStatus = ActionStatus.ACTIVE

    def __post_init__(self) -> None:
        if self.split_factor is not None:
            require_finite(self.split_factor, field="split factor")
            if self.split_factor <= 0:
                raise ValueError("split factor must be positive")

    @property
    def event_key(self) -> str:
        return _event_key("split", self.business_fields())

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.isin, self.exchange, self.code, self.event_key

    def business_fields(self) -> dict[str, JSONValue]:
        return {
            "isin": self.isin,
            "exchange": self.exchange,
            "code": self.code,
            "event_date": self.event_date.isoformat(),
            "split_ratio": self.split_ratio,
            "split_factor": (
                None if self.split_factor is None else canonical_decimal(self.split_factor)
            ),
        }


def retract_dividend(event: DividendEvent) -> DividendEvent:
    """Represent provider removal without changing the deterministic event key."""

    return replace(event, status=ActionStatus.RETRACTED)


def retract_split(event: SplitEvent) -> SplitEvent:
    """Represent provider removal without changing the deterministic event key."""

    return replace(event, status=ActionStatus.RETRACTED)


def _event_key(kind: str, business_fields: dict[str, JSONValue]) -> str:
    payload: dict[str, JSONValue] = {"kind": kind, "business_fields": business_fields}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _date_text(value: date | None) -> str | None:
    return None if value is None else value.isoformat()

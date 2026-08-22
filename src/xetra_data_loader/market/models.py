"""Typed rows for the frozen ``portfell_market`` PostgreSQL contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

_ZERO = timedelta(0)


def _require_text(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_utc(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    if value.utcoffset() != _ZERO:
        raise ValueError(f"{name} must use UTC")


@dataclass(frozen=True, slots=True)
class ListingRow:
    """One serving listing keyed by ``(isin, exchange, code)``."""

    isin: str
    exchange: str
    code: str
    fetched_at_utc: datetime
    published_at_utc: datetime
    name: str | None = None
    instrument_type: str | None = None
    currency: str | None = None
    country: str | None = None

    def __post_init__(self) -> None:
        _require_text("isin", self.isin)
        _require_text("exchange", self.exchange)
        _require_text("code", self.code)
        _require_utc("fetched_at_utc", self.fetched_at_utc)
        _require_utc("published_at_utc", self.published_at_utc)


@dataclass(frozen=True, slots=True)
class QuoteRow:
    """One EOD quote keyed by listing identity plus ``trade_date``."""

    isin: str
    exchange: str
    code: str
    trade_date: date
    timestamp_eod: datetime
    close: Decimal
    fetched_at_utc: datetime
    published_at_utc: datetime
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    adjusted_close: Decimal | None = None
    volume: int | None = None

    def __post_init__(self) -> None:
        _require_text("isin", self.isin)
        _require_text("exchange", self.exchange)
        _require_text("code", self.code)
        _require_utc("timestamp_eod", self.timestamp_eod)
        _require_utc("fetched_at_utc", self.fetched_at_utc)
        _require_utc("published_at_utc", self.published_at_utc)
        if (
            self.timestamp_eod.date() != self.trade_date
            or self.timestamp_eod.time() != datetime.min.time()
        ):
            raise ValueError("timestamp_eod must equal trade_date at 00:00:00 UTC")
        if self.volume is not None and self.volume < 0:
            raise ValueError("volume must be non-negative")


@dataclass(frozen=True, slots=True)
class DividendRow:
    """One dividend event keyed by listing identity plus deterministic ``event_key``."""

    isin: str
    exchange: str
    code: str
    event_key: str
    event_date: date
    value: Decimal
    fetched_at_utc: datetime
    published_at_utc: datetime
    declaration_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None
    currency: str | None = None
    period: str | None = None

    def __post_init__(self) -> None:
        _validate_event_identity(self.isin, self.exchange, self.code, self.event_key)
        _require_utc("fetched_at_utc", self.fetched_at_utc)
        _require_utc("published_at_utc", self.published_at_utc)


@dataclass(frozen=True, slots=True)
class SplitRow:
    """One split event keyed by listing identity plus deterministic ``event_key``."""

    isin: str
    exchange: str
    code: str
    event_key: str
    event_date: date
    split_ratio: str
    fetched_at_utc: datetime
    published_at_utc: datetime
    split_factor: Decimal | None = None

    def __post_init__(self) -> None:
        _validate_event_identity(self.isin, self.exchange, self.code, self.event_key)
        _require_text("split_ratio", self.split_ratio)
        _require_utc("fetched_at_utc", self.fetched_at_utc)
        _require_utc("published_at_utc", self.published_at_utc)


def _validate_event_identity(isin: str, exchange: str, code: str, event_key: str) -> None:
    _require_text("isin", isin)
    _require_text("exchange", exchange)
    _require_text("code", code)
    if len(event_key) != 64 or any(character not in "0123456789abcdef" for character in event_key):
        raise ValueError("event_key must be a lowercase hexadecimal SHA-256")

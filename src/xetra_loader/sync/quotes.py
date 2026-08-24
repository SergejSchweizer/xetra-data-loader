"""Transactional PostgreSQL publication for validated EOD quote Gold."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from psycopg import Connection, Cursor

from xetra_loader.gold.quotes import QuoteGoldResult
from xetra_loader.sync.core import SyncCounters, SyncOutcome, run_sync

QuoteSemantic = tuple[
    Decimal | None,
    Decimal | None,
    Decimal | None,
    Decimal,
    Decimal | None,
    int | None,
]


def sync_quotes(
    connection: Connection[Any],
    gold: QuoteGoldResult,
    *,
    run_id: str | None = None,
    published_at_utc: datetime | None = None,
    fetched_at_by_key: Mapping[tuple[str, str, str, date], datetime] | None = None,
) -> SyncOutcome:
    """Insert new quote dates, update corrections, and skip semantic replays."""

    published_at = published_at_utc or datetime.now(UTC)
    _require_utc(published_at)

    def mutate(cursor: Cursor[Any]) -> SyncCounters:
        inserted = 0
        updated = 0
        deleted = 0
        expected_keys = {row.key for row in gold.rows}
        for row in gold.rows:
            fetched_at = _fetched_at(row.key, fetched_at_by_key, published_at)
            cursor.execute(
                "SELECT open, high, low, close, adjusted_close, volume "
                "FROM xetra_loader.eod_quotes "
                "WHERE isin = %s AND exchange = %s AND code = %s AND trade_date = %s",
                row.key,
            )
            existing = cast(QuoteSemantic | None, cursor.fetchone())
            semantic: QuoteSemantic = (
                row.open,
                row.high,
                row.low,
                row.close,
                row.adjusted_close,
                row.volume,
            )
            if existing is None:
                cursor.execute(
                    "INSERT INTO xetra_loader.eod_quotes "
                    "(isin, exchange, code, trade_date, timestamp_eod, open, high, low, close, "
                    "adjusted_close, volume, fetched_at_utc, published_at_utc) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        *row.key,
                        row.timestamp_eod,
                        *semantic,
                        fetched_at,
                        published_at,
                    ),
                )
                inserted += 1
            elif existing != semantic:
                cursor.execute(
                    "UPDATE xetra_loader.eod_quotes SET timestamp_eod = %s, open = %s, "
                    "high = %s, low = %s, close = %s, adjusted_close = %s, volume = %s, "
                    "fetched_at_utc = %s, published_at_utc = %s "
                    "WHERE isin = %s AND exchange = %s AND code = %s AND trade_date = %s",
                    (
                        row.timestamp_eod,
                        *semantic,
                        fetched_at,
                        published_at,
                        *row.key,
                    ),
                )
                updated += 1
        existing_keys = cursor.execute(
            "SELECT isin, exchange, code, trade_date FROM xetra_loader.eod_quotes"
        ).fetchall()
        for key in existing_keys:
            normalized = cast(tuple[str, str, str, date], key)
            if normalized not in expected_keys:
                cursor.execute(
                    "DELETE FROM xetra_loader.eod_quotes "
                    "WHERE isin = %s AND exchange = %s AND code = %s AND trade_date = %s",
                    normalized,
                )
                deleted += cursor.rowcount
        return SyncCounters(inserted=inserted, updated=updated, deleted=deleted)

    return run_sync(
        connection,
        dataset="eod_quotes",
        semantic_rows=gold.semantic_rows(),
        mutate=mutate,
        run_id=run_id,
    )


def _require_utc(value: datetime) -> None:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None or offset != UTC.utcoffset(value):
        raise ValueError("published_at_utc must be timezone-aware UTC")


def _fetched_at(
    key: tuple[str, str, str, date],
    values: Mapping[tuple[str, str, str, date], datetime] | None,
    published_at: datetime,
) -> datetime:
    value = published_at if values is None else values.get(key, published_at)
    _require_utc(value)
    if value > published_at:
        raise ValueError("fetched_at_utc must not be after published_at_utc")
    return value

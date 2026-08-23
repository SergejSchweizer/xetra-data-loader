"""Transactional PostgreSQL publication for validated EOD quote Gold."""

from __future__ import annotations

from datetime import UTC, datetime
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
) -> SyncOutcome:
    """Insert new quote dates, update corrections, and skip semantic replays."""

    published_at = published_at_utc or datetime.now(UTC)
    _require_utc(published_at)

    def mutate(cursor: Cursor[Any]) -> SyncCounters:
        inserted = 0
        updated = 0
        for row in gold.rows:
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
                        published_at,
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
                        published_at,
                        published_at,
                        *row.key,
                    ),
                )
                updated += 1
        return SyncCounters(inserted=inserted, updated=updated)

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

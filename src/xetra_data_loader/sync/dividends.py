"""Transactional PostgreSQL publication for validated dividend Gold."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from psycopg import Connection, Cursor

from xetra_data_loader.gold.dividends import DividendGoldResult
from xetra_data_loader.sync.core import JSONValue, SyncCounters, SyncOutcome, run_sync


def sync_dividends(
    connection: Connection[Any],
    gold: DividendGoldResult,
    *,
    run_id: str | None = None,
    published_at_utc: datetime | None = None,
) -> SyncOutcome:
    """Apply active dividend events and tombstone retractions in one transaction."""

    published_at = published_at_utc or datetime.now(UTC)
    _require_utc(published_at)
    semantic_rows: list[dict[str, JSONValue]] = list(gold.semantic_rows())
    semantic_rows.extend(
        {
            "isin": key[0],
            "exchange": key[1],
            "code": key[2],
            "event_key": key[3],
            "retracted": True,
        }
        for key in gold.retracted_keys
    )

    def mutate(cursor: Cursor[Any]) -> SyncCounters:
        inserted = 0
        updated = 0
        retracted = 0
        for key in gold.retracted_keys:
            cursor.execute(
                "DELETE FROM portfell_market.dividends "
                "WHERE isin = %s AND exchange = %s AND code = %s AND event_key = %s",
                key,
            )
            if cursor.rowcount > 0:
                retracted += cursor.rowcount

        for event in gold.rows:
            cursor.execute(
                "SELECT event_date, declaration_date, record_date, payment_date, value, currency, period "
                "FROM portfell_market.dividends "
                "WHERE isin = %s AND exchange = %s AND code = %s AND event_key = %s",
                event.key,
            )
            existing = cast(
                tuple[
                    date,
                    date | None,
                    date | None,
                    date | None,
                    Decimal,
                    str | None,
                    str | None,
                ]
                | None,
                cursor.fetchone(),
            )
            semantic = (
                event.event_date,
                event.declaration_date,
                event.record_date,
                event.payment_date,
                event.value,
                event.currency,
                event.period,
            )
            if existing is None:
                cursor.execute(
                    "INSERT INTO portfell_market.dividends "
                    "(isin, exchange, code, event_key, event_date, declaration_date, record_date, "
                    "payment_date, value, currency, period, fetched_at_utc, published_at_utc) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (*event.key, *semantic, published_at, published_at),
                )
                inserted += 1
            elif existing != semantic:
                cursor.execute(
                    "UPDATE portfell_market.dividends SET event_date = %s, declaration_date = %s, "
                    "record_date = %s, payment_date = %s, value = %s, currency = %s, period = %s, "
                    "fetched_at_utc = %s, published_at_utc = %s "
                    "WHERE isin = %s AND exchange = %s AND code = %s AND event_key = %s",
                    (*semantic, published_at, published_at, *event.key),
                )
                updated += 1
        return SyncCounters(inserted=inserted, updated=updated, retracted=retracted)

    return run_sync(
        connection,
        dataset="dividends",
        semantic_rows=semantic_rows,
        mutate=mutate,
        run_id=run_id,
    )


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("published_at_utc must be timezone-aware UTC")

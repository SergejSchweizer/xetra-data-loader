"""Transactional PostgreSQL publication for validated listing Gold."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from psycopg import Connection, Cursor

from xetra_data_loader.gold.listings import ListingGoldResult
from xetra_data_loader.sync.core import SyncCounters, SyncOutcome, run_sync


def sync_listings(
    connection: Connection[Any],
    gold: ListingGoldResult,
    *,
    run_id: str | None = None,
    published_at_utc: datetime | None = None,
) -> SyncOutcome:
    """Insert/update listing rows while preserving semantic no-op behavior."""

    published_at = published_at_utc or datetime.now(UTC)
    _require_utc(published_at)

    def mutate(cursor: Cursor[Any]) -> SyncCounters:
        inserted = 0
        updated = 0
        for row in gold.rows:
            cursor.execute(
                "SELECT name, instrument_type, currency, country "
                "FROM portfell_market.listings "
                "WHERE isin = %s AND exchange = %s AND code = %s",
                row.key,
            )
            existing = cast(tuple[str | None, str | None, str | None, str | None] | None, cursor.fetchone())
            semantic = (row.name, row.instrument_type, row.currency, row.country)
            if existing is None:
                cursor.execute(
                    "INSERT INTO portfell_market.listings "
                    "(isin, exchange, code, name, instrument_type, currency, country, "
                    "fetched_at_utc, published_at_utc) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (*row.key, *semantic, published_at, published_at),
                )
                inserted += 1
            elif existing != semantic:
                cursor.execute(
                    "UPDATE portfell_market.listings SET name = %s, instrument_type = %s, "
                    "currency = %s, country = %s, fetched_at_utc = %s, published_at_utc = %s "
                    "WHERE isin = %s AND exchange = %s AND code = %s",
                    (*semantic, published_at, published_at, *row.key),
                )
                updated += 1
        return SyncCounters(inserted=inserted, updated=updated)

    return run_sync(
        connection,
        dataset="listings",
        semantic_rows=gold.semantic_rows(),
        mutate=mutate,
        run_id=run_id,
    )


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("published_at_utc must be timezone-aware UTC")

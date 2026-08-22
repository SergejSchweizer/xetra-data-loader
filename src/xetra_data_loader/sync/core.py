"""Transactional PostgreSQL publication state shared by every serving dataset."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import psycopg
from psycopg import Connection, Cursor

type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]
type SemanticRow = Mapping[str, JSONValue]
type Mutator = Callable[[Cursor[Any]], "SyncCounters"]


@dataclass(frozen=True, slots=True)
class SyncCounters:
    """Generic serving-table mutation counters."""

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    retracted: int = 0

    def __post_init__(self) -> None:
        if min(self.inserted, self.updated, self.deleted, self.retracted) < 0:
            raise ValueError("sync counters must be non-negative")

    @property
    def total_mutations(self) -> int:
        return self.inserted + self.updated + self.deleted + self.retracted


@dataclass(frozen=True, slots=True)
class SyncOutcome:
    """One committed synchronization result."""

    run_id: str
    dataset: str
    semantic_fingerprint: str
    row_count: int
    status: str
    counters: SyncCounters

    @property
    def changed(self) -> bool:
        return self.status == "applied"


def connect_postgres(dsn: str | None = None) -> Connection[Any]:
    """Connect using an explicit DSN or the secret-only environment variable."""

    resolved = dsn if dsn is not None else os.getenv("XDL_POSTGRES_DSN")
    if resolved is None or not resolved.strip():
        raise ValueError("XDL_POSTGRES_DSN is required")
    return psycopg.connect(resolved, autocommit=False)


def semantic_fingerprint(rows: Iterable[SemanticRow]) -> tuple[str, int]:
    """Hash semantic rows deterministically, independent of iteration order."""

    canonical_rows = sorted(_canonical_row(row) for row in rows)
    payload = "[" + ",".join(canonical_rows) + "]"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), len(canonical_rows)


def run_sync(
    connection: Connection[Any],
    *,
    dataset: str,
    semantic_rows: Iterable[SemanticRow],
    mutate: Mutator,
    run_id: str | None = None,
    now: Callable[[], datetime] | None = None,
) -> SyncOutcome:
    """Couple serving mutations and sync-state advance in one PostgreSQL transaction."""

    if not dataset.strip():
        raise ValueError("dataset must be non-empty")
    fingerprint, row_count = semantic_fingerprint(semantic_rows)
    resolved_run_id = run_id or str(uuid4())
    clock = now or (lambda: datetime.now(UTC))
    started_at = _require_utc(clock())

    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL TIME ZONE 'UTC'")
        cursor.execute(
            "SELECT semantic_fingerprint, row_count "
            "FROM portfell_loader_sync.sync_state WHERE dataset = %s FOR UPDATE",
            (dataset,),
        )
        raw_state = cursor.fetchone()
        state = cast(tuple[str, int] | None, raw_state)
        is_noop = state is not None and state[0] == fingerprint and state[1] == row_count

        counters = SyncCounters() if is_noop else mutate(cursor)
        if not is_noop:
            cursor.execute(
                "INSERT INTO portfell_loader_sync.sync_state "
                "(dataset, semantic_fingerprint, row_count, synced_at_utc) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (dataset) DO UPDATE SET "
                "semantic_fingerprint = EXCLUDED.semantic_fingerprint, "
                "row_count = EXCLUDED.row_count, "
                "synced_at_utc = EXCLUDED.synced_at_utc",
                (dataset, fingerprint, row_count, started_at),
            )

        finished_at = _require_utc(clock())
        status = "noop" if is_noop else "applied"
        cursor.execute(
            "INSERT INTO portfell_loader_sync.loader_runs "
            "(run_id, dataset, semantic_fingerprint, row_count, inserted_count, "
            "updated_count, deleted_count, retracted_count, started_at_utc, "
            "finished_at_utc, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                resolved_run_id,
                dataset,
                fingerprint,
                row_count,
                counters.inserted,
                counters.updated,
                counters.deleted,
                counters.retracted,
                started_at,
                finished_at,
                status,
            ),
        )

    return SyncOutcome(
        run_id=resolved_run_id,
        dataset=dataset,
        semantic_fingerprint=fingerprint,
        row_count=row_count,
        status=status,
        counters=counters,
    )


def _canonical_row(row: SemanticRow) -> str:
    return json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("sync timestamps must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("sync timestamps must use UTC")
    return value

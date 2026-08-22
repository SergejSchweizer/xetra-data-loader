"""Full confirmed XETRA bootstrap from EODHD through Gold and PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar, cast
from urllib.request import Request, urlopen

from psycopg import Connection

from xetra_data_loader.contracts.corporate_actions import DividendEvent, SplitEvent
from xetra_data_loader.contracts.listings import ListingRecord
from xetra_data_loader.contracts.quotes import QuoteRecord
from xetra_data_loader.eodhd.transport import BinaryResponse, EodhdTransport, JSONValue
from xetra_data_loader.gold.dividends import DividendGoldResult, build_dividend_gold
from xetra_data_loader.gold.listings import ListingGoldResult, build_listing_gold
from xetra_data_loader.gold.quotes import QuoteGoldResult, build_quote_gold
from xetra_data_loader.gold.splits import SplitGoldResult, build_split_gold
from xetra_data_loader.ingestion.dividends import ingest_dividends
from xetra_data_loader.ingestion.listings import ingest_xetra_listings
from xetra_data_loader.ingestion.quotes import ingest_quotes
from xetra_data_loader.ingestion.splits import ingest_splits
from xetra_data_loader.medallion.core import Layer, Manifest, MedallionLayout, canonical_json
from xetra_data_loader.ops.reset import build_reset_plan, execute_reset
from xetra_data_loader.sync import connect_postgres
from xetra_data_loader.sync.core import SyncOutcome
from xetra_data_loader.sync.dividends import sync_dividends
from xetra_data_loader.sync.listings import sync_listings
from xetra_data_loader.sync.quotes import sync_quotes
from xetra_data_loader.sync.splits import sync_splits

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class FetchMetrics:
    """Measured provider work; no request, retry, row, or timing value is guessed."""

    logical_requests: int = 0
    attempts: int = 0
    retries: int = 0
    failures: int = 0
    elapsed_seconds: float = 0.0
    rows: int = 0

    def __add__(self, other: FetchMetrics) -> FetchMetrics:
        return FetchMetrics(
            logical_requests=self.logical_requests + other.logical_requests,
            attempts=self.attempts + other.attempts,
            retries=self.retries + other.retries,
            failures=self.failures + other.failures,
            elapsed_seconds=self.elapsed_seconds + other.elapsed_seconds,
            rows=self.rows + other.rows,
        )

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "logical_requests": self.logical_requests,
            "attempts": self.attempts,
            "retries": self.retries,
            "failures": self.failures,
            "elapsed_seconds": self.elapsed_seconds,
            "rows": self.rows,
        }


@dataclass(frozen=True, slots=True)
class FetchBatch(Generic[T]):
    rows: tuple[T, ...]
    metrics: FetchMetrics


@dataclass(frozen=True, slots=True)
class BootstrapVerification:
    """Independent serving-state checks required before bootstrap is accepted."""

    row_counts: Mapping[str, tuple[int, int]]
    key_differences: Mapping[str, tuple[int, int]]
    date_bounds_match: Mapping[str, bool]
    sync_state_match: Mapping[str, bool]

    @property
    def passed(self) -> bool:
        return (
            all(expected == actual for expected, actual in self.row_counts.values())
            and all(missing == extra == 0 for missing, extra in self.key_differences.values())
            and all(self.date_bounds_match.values())
            and all(self.sync_state_match.values())
        )

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "passed": self.passed,
            "row_counts": {
                name: [expected, actual]
                for name, (expected, actual) in self.row_counts.items()
            },
            "key_differences": {
                name: [missing, extra]
                for name, (missing, extra) in self.key_differences.items()
            },
            "date_bounds_match": dict(self.date_bounds_match),
            "sync_state_match": dict(self.sync_state_match),
        }


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Measured and verified result of one full-universe bootstrap or replay."""

    fetch_metrics: FetchMetrics
    listing_gold: ListingGoldResult
    quote_gold: QuoteGoldResult
    dividend_gold: DividendGoldResult
    split_gold: SplitGoldResult
    sync_outcomes: Mapping[str, SyncOutcome]
    verification: BootstrapVerification

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "status": "PASS" if self.verification.passed else "FAIL",
            "fetch_metrics": self.fetch_metrics.as_dict(),
            "gold_rows": {
                "listings": self.listing_gold.row_count,
                "eod_quotes": self.quote_gold.row_count,
                "dividends": self.dividend_gold.row_count,
                "splits": self.split_gold.row_count,
            },
            "sync_mutations": {
                name: outcome.counters.total_mutations
                for name, outcome in self.sync_outcomes.items()
            },
            "verification": self.verification.as_dict(),
        }


class DestructiveConfirmationRequired(RuntimeError):
    """Raised before any runtime call when bootstrap confirmation is absent."""


class BootstrapVerificationError(RuntimeError):
    """Raised when independent PostgreSQL verification does not match Gold."""


class BootstrapRuntime(Protocol):
    """Provider, persistence, publication, and verification boundary for bootstrap."""

    def reset_owned_state(self) -> None: ...

    def fetch_listings(self) -> FetchBatch[ListingRecord]: ...

    def fetch_quotes(self, listing: ListingRecord) -> FetchBatch[QuoteRecord]: ...

    def fetch_dividends(self, listing: ListingRecord) -> FetchBatch[DividendEvent]: ...

    def fetch_splits(self, listing: ListingRecord) -> FetchBatch[SplitEvent]: ...

    def persist_gold(
        self,
        dataset: str,
        semantic_rows: Sequence[Mapping[str, JSONValue]],
        *,
        row_count: int,
        semantic_fingerprint: str,
    ) -> None: ...

    def publish_listings(self, gold: ListingGoldResult) -> SyncOutcome: ...

    def publish_quotes(self, gold: QuoteGoldResult) -> SyncOutcome: ...

    def publish_dividends(self, gold: DividendGoldResult) -> SyncOutcome: ...

    def publish_splits(self, gold: SplitGoldResult) -> SyncOutcome: ...

    def verify(
        self,
        listing_gold: ListingGoldResult,
        quote_gold: QuoteGoldResult,
        dividend_gold: DividendGoldResult,
        split_gold: SplitGoldResult,
        sync_outcomes: Mapping[str, SyncOutcome],
    ) -> BootstrapVerification: ...

    def close(self) -> None: ...


def run_full_bootstrap(
    runtime: BootstrapRuntime,
    *,
    confirmed: bool,
    reset_owned_state: bool = True,
) -> BootstrapResult:
    """Load every valid XETRA identity and every available history, then verify publication."""

    if not confirmed:
        raise DestructiveConfirmationRequired("--confirm-destructive-reset is required")
    if reset_owned_state:
        runtime.reset_owned_state()

    metrics = FetchMetrics()
    listing_batch = runtime.fetch_listings()
    metrics += listing_batch.metrics
    listing_gold = build_listing_gold(listing_batch.rows)

    quotes: list[QuoteRecord] = []
    dividends: list[DividendEvent] = []
    splits: list[SplitEvent] = []
    for listing in listing_gold.rows:
        quote_batch = runtime.fetch_quotes(listing)
        dividend_batch = runtime.fetch_dividends(listing)
        split_batch = runtime.fetch_splits(listing)
        quotes.extend(quote_batch.rows)
        dividends.extend(dividend_batch.rows)
        splits.extend(split_batch.rows)
        metrics += quote_batch.metrics + dividend_batch.metrics + split_batch.metrics

    quote_gold = build_quote_gold(quotes)
    dividend_gold = build_dividend_gold(dividends)
    split_gold = build_split_gold(splits)

    runtime.persist_gold(
        "listings",
        listing_gold.semantic_rows(),
        row_count=listing_gold.row_count,
        semantic_fingerprint=listing_gold.semantic_fingerprint,
    )
    runtime.persist_gold(
        "eod_quotes",
        quote_gold.semantic_rows(),
        row_count=quote_gold.row_count,
        semantic_fingerprint=quote_gold.semantic_fingerprint,
    )
    runtime.persist_gold(
        "dividends",
        dividend_gold.semantic_rows(),
        row_count=dividend_gold.row_count,
        semantic_fingerprint=dividend_gold.semantic_fingerprint,
    )
    runtime.persist_gold(
        "splits",
        split_gold.semantic_rows(),
        row_count=split_gold.row_count,
        semantic_fingerprint=split_gold.semantic_fingerprint,
    )

    sync_outcomes = {
        "listings": runtime.publish_listings(listing_gold),
        "eod_quotes": runtime.publish_quotes(quote_gold),
        "dividends": runtime.publish_dividends(dividend_gold),
        "splits": runtime.publish_splits(split_gold),
    }
    verification = runtime.verify(
        listing_gold,
        quote_gold,
        dividend_gold,
        split_gold,
        sync_outcomes,
    )
    if not verification.passed:
        raise BootstrapVerificationError("PostgreSQL serving state does not match validated Gold")

    return BootstrapResult(
        fetch_metrics=metrics,
        listing_gold=listing_gold,
        quote_gold=quote_gold,
        dividend_gold=dividend_gold,
        split_gold=split_gold,
        sync_outcomes=sync_outcomes,
        verification=verification,
    )


class _AttemptCounter:
    def __init__(self) -> None:
        self.attempts = 0

    def open(self, request: Request, timeout: float) -> BinaryResponse:
        self.attempts += 1
        return cast(BinaryResponse, urlopen(request, timeout=timeout))


class _MeasuredTransport:
    def __init__(self, token: str | None = None) -> None:
        self._opener = _AttemptCounter()
        self._transport = EodhdTransport(token=token, opener=self._opener.open)
        self.logical_requests = 0

    @property
    def attempts(self) -> int:
        return self._opener.attempts

    def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> JSONValue:
        self.logical_requests += 1
        return self._transport.get_json(path, params)


class PostgresEodhdBootstrapRuntime:
    """Concrete EODHD + medallion + PostgreSQL implementation for production bootstrap."""

    def __init__(
        self,
        *,
        connection: Connection[Any],
        transport: _MeasuredTransport,
        medallion_root: Path,
        repository_root: Path,
    ) -> None:
        self._connection = connection
        self._transport = transport
        self._layout = MedallionLayout(medallion_root.resolve())
        self._repository_root = repository_root.resolve()
        self._bronze_series: dict[str, list[dict[str, JSONValue]]] = {
            "eod_quotes": [],
            "dividends": [],
            "splits": [],
        }
        self._silver_series: dict[str, list[dict[str, JSONValue]]] = {
            "eod_quotes": [],
            "dividends": [],
            "splits": [],
        }

    @classmethod
    def from_environment(cls) -> PostgresEodhdBootstrapRuntime:
        root = os.getenv("XDL_MEDALLION_ROOT")
        if root is None or not root.strip():
            raise ValueError("XDL_MEDALLION_ROOT is required")
        return cls(
            connection=connect_postgres(),
            transport=_MeasuredTransport(),
            medallion_root=Path(root),
            repository_root=Path.cwd(),
        )

    def reset_owned_state(self) -> None:
        execute_reset(
            build_reset_plan(self._layout.root),
            confirmed=True,
            dry_run=False,
            connection=self._connection,
        )
        self._initialize_database()
        self._bronze_series = {"eod_quotes": [], "dividends": [], "splits": []}
        self._silver_series = {"eod_quotes": [], "dividends": [], "splits": []}

    def fetch_listings(self) -> FetchBatch[ListingRecord]:
        before = self._measurement_start()
        result = ingest_xetra_listings(self._transport)
        metrics = self._measurement_finish(before, len(result.silver_records))
        raw = cast(JSONValue, json.loads(result.bronze_payload))
        self._write_layer(Layer.BRONZE, "listings", raw)
        silver = [record.semantic_dict() for record in result.silver_records]
        self._write_layer(Layer.SILVER, "listings", cast(JSONValue, silver))
        return FetchBatch(result.silver_records, metrics)

    def fetch_quotes(self, listing: ListingRecord) -> FetchBatch[QuoteRecord]:
        before = self._measurement_start()
        result = ingest_quotes(self._transport, listing)
        metrics = self._measurement_finish(before, len(result.silver_records))
        self._record_series_bronze("eod_quotes", listing, result.bronze_payload)
        self._silver_series["eod_quotes"].extend(
            record.semantic_dict() for record in result.silver_records
        )
        self._flush_series("eod_quotes")
        return FetchBatch(result.silver_records, metrics)

    def fetch_dividends(self, listing: ListingRecord) -> FetchBatch[DividendEvent]:
        before = self._measurement_start()
        result = ingest_dividends(self._transport, listing)
        metrics = self._measurement_finish(before, len(result.silver_records))
        self._record_series_bronze("dividends", listing, result.bronze_payload)
        self._silver_series["dividends"].extend(
            _dividend_silver(event) for event in result.silver_records
        )
        self._flush_series("dividends")
        return FetchBatch(result.silver_records, metrics)

    def fetch_splits(self, listing: ListingRecord) -> FetchBatch[SplitEvent]:
        before = self._measurement_start()
        result = ingest_splits(self._transport, listing)
        metrics = self._measurement_finish(before, len(result.silver_records))
        self._record_series_bronze("splits", listing, result.bronze_payload)
        self._silver_series["splits"].extend(
            _split_silver(event) for event in result.silver_records
        )
        self._flush_series("splits")
        return FetchBatch(result.silver_records, metrics)

    def persist_gold(
        self,
        dataset: str,
        semantic_rows: Sequence[Mapping[str, JSONValue]],
        *,
        row_count: int,
        semantic_fingerprint: str,
    ) -> None:
        rows = [dict(row) for row in semantic_rows]
        self._write_layer(Layer.GOLD, dataset, cast(JSONValue, rows))
        manifest = Manifest(
            dataset=dataset,
            layer=Layer.GOLD,
            semantic_metadata={
                "row_count": row_count,
                "builder_semantic_fingerprint": semantic_fingerprint,
            },
            run_metadata={},
        )
        path = self._layout.manifest_path(Layer.GOLD, dataset)
        path.write_text(manifest.to_json() + "\n", encoding="utf-8")

    def publish_listings(self, gold: ListingGoldResult) -> SyncOutcome:
        return sync_listings(self._connection, gold)

    def publish_quotes(self, gold: QuoteGoldResult) -> SyncOutcome:
        return sync_quotes(self._connection, gold)

    def publish_dividends(self, gold: DividendGoldResult) -> SyncOutcome:
        return sync_dividends(self._connection, gold)

    def publish_splits(self, gold: SplitGoldResult) -> SyncOutcome:
        return sync_splits(self._connection, gold)

    def verify(
        self,
        listing_gold: ListingGoldResult,
        quote_gold: QuoteGoldResult,
        dividend_gold: DividendGoldResult,
        split_gold: SplitGoldResult,
        sync_outcomes: Mapping[str, SyncOutcome],
    ) -> BootstrapVerification:
        expected_keys = {
            "listings": {tuple(row.key) for row in listing_gold.rows},
            "eod_quotes": {tuple(str(value) for value in row.key) for row in quote_gold.rows},
            "dividends": {tuple(row.key) for row in dividend_gold.rows},
            "splits": {tuple(row.key) for row in split_gold.rows},
        }
        actual_keys = {
            "listings": self._keys("listings", "isin, exchange, code"),
            "eod_quotes": self._keys(
                "eod_quotes", "isin, exchange, code, trade_date::text"
            ),
            "dividends": self._keys("dividends", "isin, exchange, code, event_key"),
            "splits": self._keys("splits", "isin, exchange, code, event_key"),
        }
        row_counts = {
            "listings": (listing_gold.row_count, self._count("listings")),
            "eod_quotes": (quote_gold.row_count, self._count("eod_quotes")),
            "dividends": (dividend_gold.row_count, self._count("dividends")),
            "splits": (split_gold.row_count, self._count("splits")),
        }
        key_differences = {
            name: (len(expected_keys[name] - actual_keys[name]), len(actual_keys[name] - expected_keys[name]))
            for name in expected_keys
        }
        date_bounds_match = {
            "listings": True,
            "eod_quotes": self._date_bounds("eod_quotes", "trade_date")
            == _bounds(record.trade_date for record in quote_gold.rows),
            "dividends": self._date_bounds("dividends", "event_date")
            == _bounds(record.event_date for record in dividend_gold.rows),
            "splits": self._date_bounds("splits", "event_date")
            == _bounds(record.event_date for record in split_gold.rows),
        }
        sync_state_match = {
            name: self._sync_state_matches(name, outcome)
            for name, outcome in sync_outcomes.items()
        }
        return BootstrapVerification(
            row_counts=row_counts,
            key_differences=key_differences,
            date_bounds_match=date_bounds_match,
            sync_state_match=sync_state_match,
        )

    def close(self) -> None:
        self._connection.close()

    def _initialize_database(self) -> None:
        for relative in (
            "sql/schema/001_portfell_market.sql",
            "sql/schema/002_roles.sql",
            "sql/sync/001_portfell_loader_sync.sql",
        ):
            sql = (self._repository_root / relative).read_text(encoding="utf-8")
            self._connection.execute(sql)

    def _measurement_start(self) -> tuple[int, int, float]:
        return self._transport.logical_requests, self._transport.attempts, time.perf_counter()

    def _measurement_finish(
        self,
        before: tuple[int, int, float],
        row_count: int,
    ) -> FetchMetrics:
        calls_before, attempts_before, started = before
        calls = self._transport.logical_requests - calls_before
        attempts = self._transport.attempts - attempts_before
        return FetchMetrics(
            logical_requests=calls,
            attempts=attempts,
            retries=max(0, attempts - calls),
            failures=0,
            elapsed_seconds=time.perf_counter() - started,
            rows=row_count,
        )

    def _record_series_bronze(
        self,
        dataset: str,
        listing: ListingRecord,
        bronze_payload: str,
    ) -> None:
        payload = cast(JSONValue, json.loads(bronze_payload))
        self._bronze_series[dataset].append(
            {
                "isin": listing.isin,
                "exchange": listing.exchange,
                "code": listing.code,
                "payload": payload,
            }
        )

    def _flush_series(self, dataset: str) -> None:
        bronze = sorted(self._bronze_series[dataset], key=canonical_json)
        silver = sorted(self._silver_series[dataset], key=canonical_json)
        self._write_layer(Layer.BRONZE, dataset, cast(JSONValue, bronze))
        self._write_layer(Layer.SILVER, dataset, cast(JSONValue, silver))

    def _write_layer(self, layer: Layer, dataset: str, payload: JSONValue) -> None:
        directory = self._layout.dataset_path(layer, dataset)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "data.json").write_text(canonical_json(payload) + "\n", encoding="utf-8")

    def _count(self, table: str) -> int:
        row = self._connection.execute(
            f'SELECT count(*) FROM portfell_market."{table}"'
        ).fetchone()
        if row is None:
            raise RuntimeError(f"missing count result for {table}")
        return int(row[0])

    def _keys(self, table: str, columns: str) -> set[tuple[str, ...]]:
        rows = self._connection.execute(
            f'SELECT {columns} FROM portfell_market."{table}"'
        ).fetchall()
        return {tuple(str(value) for value in row) for row in rows}

    def _date_bounds(self, table: str, column: str) -> tuple[date | None, date | None]:
        row = self._connection.execute(
            f'SELECT min("{column}"), max("{column}") FROM portfell_market."{table}"'
        ).fetchone()
        if row is None:
            raise RuntimeError(f"missing date-bound result for {table}")
        return cast(tuple[date | None, date | None], row)

    def _sync_state_matches(self, dataset: str, outcome: SyncOutcome) -> bool:
        row = self._connection.execute(
            "SELECT semantic_fingerprint, row_count "
            "FROM portfell_loader_sync.sync_state WHERE dataset = %s",
            (dataset,),
        ).fetchone()
        if row is None:
            return False
        return str(row[0]) == outcome.semantic_fingerprint and int(row[1]) == outcome.row_count


def _dividend_silver(event: DividendEvent) -> dict[str, JSONValue]:
    row = event.business_fields()
    row["event_key"] = event.event_key
    row["status"] = event.status.value
    return row


def _split_silver(event: SplitEvent) -> dict[str, JSONValue]:
    row = event.business_fields()
    row["event_key"] = event.event_key
    row["status"] = event.status.value
    return row


def _bounds(values: Sequence[date] | Any) -> tuple[date | None, date | None]:
    materialized = tuple(values)
    if not materialized:
        return None, None
    return min(materialized), max(materialized)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xdl-bootstrap")
    parser.add_argument("--confirm-destructive-reset", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the production bootstrap only after literal destructive confirmation."""

    args = _parser().parse_args(argv)
    if not args.confirm_destructive_reset:
        print(canonical_json({"status": "BLOCKED", "reason": "confirmation-required"}))
        return 2

    runtime = PostgresEodhdBootstrapRuntime.from_environment()
    try:
        result = run_full_bootstrap(runtime, confirmed=True, reset_owned_state=True)
    finally:
        runtime.close()
    print(canonical_json(result.as_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

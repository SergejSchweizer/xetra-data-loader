"""Real-target PostgreSQL verification and production acceptance reporting."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from psycopg import Connection, Cursor, Error

from xetra_data_loader.config import resolve_medallion_root
from xetra_data_loader.medallion.core import JSONValue, Layer, MedallionLayout, canonical_json
from xetra_data_loader.ops.bootstrap import (
    BootstrapResult,
    PostgresEodhdBootstrapRuntime,
    run_full_bootstrap,
)
from xetra_data_loader.sync import connect_postgres
from xetra_data_loader.sync.core import SyncOutcome

EXPECTED_HOST = "10.10.1.3"
EXPECTED_PORT = 54321
DATASETS = ("listings", "eod_quotes", "dividends", "splits")

_EXPECTED_TIMESTAMP_COLUMNS = {
    ("portfell_market", "listings", "fetched_at_utc"),
    ("portfell_market", "listings", "published_at_utc"),
    ("portfell_market", "eod_quotes", "timestamp_eod"),
    ("portfell_market", "eod_quotes", "fetched_at_utc"),
    ("portfell_market", "eod_quotes", "published_at_utc"),
    ("portfell_market", "dividends", "fetched_at_utc"),
    ("portfell_market", "dividends", "published_at_utc"),
    ("portfell_market", "splits", "fetched_at_utc"),
    ("portfell_market", "splits", "published_at_utc"),
    ("portfell_loader_sync", "sync_state", "synced_at_utc"),
    ("portfell_loader_sync", "loader_runs", "started_at_utc"),
    ("portfell_loader_sync", "loader_runs", "finished_at_utc"),
}


@dataclass(frozen=True, slots=True)
class GoldDatasetSnapshot:
    """Normalized source/Gold state reconstructed from the medallion sidecar."""

    dataset: str
    source_count: int
    rows: tuple[dict[str, JSONValue], ...]
    manifest_fingerprint: str
    computed_fingerprint: str

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def fingerprint_valid(self) -> bool:
        return self.manifest_fingerprint == self.computed_fingerprint


@dataclass(frozen=True, slots=True)
class DatasetVerification:
    """Exact comparison of one validated Gold dataset with PostgreSQL."""

    source_count: int
    gold_count: int
    postgres_count: int
    missing_keys: int
    extra_keys: int
    duplicate_keys: int
    gold_fingerprint: str
    postgres_fingerprint: str
    gold_manifest_valid: bool
    gold_min_date: str | None
    gold_max_date: str | None
    postgres_min_date: str | None
    postgres_max_date: str | None

    @property
    def passed(self) -> bool:
        return (
            self.gold_count == self.postgres_count
            and self.missing_keys == 0
            and self.extra_keys == 0
            and self.duplicate_keys == 0
            and self.gold_manifest_valid
            and self.gold_fingerprint == self.postgres_fingerprint
            and self.gold_min_date == self.postgres_min_date
            and self.gold_max_date == self.postgres_max_date
        )

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "source_count": self.source_count,
            "gold_count": self.gold_count,
            "postgres_count": self.postgres_count,
            "missing_keys": self.missing_keys,
            "extra_keys": self.extra_keys,
            "duplicate_keys": self.duplicate_keys,
            "gold_fingerprint": self.gold_fingerprint,
            "postgres_fingerprint": self.postgres_fingerprint,
            "gold_manifest_valid": self.gold_manifest_valid,
            "gold_min_date": self.gold_min_date,
            "gold_max_date": self.gold_max_date,
            "postgres_min_date": self.postgres_min_date,
            "postgres_max_date": self.postgres_max_date,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class TimestampVerification:
    """Timestamp precision and session-timezone acceptance state."""

    session_timezone: str
    checked_columns: tuple[str, ...]
    invalid_columns: tuple[str, ...]
    missing_columns: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return (
            self.session_timezone == "UTC"
            and not self.invalid_columns
            and not self.missing_columns
        )

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "session_timezone": self.session_timezone,
            "required_type": "TIMESTAMPTZ(6)",
            "checked_columns": list(self.checked_columns),
            "invalid_columns": list(self.invalid_columns),
            "missing_columns": list(self.missing_columns),
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class RoleVerification:
    """Actual permission probes performed under SET LOCAL ROLE portfell_app."""

    select_tables: Mapping[str, bool]
    insert_denied: bool
    update_denied: bool
    delete_denied: bool
    ddl_denied: bool
    sync_schema_select_denied: bool

    @property
    def passed(self) -> bool:
        return (
            all(self.select_tables.values())
            and self.insert_denied
            and self.update_denied
            and self.delete_denied
            and self.ddl_denied
            and self.sync_schema_select_denied
        )

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "role": "portfell_app",
            "select_tables": dict(self.select_tables),
            "insert_denied": self.insert_denied,
            "update_denied": self.update_denied,
            "delete_denied": self.delete_denied,
            "ddl_denied": self.ddl_denied,
            "sync_schema_select_denied": self.sync_schema_select_denied,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class ProductionAcceptanceReport:
    """Sanitized evidence required before XDL-PR033 can be merged."""

    target_host: str
    target_port: int
    resolved_addresses: tuple[str, ...]
    target_matches: bool
    initial_run_ids: Mapping[str, str]
    committed_runs: Mapping[str, bool]
    datasets: Mapping[str, DatasetVerification]
    orphan_counts: Mapping[str, int]
    timestamps: TimestampVerification
    role: RoleVerification
    replay_mutations: Mapping[str, int]

    @property
    def passed(self) -> bool:
        return (
            self.target_matches
            and all(self.committed_runs.values())
            and all(dataset.passed for dataset in self.datasets.values())
            and all(count == 0 for count in self.orphan_counts.values())
            and self.timestamps.passed
            and self.role.passed
            and all(count == 0 for count in self.replay_mutations.values())
        )

    def as_dict(self) -> dict[str, JSONValue]:
        return {
            "status": "PASS" if self.passed else "FAIL",
            "target": {
                "host": self.target_host,
                "port": self.target_port,
                "resolved_addresses": list(self.resolved_addresses),
                "matches_required_target": self.target_matches,
            },
            "initial_run_ids": dict(self.initial_run_ids),
            "committed_runs": dict(self.committed_runs),
            "datasets": {
                name: verification.as_dict()
                for name, verification in sorted(self.datasets.items())
            },
            "orphan_counts": dict(self.orphan_counts),
            "timestamps": self.timestamps.as_dict(),
            "role": self.role.as_dict(),
            "unchanged_replay_mutations": dict(self.replay_mutations),
        }


class ProductionVerificationError(RuntimeError):
    """Raised whenever the mandatory production acceptance contract does not pass."""


def execute_production_full_sync_and_verify(
    *,
    medallion_root: Path,
    output_path: Path,
) -> ProductionAcceptanceReport:
    """Destructively bootstrap the real target, replay unchanged state, and verify independently."""

    preflight = connect_postgres()
    try:
        preflight.autocommit = True
        _, _, _, target_matches = _verify_target(preflight)
        if not target_matches:
            raise ProductionVerificationError(
                f"XDL_POSTGRES_DSN must resolve exactly to {EXPECTED_HOST}:{EXPECTED_PORT}"
            )
    finally:
        preflight.close()

    initial_runtime = PostgresEodhdBootstrapRuntime.from_environment()
    try:
        initial = run_full_bootstrap(initial_runtime, confirmed=True, reset_owned_state=True)
        # The bootstrap schema initializer runs after the reset transaction. Explicitly commit
        # its outer transaction so a fresh verification connection can prove durable state.
        initial_runtime._connection.commit()
    finally:
        initial_runtime.close()

    replay_runtime = PostgresEodhdBootstrapRuntime.from_environment()
    try:
        replay = run_full_bootstrap(replay_runtime, confirmed=True, reset_owned_state=False)
    finally:
        replay_runtime.close()

    connection = connect_postgres()
    try:
        connection.autocommit = True
        connection.execute("SET TIME ZONE 'UTC'")
        report = verify_postgres_sync(
            connection,
            medallion_root=medallion_root,
            initial=initial,
            replay=replay,
        )
    finally:
        connection.close()

    write_production_report(report, output_path)
    if not report.passed:
        raise ProductionVerificationError("production PostgreSQL acceptance report is not PASS")
    return report


def verify_postgres_sync(
    connection: Connection[Any],
    *,
    medallion_root: Path,
    initial: BootstrapResult,
    replay: BootstrapResult,
) -> ProductionAcceptanceReport:
    """Read PostgreSQL independently and compare it with validated Gold state."""

    host, port, addresses, target_matches = _verify_target(connection)
    gold = load_gold_snapshots(medallion_root)
    postgres_rows = {dataset: _fetch_semantic_rows(connection, dataset) for dataset in DATASETS}

    datasets: dict[str, DatasetVerification] = {}
    for dataset in DATASETS:
        gold_snapshot = gold[dataset]
        db_rows = postgres_rows[dataset]
        gold_keys = {_business_key(dataset, row) for row in gold_snapshot.rows}
        db_keys = {_business_key(dataset, row) for row in db_rows}
        gold_min, gold_max = _date_bounds(dataset, gold_snapshot.rows)
        db_min, db_max = _date_bounds(dataset, db_rows)
        datasets[dataset] = DatasetVerification(
            source_count=gold_snapshot.source_count,
            gold_count=gold_snapshot.row_count,
            postgres_count=len(db_rows),
            missing_keys=len(gold_keys - db_keys),
            extra_keys=len(db_keys - gold_keys),
            duplicate_keys=_duplicate_key_count(connection, dataset),
            gold_fingerprint=gold_snapshot.computed_fingerprint,
            postgres_fingerprint=semantic_fingerprint(dataset, db_rows),
            gold_manifest_valid=gold_snapshot.fingerprint_valid,
            gold_min_date=gold_min,
            gold_max_date=gold_max,
            postgres_min_date=db_min,
            postgres_max_date=db_max,
        )

    initial_outcomes = initial.sync_outcomes
    committed_runs = {
        dataset: _run_is_committed(connection, outcome)
        for dataset, outcome in initial_outcomes.items()
    }
    replay_mutations = {
        dataset: outcome.counters.total_mutations
        for dataset, outcome in replay.sync_outcomes.items()
    }
    return ProductionAcceptanceReport(
        target_host=host,
        target_port=port,
        resolved_addresses=addresses,
        target_matches=target_matches,
        initial_run_ids={dataset: outcome.run_id for dataset, outcome in initial_outcomes.items()},
        committed_runs=committed_runs,
        datasets=datasets,
        orphan_counts=_orphan_counts(connection),
        timestamps=_verify_timestamps(connection),
        role=_verify_app_role(connection),
        replay_mutations=replay_mutations,
    )


def load_gold_snapshots(root: Path) -> dict[str, GoldDatasetSnapshot]:
    """Load normalized Silver counts and validated Gold fingerprints from disk."""

    layout = MedallionLayout(root.resolve())
    result: dict[str, GoldDatasetSnapshot] = {}
    for dataset in DATASETS:
        source_rows = _read_json_rows(layout.dataset_path(Layer.SILVER, dataset) / "data.json")
        gold_rows = _read_json_rows(layout.dataset_path(Layer.GOLD, dataset) / "data.json")
        manifest_path = layout.manifest_path(Layer.GOLD, dataset)
        manifest = cast(dict[str, JSONValue], json.loads(manifest_path.read_text(encoding="utf-8")))
        semantic_metadata = manifest.get("semantic_metadata")
        if not isinstance(semantic_metadata, dict):
            raise ValueError(f"Gold manifest for {dataset} has no semantic_metadata")
        manifest_fingerprint = semantic_metadata.get("builder_semantic_fingerprint")
        if not isinstance(manifest_fingerprint, str) or len(manifest_fingerprint) != 64:
            raise ValueError(f"Gold manifest for {dataset} has no builder fingerprint")
        ordered = tuple(sorted(gold_rows, key=lambda row: _business_key(dataset, row)))
        result[dataset] = GoldDatasetSnapshot(
            dataset=dataset,
            source_count=len(source_rows),
            rows=ordered,
            manifest_fingerprint=manifest_fingerprint,
            computed_fingerprint=semantic_fingerprint(dataset, ordered),
        )
    return result


def semantic_fingerprint(
    dataset: str,
    rows: Sequence[Mapping[str, JSONValue]],
) -> str:
    """Recompute the exact Gold-builder semantic fingerprint for serving rows."""

    ordered = [dict(row) for row in sorted(rows, key=lambda row: _business_key(dataset, row))]
    payload: JSONValue
    if dataset in {"dividends", "splits"}:
        payload = {"rows": ordered, "retracted_keys": []}
    else:
        payload = ordered
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def write_production_report(report: ProductionAcceptanceReport, path: Path) -> Path:
    """Write sanitized JSON evidence; credentials and raw provider payloads are never included."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(report.as_dict()) + "\n", encoding="utf-8")
    return path


def _verify_target(connection: Connection[Any]) -> tuple[str, int, tuple[str, ...], bool]:
    host = str(connection.info.host)
    port = int(connection.info.port)
    try:
        addresses = tuple(
            sorted({entry[4][0] for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        )
    except OSError:
        addresses = ()
    matches = port == EXPECTED_PORT and addresses == (EXPECTED_HOST,)
    return host, port, addresses, matches


def _read_json_rows(path: Path) -> list[dict[str, JSONValue]]:
    decoded = cast(JSONValue, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(decoded, list):
        raise ValueError(f"expected JSON array at {path}")
    rows: list[dict[str, JSONValue]] = []
    for item in decoded:
        if not isinstance(item, dict):
            raise ValueError(f"expected JSON object rows at {path}")
        rows.append(item)
    return rows


def _fetch_semantic_rows(
    connection: Connection[Any],
    dataset: str,
) -> tuple[dict[str, JSONValue], ...]:
    queries = {
        "listings": (
            "SELECT isin, exchange, code, name, instrument_type, currency, country "
            "FROM portfell_market.listings ORDER BY isin, exchange, code"
        ),
        "eod_quotes": (
            "SELECT isin, exchange, code, trade_date, timestamp_eod, open, high, low, close, "
            "adjusted_close, volume FROM portfell_market.eod_quotes "
            "ORDER BY isin, exchange, code, trade_date"
        ),
        "dividends": (
            "SELECT isin, exchange, code, event_key, event_date, declaration_date, record_date, "
            "payment_date, value, currency, period FROM portfell_market.dividends "
            "ORDER BY isin, exchange, code, event_key"
        ),
        "splits": (
            "SELECT isin, exchange, code, event_key, event_date, split_ratio, split_factor "
            "FROM portfell_market.splits ORDER BY isin, exchange, code, event_key"
        ),
    }
    if dataset not in queries:
        raise ValueError(f"unsupported dataset: {dataset}")
    rows = connection.execute(queries[dataset]).fetchall()
    if dataset == "listings":
        return tuple(_listing_row(row) for row in rows)
    if dataset == "eod_quotes":
        return tuple(_quote_row(row) for row in rows)
    if dataset == "dividends":
        return tuple(_dividend_row(row) for row in rows)
    return tuple(_split_row(row) for row in rows)


def _listing_row(row: Sequence[object]) -> dict[str, JSONValue]:
    return {
        "isin": str(row[0]),
        "exchange": str(row[1]),
        "code": str(row[2]),
        "name": _optional_text(row[3]),
        "instrument_type": _optional_text(row[4]),
        "currency": _optional_text(row[5]),
        "country": _optional_text(row[6]),
    }


def _quote_row(row: Sequence[object]) -> dict[str, JSONValue]:
    trade_date = cast(date, row[3])
    timestamp = cast(datetime, row[4])
    return {
        "isin": str(row[0]),
        "exchange": str(row[1]),
        "code": str(row[2]),
        "trade_date": trade_date.isoformat(),
        "timestamp_eod": timestamp.isoformat(),
        "open": _decimal_text(row[5]),
        "high": _decimal_text(row[6]),
        "low": _decimal_text(row[7]),
        "close": _decimal_text(row[8]),
        "adjusted_close": _decimal_text(row[9]),
        "volume": None if row[10] is None else int(cast(int, row[10])),
    }


def _dividend_row(row: Sequence[object]) -> dict[str, JSONValue]:
    return {
        "isin": str(row[0]),
        "exchange": str(row[1]),
        "code": str(row[2]),
        "event_key": str(row[3]),
        "event_date": cast(date, row[4]).isoformat(),
        "declaration_date": _date_text(row[5]),
        "record_date": _date_text(row[6]),
        "payment_date": _date_text(row[7]),
        "value": _decimal_text(row[8]),
        "currency": _optional_text(row[9]),
        "period": _optional_text(row[10]),
    }


def _split_row(row: Sequence[object]) -> dict[str, JSONValue]:
    return {
        "isin": str(row[0]),
        "exchange": str(row[1]),
        "code": str(row[2]),
        "event_key": str(row[3]),
        "event_date": cast(date, row[4]).isoformat(),
        "split_ratio": str(row[5]),
        "split_factor": _decimal_text(row[6]),
    }


def _business_key(dataset: str, row: Mapping[str, JSONValue]) -> tuple[str, ...]:
    fields = {
        "listings": ("isin", "exchange", "code"),
        "eod_quotes": ("isin", "exchange", "code", "trade_date"),
        "dividends": ("isin", "exchange", "code", "event_key"),
        "splits": ("isin", "exchange", "code", "event_key"),
    }
    if dataset not in fields:
        raise ValueError(f"unsupported dataset: {dataset}")
    values: list[str] = []
    for field in fields[dataset]:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{dataset} row has invalid business-key field {field}")
        values.append(value)
    return tuple(values)


def _date_bounds(
    dataset: str,
    rows: Sequence[Mapping[str, JSONValue]],
) -> tuple[str | None, str | None]:
    field = {
        "eod_quotes": "trade_date",
        "dividends": "event_date",
        "splits": "event_date",
    }.get(dataset)
    if field is None or not rows:
        return None, None
    values = [row.get(field) for row in rows]
    if not all(isinstance(value, str) for value in values):
        raise ValueError(f"{dataset} contains invalid date values")
    typed = cast(list[str], values)
    return min(typed), max(typed)


def _duplicate_key_count(connection: Connection[Any], dataset: str) -> int:
    keys = {
        "listings": "isin, exchange, code",
        "eod_quotes": "isin, exchange, code, trade_date",
        "dividends": "isin, exchange, code, event_key",
        "splits": "isin, exchange, code, event_key",
    }
    columns = keys[dataset]
    query = (
        f'SELECT COALESCE(sum(n - 1), 0) FROM ('
        f'SELECT count(*) AS n FROM portfell_market."{dataset}" '
        f'GROUP BY {columns} HAVING count(*) > 1) duplicates'
    )
    row = connection.execute(query).fetchone()
    if row is None:
        raise RuntimeError(f"missing duplicate count for {dataset}")
    return int(row[0])


def _orphan_counts(connection: Connection[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for dataset in ("eod_quotes", "dividends", "splits"):
        query = (
            f'SELECT count(*) FROM portfell_market."{dataset}" child '
            "LEFT JOIN portfell_market.listings parent "
            "ON parent.isin = child.isin AND parent.exchange = child.exchange "
            "AND parent.code = child.code WHERE parent.isin IS NULL"
        )
        row = connection.execute(query).fetchone()
        if row is None:
            raise RuntimeError(f"missing orphan count for {dataset}")
        result[dataset] = int(row[0])
    return result


def _run_is_committed(connection: Connection[Any], outcome: SyncOutcome) -> bool:
    row = connection.execute(
        "SELECT semantic_fingerprint, row_count, status FROM portfell_loader_sync.loader_runs "
        "WHERE run_id = %s AND dataset = %s",
        (outcome.run_id, outcome.dataset),
    ).fetchone()
    if row is None:
        return False
    return (
        str(row[0]) == outcome.semantic_fingerprint
        and int(row[1]) == outcome.row_count
        and str(row[2]) in {"applied", "noop"}
    )


def _verify_timestamps(connection: Connection[Any]) -> TimestampVerification:
    timezone_row = connection.execute("SHOW TIME ZONE").fetchone()
    timezone = "" if timezone_row is None else str(timezone_row[0])
    rows = connection.execute(
        "SELECT table_schema, table_name, column_name, data_type, datetime_precision "
        "FROM information_schema.columns "
        "WHERE table_schema IN ('portfell_market', 'portfell_loader_sync') "
        "AND data_type LIKE 'timestamp%' ORDER BY table_schema, table_name, column_name"
    ).fetchall()
    seen: set[tuple[str, str, str]] = set()
    invalid: list[str] = []
    checked: list[str] = []
    for row in rows:
        key = (str(row[0]), str(row[1]), str(row[2]))
        seen.add(key)
        label = ".".join(key)
        checked.append(label)
        if str(row[3]) != "timestamp with time zone" or int(row[4]) != 6:
            invalid.append(label)
    missing = sorted(".".join(key) for key in _EXPECTED_TIMESTAMP_COLUMNS - seen)
    return TimestampVerification(
        session_timezone=timezone,
        checked_columns=tuple(checked),
        invalid_columns=tuple(sorted(invalid)),
        missing_columns=tuple(missing),
    )


def _verify_app_role(connection: Connection[Any]) -> RoleVerification:
    select_tables: dict[str, bool] = {dataset: False for dataset in DATASETS}
    insert_denied = False
    update_denied = False
    delete_denied = False
    ddl_denied = False
    sync_denied = False
    cursor = connection.cursor()
    cursor.execute("BEGIN")
    try:
        cursor.execute("SET LOCAL ROLE portfell_app")
        select_tables = {
            dataset: _statement_succeeds(
                cursor,
                f'SELECT 1 FROM portfell_market."{dataset}" LIMIT 0',
                f"select_{dataset}",
            )
            for dataset in DATASETS
        }
        insert_denied = _statement_denied(
            cursor,
            "INSERT INTO portfell_market.listings "
            "(isin, exchange, code, fetched_at_utc, published_at_utc) "
            "SELECT isin, exchange, code, fetched_at_utc, published_at_utc "
            "FROM portfell_market.listings WHERE false",
            "insert_probe",
        )
        update_denied = _statement_denied(
            cursor,
            "UPDATE portfell_market.listings SET code = code WHERE false",
            "update_probe",
        )
        delete_denied = _statement_denied(
            cursor,
            "DELETE FROM portfell_market.listings WHERE false",
            "delete_probe",
        )
        ddl_denied = _statement_denied(
            cursor,
            "CREATE TABLE portfell_market.__xdl_privilege_probe (id integer)",
            "ddl_probe",
        )
        sync_denied = _statement_denied(
            cursor,
            "SELECT 1 FROM portfell_loader_sync.sync_state LIMIT 0",
            "sync_probe",
        )
    except Error:
        pass
    finally:
        cursor.execute("ROLLBACK")
        cursor.close()
    return RoleVerification(
        select_tables=select_tables,
        insert_denied=insert_denied,
        update_denied=update_denied,
        delete_denied=delete_denied,
        ddl_denied=ddl_denied,
        sync_schema_select_denied=sync_denied,
    )


def _statement_succeeds(cursor: Cursor[Any], sql: str, savepoint: str) -> bool:
    cursor.execute(f"SAVEPOINT {savepoint}")
    try:
        cursor.execute(sql)
    except Error:
        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
        return False
    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
    return True


def _statement_denied(cursor: Cursor[Any], sql: str, savepoint: str) -> bool:
    return not _statement_succeeds(cursor, sql, savepoint)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _decimal_text(value: object) -> str | None:
    if value is None:
        return None
    return str(cast(Decimal, value))


def _date_text(value: object) -> str | None:
    if value is None:
        return None
    return cast(date, value).isoformat()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xdl-verify-production-sync")
    parser.add_argument("--execute-full-sync", action="store_true")
    parser.add_argument("--confirm-destructive-reset", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/acceptance/postgres-full-sync.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the mandatory real-target gate only with both explicit execution confirmations."""

    args = _parser().parse_args(argv)
    if not args.execute_full_sync or not args.confirm_destructive_reset:
        print(
            canonical_json(
                {
                    "status": "BLOCKED",
                    "reason": "--execute-full-sync and --confirm-destructive-reset are required",
                    "target": {"host": EXPECTED_HOST, "port": EXPECTED_PORT},
                }
            )
        )
        return 2

    medallion_root_value = resolve_medallion_root()
    report = execute_production_full_sync_and_verify(
        medallion_root=Path(medallion_root_value),
        output_path=args.output,
    )
    print(canonical_json(report.as_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

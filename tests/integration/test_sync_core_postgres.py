import os
import subprocess
from pathlib import Path

import pytest
from psycopg import Cursor

from xetra_loader.sync import SyncCounters, connect_postgres, run_sync

DSN = os.getenv("XDL_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.integration


def _apply_sql(path: str) -> None:
    if DSN is None:
        pytest.skip("XDL_TEST_POSTGRES_DSN is not configured")
    subprocess.run(
        ["psql", DSN, "-X", "-v", "ON_ERROR_STOP=1"],
        check=True,
        text=True,
        input=Path(path).read_text(encoding="utf-8"),
        capture_output=True,
    )


def test_sync_transaction_noop_and_rollback_are_atomic() -> None:
    if DSN is None:
        pytest.skip("XDL_TEST_POSTGRES_DSN is not configured")
    _apply_sql("sql/schema/001_xetra_loader.sql")
    _apply_sql("sql/schema/002_roles.sql")
    _apply_sql("sql/sync/001_xetra_loader_sync.sql")

    connection = connect_postgres(DSN)
    try:
        with connection.transaction():
            connection.execute(
                "CREATE TABLE IF NOT EXISTS xetra_loader.sync_core_probe "
                "(id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute("TRUNCATE xetra_loader.sync_core_probe")
            connection.execute(
                "DELETE FROM xetra_loader_sync.loader_runs WHERE dataset = 'sync-core-probe'"
            )
            connection.execute(
                "DELETE FROM xetra_loader_sync.sync_state WHERE dataset = 'sync-core-probe'"
            )

        def insert_probe(cursor: Cursor[object]) -> SyncCounters:
            cursor.execute(
                "INSERT INTO xetra_loader.sync_core_probe (id, value) VALUES (1, 'a')"
            )
            return SyncCounters(inserted=1)

        first = run_sync(
            connection,
            dataset="sync-core-probe",
            semantic_rows=[{"id": 1, "value": "a"}],
            mutate=insert_probe,
            run_id="sync-core-first",
        )
        assert first.status == "applied"
        assert first.counters.inserted == 1

        def must_not_run(cursor: Cursor[object]) -> SyncCounters:
            raise AssertionError("no-op replay must not call serving mutator")

        replay = run_sync(
            connection,
            dataset="sync-core-probe",
            semantic_rows=[{"value": "a", "id": 1}],
            mutate=must_not_run,
            run_id="sync-core-replay",
        )
        assert replay.status == "noop"
        assert replay.counters.total_mutations == 0

        def fail_after_mutation(cursor: Cursor[object]) -> SyncCounters:
            cursor.execute(
                "UPDATE xetra_loader.sync_core_probe SET value = 'broken' WHERE id = 1"
            )
            raise RuntimeError("injected sync failure")

        with pytest.raises(RuntimeError, match="injected sync failure"):
            run_sync(
                connection,
                dataset="sync-core-probe",
                semantic_rows=[{"id": 1, "value": "changed"}],
                mutate=fail_after_mutation,
                run_id="sync-core-failure",
            )

        value = connection.execute(
            "SELECT value FROM xetra_loader.sync_core_probe WHERE id = 1"
        ).fetchone()
        state = connection.execute(
            "SELECT semantic_fingerprint FROM xetra_loader_sync.sync_state "
            "WHERE dataset = 'sync-core-probe'"
        ).fetchone()
        failed_run = connection.execute(
            "SELECT count(*) FROM xetra_loader_sync.loader_runs "
            "WHERE run_id = 'sync-core-failure'"
        ).fetchone()
        assert value == ("a",)
        assert state == (first.semantic_fingerprint,)
        assert failed_run == (0,)
    finally:
        connection.close()

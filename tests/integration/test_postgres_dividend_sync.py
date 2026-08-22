import os
import subprocess
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from xetra_data_loader.contracts.corporate_actions import DividendEvent, retract_dividend
from xetra_data_loader.gold.dividends import build_dividend_gold
from xetra_data_loader.sync import connect_postgres
from xetra_data_loader.sync.dividends import sync_dividends

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


def _event(value: str) -> DividendEvent:
    return DividendEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        event_date=date(2026, 8, 20),
        value=Decimal(value),
        currency="EUR",
    )


def _dividend_count(connection: object) -> tuple[int]:
    return connection.execute(
        "SELECT count(*) FROM portfell_market.dividends"
    ).fetchone()


def test_dividend_sync_initial_replay_correction_and_retraction() -> None:
    if DSN is None:
        pytest.skip("XDL_TEST_POSTGRES_DSN is not configured")
    _apply_sql("sql/schema/001_portfell_market.sql")
    _apply_sql("sql/schema/002_roles.sql")
    _apply_sql("sql/sync/001_portfell_loader_sync.sql")
    connection = connect_postgres(DSN)
    try:
        with connection.transaction():
            connection.execute("TRUNCATE portfell_market.listings CASCADE")
            connection.execute(
                "DELETE FROM portfell_loader_sync.loader_runs WHERE dataset = 'dividends'"
            )
            connection.execute(
                "DELETE FROM portfell_loader_sync.sync_state WHERE dataset = 'dividends'"
            )
            connection.execute(
                "INSERT INTO portfell_market.listings "
                "(isin, exchange, code, fetched_at_utc, published_at_utc) "
                "VALUES ('DE0000000001', 'XETRA', 'AAA', now(), now())"
            )

        published = datetime(2026, 8, 22, 20, 0, tzinfo=UTC)
        old = _event("1.25")
        first_gold = build_dividend_gold([old])
        first = sync_dividends(
            connection,
            first_gold,
            run_id="dividend-first",
            published_at_utc=published,
        )
        assert first.counters.inserted == 1
        replay = sync_dividends(
            connection,
            first_gold,
            run_id="dividend-replay",
            published_at_utc=published,
        )
        assert replay.counters.total_mutations == 0

        new = _event("1.30")
        correction = sync_dividends(
            connection,
            build_dividend_gold([new, retract_dividend(old)]),
            run_id="dividend-correction",
            published_at_utc=published,
        )
        assert correction.counters.inserted == 1
        assert correction.counters.retracted == 1
        assert _dividend_count(connection) == (1,)

        removed = sync_dividends(
            connection,
            build_dividend_gold([retract_dividend(new)]),
            run_id="dividend-retraction",
            published_at_utc=published,
        )
        assert removed.counters.retracted == 1
        assert _dividend_count(connection) == (0,)
    finally:
        connection.close()

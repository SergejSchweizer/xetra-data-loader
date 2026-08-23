import os
import subprocess
from pathlib import Path

import pytest

DSN = os.getenv("XDL_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.integration


def _psql(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    if DSN is None:
        pytest.skip("XDL_TEST_POSTGRES_DSN is not configured")
    return subprocess.run(
        ["psql", DSN, "-X", "-v", "ON_ERROR_STOP=1", *arguments],
        check=True,
        text=True,
        input=input_text,
        capture_output=True,
    )


def test_market_schema_recreates_and_introspects_exact_types() -> None:
    _psql("-c", "DROP SCHEMA IF EXISTS xetra_loader CASCADE")
    schema_sql = Path("sql/schema/001_xetra_loader.sql").read_text(encoding="utf-8")
    _psql(input_text=schema_sql)
    result = _psql(
        "-At",
        "-c",
        "SELECT table_name || ':' || column_name || ':' || data_type || ':' || "
        "COALESCE(datetime_precision::text, '') FROM information_schema.columns "
        "WHERE table_schema='xetra_loader' ORDER BY table_name, ordinal_position",
    )
    rows = result.stdout.splitlines()
    assert any(row.startswith("eod_quotes:trade_date:date:") for row in rows)
    timestamp_rows = [row for row in rows if "timestamp with time zone" in row]
    assert timestamp_rows
    assert all(row.endswith(":6") for row in timestamp_rows)

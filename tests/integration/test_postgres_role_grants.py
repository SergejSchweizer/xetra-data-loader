import os
import subprocess
from pathlib import Path

import pytest

DSN = os.getenv("XDL_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.integration


def _psql(
    *arguments: str,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if DSN is None:
        pytest.skip("XDL_TEST_POSTGRES_DSN is not configured")
    return subprocess.run(
        ["psql", DSN, "-X", "-v", "ON_ERROR_STOP=1", *arguments],
        check=check,
        text=True,
        input=input_text,
        capture_output=True,
    )


def test_writer_and_read_only_grants() -> None:
    schema_sql = Path("sql/schema/001_xetra_market.sql").read_text(encoding="utf-8")
    grants_sql = Path("sql/schema/002_roles.sql").read_text(encoding="utf-8")
    _psql("-c", "DROP SCHEMA IF EXISTS xetra_market CASCADE")
    _psql(input_text=schema_sql)
    _psql(input_text=grants_sql)

    privileges = _psql(
        "-At",
        "-c",
        "SELECT has_table_privilege('xetra-loader', "
        "'xetra_market.listings', 'INSERT,UPDATE,DELETE'), "
        "has_table_privilege('portfell_app', 'xetra_market.listings', 'SELECT'), "
        "has_table_privilege('portfell_app', 'xetra_market.listings', 'INSERT,UPDATE,DELETE'), "
        "has_schema_privilege('portfell_app', 'xetra_market', 'CREATE')",
    ).stdout.strip()
    assert privileges == "t|t|f|f"

    forbidden = _psql(
        "-c",
        "SET ROLE portfell_app; INSERT INTO xetra_market.listings "
        "(isin, exchange, code, fetched_at_utc, published_at_utc) "
        "VALUES ('DE0000000001', 'XETRA', 'AAA', now(), now())",
        check=False,
    )
    assert forbidden.returncode != 0

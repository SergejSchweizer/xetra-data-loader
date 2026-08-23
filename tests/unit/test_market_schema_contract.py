from pathlib import Path

SCHEMA = Path("sql/schema/001_xetra_market.sql")


def test_schema_freezes_serving_tables_and_keys() -> None:
    sql = SCHEMA.read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS xetra_market" in sql
    assert "xetra_market.listings" in sql
    assert "xetra_market.eod_quotes" in sql
    assert "xetra_market.dividends" in sql
    assert "xetra_market.splits" in sql
    assert "PRIMARY KEY (isin, exchange, code)" in sql
    assert "PRIMARY KEY (isin, exchange, code, trade_date)" in sql
    assert sql.count("PRIMARY KEY (isin, exchange, code, event_key)") == 2


def test_schema_uses_exact_timestamp_and_date_contract() -> None:
    sql = SCHEMA.read_text(encoding="utf-8")
    assert "timestamp_eod TIMESTAMPTZ(6) NOT NULL" in sql
    assert "trade_date DATE NOT NULL" in sql
    assert "timestamp_eod = (trade_date::timestamp AT TIME ZONE 'UTC')" in sql
    assert "TIMESTAMP WITHOUT TIME ZONE" not in sql.upper()

BEGIN;

CREATE SCHEMA IF NOT EXISTS portfell_market;

CREATE TABLE IF NOT EXISTS portfell_market.listings (
    isin TEXT NOT NULL,
    exchange TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT,
    instrument_type TEXT,
    currency TEXT,
    country TEXT,
    fetched_at_utc TIMESTAMPTZ(6) NOT NULL,
    published_at_utc TIMESTAMPTZ(6) NOT NULL,
    PRIMARY KEY (isin, exchange, code),
    CHECK (btrim(isin) <> ''),
    CHECK (btrim(exchange) <> ''),
    CHECK (btrim(code) <> '')
);

CREATE TABLE IF NOT EXISTS portfell_market.eod_quotes (
    isin TEXT NOT NULL,
    exchange TEXT NOT NULL,
    code TEXT NOT NULL,
    trade_date DATE NOT NULL,
    timestamp_eod TIMESTAMPTZ(6) NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC NOT NULL,
    adjusted_close NUMERIC,
    volume BIGINT,
    fetched_at_utc TIMESTAMPTZ(6) NOT NULL,
    published_at_utc TIMESTAMPTZ(6) NOT NULL,
    PRIMARY KEY (isin, exchange, code, trade_date),
    FOREIGN KEY (isin, exchange, code)
        REFERENCES portfell_market.listings (isin, exchange, code),
    CHECK (timestamp_eod = (trade_date::timestamp AT TIME ZONE 'UTC')),
    CHECK (volume IS NULL OR volume >= 0)
);

CREATE TABLE IF NOT EXISTS portfell_market.dividends (
    isin TEXT NOT NULL,
    exchange TEXT NOT NULL,
    code TEXT NOT NULL,
    event_key CHAR(64) NOT NULL,
    event_date DATE NOT NULL,
    declaration_date DATE,
    record_date DATE,
    payment_date DATE,
    value NUMERIC NOT NULL,
    currency TEXT,
    period TEXT,
    fetched_at_utc TIMESTAMPTZ(6) NOT NULL,
    published_at_utc TIMESTAMPTZ(6) NOT NULL,
    PRIMARY KEY (isin, exchange, code, event_key),
    FOREIGN KEY (isin, exchange, code)
        REFERENCES portfell_market.listings (isin, exchange, code),
    CHECK (event_key ~ '^[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS portfell_market.splits (
    isin TEXT NOT NULL,
    exchange TEXT NOT NULL,
    code TEXT NOT NULL,
    event_key CHAR(64) NOT NULL,
    event_date DATE NOT NULL,
    split_ratio TEXT NOT NULL,
    split_factor NUMERIC,
    fetched_at_utc TIMESTAMPTZ(6) NOT NULL,
    published_at_utc TIMESTAMPTZ(6) NOT NULL,
    PRIMARY KEY (isin, exchange, code, event_key),
    FOREIGN KEY (isin, exchange, code)
        REFERENCES portfell_market.listings (isin, exchange, code),
    CHECK (event_key ~ '^[0-9a-f]{64}$'),
    CHECK (btrim(split_ratio) <> '')
);

COMMIT;

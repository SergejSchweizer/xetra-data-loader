BEGIN;
SET LOCAL TIME ZONE 'UTC';

CREATE SCHEMA IF NOT EXISTS xetra_loader_sync;

CREATE TABLE IF NOT EXISTS xetra_loader_sync.sync_state (
    dataset TEXT PRIMARY KEY,
    semantic_fingerprint CHAR(64) NOT NULL,
    row_count BIGINT NOT NULL CHECK (row_count >= 0),
    synced_at_utc TIMESTAMPTZ(6) NOT NULL,
    CHECK (semantic_fingerprint ~ '^[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS xetra_loader_sync.loader_runs (
    run_id TEXT PRIMARY KEY,
    dataset TEXT NOT NULL,
    semantic_fingerprint CHAR(64) NOT NULL,
    row_count BIGINT NOT NULL CHECK (row_count >= 0),
    inserted_count BIGINT NOT NULL CHECK (inserted_count >= 0),
    updated_count BIGINT NOT NULL CHECK (updated_count >= 0),
    deleted_count BIGINT NOT NULL CHECK (deleted_count >= 0),
    retracted_count BIGINT NOT NULL CHECK (retracted_count >= 0),
    started_at_utc TIMESTAMPTZ(6) NOT NULL,
    finished_at_utc TIMESTAMPTZ(6) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('applied', 'noop')),
    CHECK (semantic_fingerprint ~ '^[0-9a-f]{64}$'),
    CHECK (finished_at_utc >= started_at_utc)
);

REVOKE ALL ON SCHEMA xetra_loader_sync FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA xetra_loader_sync FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA xetra_loader_sync TO "xetra-loader";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA xetra_loader_sync
    TO "xetra-loader";
REVOKE ALL ON SCHEMA xetra_loader_sync FROM portfell_app;
REVOKE ALL ON ALL TABLES IN SCHEMA xetra_loader_sync FROM portfell_app;

COMMIT;

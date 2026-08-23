BEGIN;

DO $$
BEGIN
    CREATE ROLE "xetra-loader" NOLOGIN;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

DO $$
BEGIN
    CREATE ROLE portfell_app NOLOGIN;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END
$$;

REVOKE ALL ON SCHEMA xetra_market FROM PUBLIC;
GRANT USAGE ON SCHEMA xetra_market TO "xetra-loader", portfell_app;
REVOKE CREATE ON SCHEMA xetra_market FROM "xetra-loader", portfell_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA xetra_market
    TO "xetra-loader";
GRANT SELECT ON ALL TABLES IN SCHEMA xetra_market TO portfell_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA xetra_market FROM portfell_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA xetra_market
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "xetra-loader";
ALTER DEFAULT PRIVILEGES IN SCHEMA xetra_market
    GRANT SELECT ON TABLES TO portfell_app;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'xetra_loader_sync') THEN
        REVOKE ALL ON SCHEMA xetra_loader_sync FROM portfell_app;
        REVOKE ALL ON ALL TABLES IN SCHEMA xetra_loader_sync FROM portfell_app;
    END IF;
END
$$;

COMMIT;

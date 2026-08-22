BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'portfell_data_loader')
        AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'xetra-data-loader') THEN
        ALTER ROLE portfell_data_loader RENAME TO "xetra-data-loader";
    END IF;
END
$$;

DO $$
BEGIN
    CREATE ROLE "xetra-data-loader" NOLOGIN;
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

REVOKE ALL ON SCHEMA portfell_market FROM PUBLIC;
GRANT USAGE ON SCHEMA portfell_market TO "xetra-data-loader", portfell_app;
REVOKE CREATE ON SCHEMA portfell_market FROM "xetra-data-loader", portfell_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA portfell_market
    TO "xetra-data-loader";
GRANT SELECT ON ALL TABLES IN SCHEMA portfell_market TO portfell_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA portfell_market FROM portfell_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA portfell_market
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "xetra-data-loader";
ALTER DEFAULT PRIVILEGES IN SCHEMA portfell_market
    GRANT SELECT ON TABLES TO portfell_app;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'portfell_loader_sync') THEN
        REVOKE ALL ON SCHEMA portfell_loader_sync FROM portfell_app;
        REVOKE ALL ON ALL TABLES IN SCHEMA portfell_loader_sync FROM portfell_app;
    END IF;
END
$$;

COMMIT;

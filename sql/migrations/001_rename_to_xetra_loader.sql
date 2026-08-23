BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'xetra-data-loader')
        AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'xetra-loader') THEN
        RAISE EXCEPTION 'both xetra-data-loader and xetra-loader roles exist';
    ELSIF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'xetra-data-loader') THEN
        ALTER ROLE "xetra-data-loader" RENAME TO "xetra-loader";
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'portfell_market')
        AND EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'xetra_market') THEN
        RAISE EXCEPTION 'both portfell_market and xetra_market schemas exist';
    ELSIF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'portfell_market') THEN
        ALTER SCHEMA portfell_market RENAME TO xetra_market;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'portfell_loader_sync')
        AND EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'xetra_loader_sync') THEN
        RAISE EXCEPTION 'both portfell_loader_sync and xetra_loader_sync schemas exist';
    ELSIF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'portfell_loader_sync') THEN
        ALTER SCHEMA portfell_loader_sync RENAME TO xetra_loader_sync;
    END IF;
END
$$;

COMMIT;

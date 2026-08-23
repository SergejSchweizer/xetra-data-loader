BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'xetra_market')
        AND EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'xetra_loader') THEN
        RAISE EXCEPTION 'both xetra_market and xetra_loader schemas exist';
    ELSIF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'xetra_market') THEN
        ALTER SCHEMA xetra_market RENAME TO xetra_loader;
    END IF;
END
$$;

COMMIT;

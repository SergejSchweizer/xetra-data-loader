BEGIN;

ALTER TABLE xetra_loader.listings
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN;

UPDATE xetra_loader.listings
SET is_active = TRUE
WHERE is_active IS NULL;

ALTER TABLE xetra_loader.listings
    ALTER COLUMN is_active SET NOT NULL;

ALTER TABLE xetra_loader.listings
    ALTER COLUMN is_active SET DEFAULT TRUE;

COMMIT;

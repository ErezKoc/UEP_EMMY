-- 0001 ROLLBACK -- narrow symptom_checks.triage_level back to VARCHAR(10)
--
-- WHEN THIS IS SAFE
--   Narrowing a VARCHAR fails outright if any stored value is longer than the new
--   bound, so this is only safe while every level in the table is 10 characters or
--   fewer. Today all four are:
--     'red' (3), 'amber' (5), 'green' (5), 'unassessed' (10)
--   `unassessed` fits VARCHAR(10) exactly, so rolling back does NOT require
--   deleting or rewriting any triage verdict -- the reason the column was widened
--   was headroom for a FUTURE level, not an overflow that exists now.
--
-- WHEN THIS IS NOT SAFE
--   If a level longer than 10 characters has been introduced and written to this
--   table, this rollback must not run: it would either fail (good) or, if someone
--   forced it with a USING clause, silently truncate a clinical verdict (very
--   bad). The guard below aborts with an explicit error rather than letting that
--   happen, and names the offending values.
--
--   Rolling the SCHEMA back without also rolling the APPLICATION back is unsafe
--   for the same reason: application code that can emit a longer level will start
--   failing its writes. Deploy order for a rollback is application first, then
--   this file.
--
-- APPLY
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/0001_triage_level_varchar32.rollback.sql

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    current_width integer;
    too_long      integer;
    offenders     text;
BEGIN
    SELECT character_maximum_length
      INTO current_width
      FROM information_schema.columns
     WHERE table_name = 'symptom_checks'
       AND column_name = 'triage_level';

    IF current_width IS NULL THEN
        RAISE NOTICE 'symptom_checks.triage_level not found -- nothing to roll back.';
        RETURN;
    END IF;

    IF current_width <= 10 THEN
        RAISE NOTICE 'symptom_checks.triage_level is already VARCHAR(%) -- nothing to do.',
            current_width;
        RETURN;
    END IF;

    -- Refuse rather than truncate a stored clinical verdict.
    SELECT count(*), string_agg(DISTINCT triage_level, ', ')
      INTO too_long, offenders
      FROM symptom_checks
     WHERE length(triage_level) > 10;

    IF too_long > 0 THEN
        RAISE EXCEPTION
            'Refusing to narrow triage_level: % row(s) hold a value longer than 10 characters '
            '(%). Narrowing would truncate a stored triage verdict. Roll the application back '
            'first, migrate or remove those rows deliberately, then re-run this file.',
            too_long, offenders;
    END IF;

    ALTER TABLE symptom_checks
        ALTER COLUMN triage_level TYPE VARCHAR(10);

    RAISE NOTICE 'symptom_checks.triage_level narrowed from VARCHAR(%) to VARCHAR(10).',
        current_width;
END
$$;

COMMIT;

-- Post-flight check. Expect exactly one row: 10.
--   SELECT character_maximum_length
--     FROM information_schema.columns
--    WHERE table_name = 'symptom_checks' AND column_name = 'triage_level';

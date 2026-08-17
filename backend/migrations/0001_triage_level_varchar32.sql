-- 0001 -- widen symptom_checks.triage_level from VARCHAR(10) to VARCHAR(32)
--
-- WHY
--   The triage engine gained a fourth level, `unassessed`, which it returns when
--   the owner described something no published source we hold covers. Before it
--   existed such a case was answered `green`, and green is the reassuring end of
--   a red/amber/green scale -- an owner reporting a seizing rabbit was shown the
--   same colour as an owner told to monitor at home.
--
--   `unassessed` is exactly 10 characters, so it fits the old column with nothing
--   to spare. The widening is about headroom, not about a value that overflows
--   today: the next level name added would break inserts on PostgreSQL with a
--   `value too long for type character varying(10)` error, and the failure would
--   land on a write path that stores a clinical verdict.
--
-- EXISTING DATA
--   Widening a VARCHAR never invalidates a stored value. Every level ever written
--   is well inside the new bound:
--     'red' (3), 'amber' (5), 'green' (5), 'unassessed' (10)
--   No row is read, rewritten, or reinterpreted. There is no data migration here,
--   only a relaxed constraint.
--
-- LOCKING
--   PostgreSQL 9.2 and later treat a VARCHAR length INCREASE as a metadata-only
--   change: no table rewrite, and dependent indexes (here
--   `ix_symptom_checks_triage_level`) are left in place. The statement still takes
--   a brief ACCESS EXCLUSIVE lock on the table, so run it when the table is not
--   under sustained write load. `lock_timeout` below makes the migration give up
--   rather than queue behind a long transaction and block application writes.
--
-- SAFETY
--   Idempotent: re-running it after a partially-applied deploy is a no-op.
--   Applying it before the new application code is deployed is also safe -- a wider
--   column accepts everything the old code writes.
--
-- APPLY
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/0001_triage_level_varchar32.sql
--
-- ROLLBACK
--   migrations/0001_triage_level_varchar32.rollback.sql

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $$
DECLARE
    current_width integer;
BEGIN
    SELECT character_maximum_length
      INTO current_width
      FROM information_schema.columns
     WHERE table_name = 'symptom_checks'
       AND column_name = 'triage_level';

    IF current_width IS NULL THEN
        RAISE NOTICE
            'symptom_checks.triage_level not found -- nothing to do. This is expected on a '
            'database created by create_all after the change, or one where the table does not '
            'exist yet.';
        RETURN;
    END IF;

    IF current_width >= 32 THEN
        RAISE NOTICE 'symptom_checks.triage_level is already VARCHAR(%) -- nothing to do.',
            current_width;
        RETURN;
    END IF;

    ALTER TABLE symptom_checks
        ALTER COLUMN triage_level TYPE VARCHAR(32);

    RAISE NOTICE 'symptom_checks.triage_level widened from VARCHAR(%) to VARCHAR(32).',
        current_width;
END
$$;

COMMIT;

-- Post-flight check. Expect exactly one row: 32.
--   SELECT character_maximum_length
--     FROM information_schema.columns
--    WHERE table_name = 'symptom_checks' AND column_name = 'triage_level';

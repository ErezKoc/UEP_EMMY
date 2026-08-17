# Schema migrations

This project has **no migration tool**. The schema is created by
`Base.metadata.create_all(bind=engine)` in `app/main.py`, which creates missing tables and does
nothing at all to tables that already exist. A fresh database therefore needs nothing from this
directory; an existing one needs the numbered SQL applied by hand.

Adding Alembic is the right long-term answer, and folding `0001` in as its baseline is tracked as
follow-up work. Until then:

## Applying a migration

Files are numbered and applied in order. Each has a matching `.rollback.sql`.

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/0001_triage_level_varchar32.sql
```

Every migration here is written to be **idempotent** — safe to run twice — so a partially-applied
deploy can simply be re-run.

## Which databases need this

| Deployment | Needs migration? |
| --- | --- |
| PostgreSQL (the `database_url` default) | **Yes.** Postgres enforces `VARCHAR(n)`. |
| SQLite (local dev, `uep_emmy.db`) | No. SQLite does not enforce `VARCHAR` length; a longer value is stored regardless. |
| Cloudflare D1 (`frontend/drizzle`) | No. The D1 schema covers users, posts and analyses only — it has no `symptom_checks` table. |
| A database created after this change | No. `create_all` builds the column at its current width. |

## Verifying before and after

```sql
SELECT character_maximum_length
FROM information_schema.columns
WHERE table_name = 'symptom_checks' AND column_name = 'triage_level';
```

`10` means the migration is outstanding; `32` means it has been applied.

## Keeping the model and the SQL in step

`tests/test_migrations.py` fails if `SymptomCheck.triage_level`'s declared width stops matching the
width the latest migration sets, or if any `TriageLevel` value no longer fits. A schema change made
in the model alone will not pass CI.

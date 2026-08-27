# Schema migrations

This project has **no migration tool**. The schema is created by
`Base.metadata.create_all(bind=engine)` in `app/main.py`, which creates missing tables and does
nothing at all to tables that already exist. A fresh database therefore needs nothing from this
directory; an existing one needs the numbered SQL applied by hand.

Adding Alembic is the right long-term answer, and folding `0001` in as its baseline is tracked as
follow-up work. Until then:

## What lives here, and what does not

This directory is only for schema changes `create_all` and
`ensure_compatibility_columns` **cannot** make — so far, one widening of an
existing column's type.

Everything additive is handled in `app/main.py` on boot, and that is deliberate:

| Change | Handled by |
| --- | --- |
| A new table | `Base.metadata.create_all` |
| A new column on an existing table | `ensure_compatibility_columns` |
| Changing an existing column's type or width | numbered SQL here |

The email work is entirely additive and therefore adds nothing to this
directory. It introduces two tables — `email_messages` and `security_tokens` —
which `create_all` builds, and seven columns on tables that already exist, which
`ensure_compatibility_columns` adds:

| Table | Columns |
| --- | --- |
| `users` | `notify_leads`, `email_verified_at`, `pending_email` |
| `notifications` | `email_state`, `email_attempts`, `email_next_attempt_at`, `email_detail` |

Every one is nullable or carries a default that means what an existing row
already meant. `notify_leads` is NULL, which reads as "just `notify_lead_days`";
`email_verified_at` is NULL, which reads as "nobody has proved this address" —
true for every account that predates there being a way to prove one, and
backfilling a timestamp would claim a verification that never happened. Existing
notifications default to `email_state = 'not_requested'` rather than to `sent`,
which we cannot know, or `failed`, which would put a red mark on rows that were
fine.

`tests/test_email_compatibility.py` builds a database in the pre-email shape,
runs the compatibility step against it, and checks the rows survive and the
application can read them. Re-running the step is a no-op, so a restart is safe.

**No database needs to be deleted or recreated for any of this.**

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

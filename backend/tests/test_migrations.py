"""The hand-written migrations must stay in step with the models.

There is no migration tool here — `create_all` builds fresh databases and does
nothing to existing ones — so nothing automatically notices when a model's
column changes and the SQL in `migrations/` does not. These tests are that
notice.

They read the SQL as text rather than executing it. Running the real thing needs
a PostgreSQL server, which this suite deliberately does not require; what can be
checked offline is that the numbers agree and that every level still fits.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.models.symptom_check import SymptomCheck
from app.schemas.triage import TriageLevel

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
UP = MIGRATIONS / "0001_triage_level_varchar32.sql"
DOWN = MIGRATIONS / "0001_triage_level_varchar32.rollback.sql"


def _declared_width(sql: str) -> int:
    """The width the ALTER in this file sets."""
    match = re.search(r"ALTER COLUMN triage_level TYPE VARCHAR\((\d+)\)", sql)
    assert match, "No triage_level ALTER found in the migration."
    return int(match.group(1))


def test_every_migration_has_a_rollback():
    forward = sorted(p for p in MIGRATIONS.glob("*.sql") if not p.name.endswith(".rollback.sql"))
    assert forward, "No migrations found."
    for path in forward:
        rollback = path.with_suffix("").with_suffix("")  # strip .sql
        rollback = path.parent / f"{path.stem}.rollback.sql"
        assert rollback.exists(), f"{path.name} has no rollback."


def test_the_migration_matches_the_model_column_width():
    """If someone widens the column in Python only, this fails."""
    model_width = SymptomCheck.__table__.c.triage_level.type.length
    assert _declared_width(UP.read_text(encoding="utf-8")) == model_width, (
        "migrations/0001 and SymptomCheck.triage_level disagree about the column width. "
        "A database migrated by this SQL would not match the model."
    )


def test_every_triage_level_fits_the_migrated_column():
    width = _declared_width(UP.read_text(encoding="utf-8"))
    for level in TriageLevel:
        assert len(level.value) <= width, (
            f"TriageLevel.{level.name} ({level.value!r}, {len(level.value)} chars) does not fit "
            f"VARCHAR({width}). Add a migration widening the column before shipping this value."
        )


def test_the_rollback_narrows_to_the_previous_width():
    assert _declared_width(DOWN.read_text(encoding="utf-8")) == 10, (
        "The rollback must restore the width the column had before 0001."
    )


@pytest.mark.parametrize("level", list(TriageLevel), ids=lambda level: level.value)
def test_existing_rows_stay_valid_after_the_rollback(level):
    """Rolling back must not truncate any verdict the system can write today.

    `unassessed` is exactly 10 characters, so it survives the narrowing. This
    test is what will fail — loudly, at the point of writing the code rather than
    at the point of running the rollback — if a longer level is ever added while
    the rollback still claims to be safe.
    """
    assert len(level.value) <= 10, (
        f"{level.value!r} is longer than VARCHAR(10), so the 0001 rollback can no longer run "
        "without truncating stored data. Update the rollback's guard and its documented "
        "safety conditions."
    )


def test_the_migration_is_guarded_and_idempotent():
    """Re-running a partially-applied deploy must be a no-op, not an error."""
    up = UP.read_text(encoding="utf-8")
    assert "character_maximum_length" in up, "The migration does not check the current width."
    assert "current_width >= 32" in up, "The migration is not guarded against re-running."
    assert "lock_timeout" in up, "The migration should give up rather than block writes."


def test_the_rollback_refuses_to_truncate_a_stored_verdict():
    down = DOWN.read_text(encoding="utf-8")
    assert "RAISE EXCEPTION" in down, "The rollback must abort rather than truncate."
    assert "length(triage_level) > 10" in down, "The rollback does not check for long values."

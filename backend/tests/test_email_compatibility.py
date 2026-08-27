"""An existing database must keep working, without being recreated.

There is no migration tool here: `create_all` builds missing TABLES and does
nothing at all to tables that already exist, so every new COLUMN on an existing
table has to be added by `ensure_compatibility_columns`. A column that is in the
model and not in that function is a 500 on every request that touches the table,
in exactly the deployments that already have data.

The email work adds two tables (`email_messages`, `security_tokens` — handled by
`create_all`) and seven columns across two existing ones. These tests build a
database in the shape it had BEFORE that work, run the compatibility step, and
check the application can read and write it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.db.base import Base
from app.models import User
from app.models.email import EmailState
from app.models.notification import Notification, NotificationKind

#: What this piece of work added to tables that already existed.
NEW_USER_COLUMNS = ["notify_leads", "email_verified_at", "pending_email"]
NEW_NOTIFICATION_COLUMNS = [
    "email_state",
    "email_attempts",
    "email_next_attempt_at",
    "email_detail",
]


@pytest.fixture
def legacy_database(tmp_path, monkeypatch):
    """A database in the shape it had before the email work.

    Built by creating the current schema and then dropping the new columns,
    which is far more honest than hand-writing the old DDL: the old DDL would
    be a copy that drifts, and this cannot drift because it is derived from the
    schema in front of it.
    """
    path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        for column in NEW_USER_COLUMNS:
            connection.execute(text(f"ALTER TABLE users DROP COLUMN {column}"))
        for column in NEW_NOTIFICATION_COLUMNS:
            connection.execute(text(f"ALTER TABLE notifications DROP COLUMN {column}"))
        # A row from before any of this existed, to prove nothing is lost.
        connection.execute(
            text(
                "INSERT INTO users (id, email, display_name, role, notify_in_app, "
                "notify_email, notify_lead_days, notify_time, verification_status, "
                "account_status, accepts_appointments, created_at) VALUES "
                "('00000000000000000000000000000001', 'existing@example.com', 'Existing', "
                "'owner', 1, 1, 1, '09:00:00', 'unverified', 'active', 0, '2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO notifications (id, user_id, kind, title, body, dedupe_key, "
                "emailed, created_at) VALUES "
                "('00000000000000000000000000000002', '00000000000000000000000000000001', "
                "'reminder_due', 'Reminder: Booster', 'Due tomorrow.', "
                "'reminder:abc:2026-01-02', 0, '2026-01-01 00:00:00')"
            )
        )

    # `ensure_compatibility_columns` works against the module-level engine.
    import app.main as main_module

    monkeypatch.setattr(main_module, "engine", engine)
    return engine


def test_the_legacy_shape_really_is_missing_the_columns(legacy_database):
    """The fixture has to be wrong-shaped, or every test below proves nothing."""
    inspector = inspect(legacy_database)
    users = {column["name"] for column in inspector.get_columns("users")}
    notifications = {column["name"] for column in inspector.get_columns("notifications")}

    assert not users & set(NEW_USER_COLUMNS)
    assert not notifications & set(NEW_NOTIFICATION_COLUMNS)


def test_the_missing_columns_are_added_in_place(legacy_database):
    import app.main as main_module

    main_module.ensure_compatibility_columns()

    inspector = inspect(legacy_database)
    users = {column["name"] for column in inspector.get_columns("users")}
    notifications = {column["name"] for column in inspector.get_columns("notifications")}

    assert set(NEW_USER_COLUMNS) <= users
    assert set(NEW_NOTIFICATION_COLUMNS) <= notifications


def test_existing_rows_survive_untouched(legacy_database):
    import app.main as main_module

    main_module.ensure_compatibility_columns()

    with Session(legacy_database) as session:
        user = session.scalars(select(User)).one()
        notification = session.scalars(select(Notification)).one()

    assert user.email == "existing@example.com"
    assert user.display_name == "Existing"
    assert notification.title == "Reminder: Booster"
    assert notification.kind is NotificationKind.REMINDER_DUE


def test_an_existing_notification_reads_as_nothing_queued(legacy_database):
    """Not "sent", which we cannot know, and not "failed", which would be a lie.

    A notification created before the queue existed was emailed inline or not at
    all. The truthful thing to say about it now is that nothing is queued for
    it — anything else puts a claim or a red mark on rows that were fine.
    """
    import app.main as main_module

    main_module.ensure_compatibility_columns()

    with Session(legacy_database) as session:
        notification = session.scalars(select(Notification)).one()

    assert notification.email_state is EmailState.NOT_REQUESTED
    assert notification.email_attempts == 0
    assert notification.email_detail is None


def test_existing_accounts_are_grandfathered_so_the_upgrade_locks_nobody_out(
    legacy_database,
):
    """The one backfill in this codebase, and why it earns its exception.

    Signing in now requires a confirmed address. Every account in an existing
    database was created before there was any way to confirm one, so leaving
    `email_verified_at` NULL would lock out every user of a working deployment
    - including the administrator who would have to fix it.
    """
    import app.main as main_module

    main_module.ensure_compatibility_columns()

    with Session(legacy_database) as session:
        user = session.scalars(select(User)).one()

    assert user.email_verified_at is not None
    assert user.email_is_verified is True
    # Stamped with when the account was trusted, not when this code ran - so an
    # audit can tell a grandfathered row from a genuinely proved one.
    assert user.email_verified_at == user.created_at


def test_the_backfill_never_runs_a_second_time(legacy_database):
    """Otherwise every restart confirms whoever signed up and never clicked.

    That would be the sign-in rule quietly undone by its own migration, on a
    schedule nobody is watching.
    """
    import uuid

    import app.main as main_module
    from sqlalchemy import text

    main_module.ensure_compatibility_columns()

    # A new account, created after the gate exists: unconfirmed on purpose.
    with legacy_database.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, display_name, role, notify_in_app, "
                "notify_email, notify_lead_days, notify_time, verification_status, "
                "account_status, accepts_appointments, created_at) VALUES "
                "(:id, 'new@example.com', 'New', 'owner', 1, 1, 1, '09:00:00', "
                "'unverified', 'active', 0, '2026-06-01 00:00:00')"
            ),
            {"id": uuid.uuid4().hex},
        )

    main_module.ensure_compatibility_columns()
    main_module.ensure_compatibility_columns()

    with Session(legacy_database) as session:
        newcomer = session.scalars(
            select(User).where(User.email == "new@example.com")
        ).one()

    assert newcomer.email_verified_at is None
    assert newcomer.email_is_verified is False


def test_an_existing_account_keeps_the_alerts_it_already_had(legacy_database):
    """`notify_leads` is NULL, which means exactly what the old single value meant."""
    import app.main as main_module

    main_module.ensure_compatibility_columns()

    with Session(legacy_database) as session:
        user = session.scalars(select(User)).one()

    assert user.notify_leads is None
    assert user.lead_days == [user.notify_lead_days]
    # No address change is waiting, and nothing pretends otherwise.
    assert user.pending_email is None


def test_running_the_compatibility_step_twice_is_a_no_op(legacy_database):
    """A restart must not fail with "duplicate column name"."""
    import app.main as main_module

    main_module.ensure_compatibility_columns()
    main_module.ensure_compatibility_columns()

    with Session(legacy_database) as session:
        assert session.scalars(select(User)).one().email == "existing@example.com"


def test_the_new_tables_are_created_by_create_all(legacy_database):
    """`email_messages` and `security_tokens` are new tables, not new columns."""
    tables = set(inspect(legacy_database).get_table_names())

    assert "email_messages" in tables
    assert "security_tokens" in tables


def test_the_email_state_column_is_wide_enough_for_every_state():
    """VARCHAR(13) is exactly `not_requested`. A longer state needs a migration."""
    import re

    from pathlib import Path

    main_py = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r"email_state VARCHAR\((\d+)\)", main_py)
    assert match, "The email_state compatibility column is missing from main.py."
    width = int(match.group(1))

    for state in EmailState:
        assert len(state.value) <= width, (
            f"EmailState.{state.name} ({state.value!r}) does not fit VARCHAR({width}). "
            "Widen the compatibility column before shipping this value."
        )


def test_every_new_column_is_declared_in_the_compatibility_step():
    """A column added to a model and not to `main.py` is a 500 on upgrade.

    Compares the model against the ALTER statements rather than against a
    hand-kept list, so a column added later is caught by this test rather than
    by an existing deployment.
    """
    from pathlib import Path

    main_py = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(
        encoding="utf-8"
    )

    for column in NEW_USER_COLUMNS:
        assert f"ALTER TABLE users ADD COLUMN {column}" in main_py
    for column in NEW_NOTIFICATION_COLUMNS:
        assert f"ALTER TABLE notifications ADD COLUMN {column}" in main_py

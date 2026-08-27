"""Signing in requires a confirmed address — without locking anybody out.

The rule itself is one line in `/login`. Everything that makes it survivable is
here: the fixture accounts nobody can read mail for, and the databases that
existed before the rule did.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.db.base import Base
from app.db.seed import (
    SEEDED_ACCOUNTS,
    ensure_admin_account,
    ensure_seeded_accounts_verified,
    seed_demo_data,
)
from app.models import User


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _accounts(session) -> dict[str, User]:
    return {user.email: user for user in session.scalars(select(User)).all()}


def test_a_fresh_database_can_be_signed_into(session):
    """A checkout with no way in is a checkout nobody can demo.

    Every fixture address is at `@uepemmy.com`, which nobody can read, so if
    seeding left them unconfirmed the documented demo logins would all be
    refused and there would be no way to reach the admin queue at all.
    """
    seed_demo_data(session)
    ensure_admin_account(session)

    accounts = _accounts(session)
    for email in SEEDED_ACCOUNTS:
        assert email in accounts, f"{email} was not seeded"
        assert accounts[email].email_is_verified, f"{email} cannot sign in"


def test_demo_accounts_seeded_before_the_rule_are_repaired_on_boot(session):
    """`seed_demo_data` only fires on an empty database, so this is the only route.

    A deployment that already had these accounts would otherwise never get the
    flag, and its demo logins would break on upgrade.
    """
    seed_demo_data(session)
    ensure_admin_account(session)
    for user in session.scalars(select(User)).all():
        user.email_verified_at = None
    session.commit()

    repaired = ensure_seeded_accounts_verified(session)

    assert repaired == len(SEEDED_ACCOUNTS)
    assert all(user.email_is_verified for user in _accounts(session).values())


def test_repairing_twice_changes_nothing(session):
    seed_demo_data(session)
    ensure_admin_account(session)

    assert ensure_seeded_accounts_verified(session) == 0


def test_a_real_account_is_never_confirmed_on_its_behalf(session):
    """The rule must not be undone by the thing that keeps the demo working.

    A heuristic like "confirm everybody if nobody is confirmed yet" would, on a
    fresh deployment, silently let in the first person who signed up and never
    opened their link. This matches the four fixture addresses by name instead.
    """
    seed_demo_data(session)
    ensure_admin_account(session)
    session.add(
        User(email="a.real.person@example.com", display_name="Real", password_hash="x")
    )
    session.commit()

    ensure_seeded_accounts_verified(session)
    ensure_seeded_accounts_verified(session)

    real = _accounts(session)["a.real.person@example.com"]
    assert real.email_verified_at is None
    assert real.email_is_verified is False


def test_an_account_that_looks_like_a_fixture_but_is_not_stays_unconfirmed(session):
    """Only the exact seeded addresses, not anything that resembles them."""
    session.add(
        User(email="demo.vet@uepemmy.com.evil.test", display_name="Nope", password_hash="x")
    )
    session.commit()

    ensure_seeded_accounts_verified(session)

    assert _accounts(session)["demo.vet@uepemmy.com.evil.test"].email_verified_at is None


# ------------------------------------------- a token from before the rule


def test_a_leftover_token_stops_working_too(session):
    """Tokens live a week, so `/login` alone would leave a seven-day gap.

    An account signed in BEFORE confirmation was required would keep working
    for the life of its token - signed in, having never proved its address,
    which is the one thing the rule exists to prevent.
    """
    from fastapi import HTTPException

    from app.api.deps import EMAIL_UNVERIFIED, get_current_user

    unconfirmed = User(email="stale@example.com", display_name="Stale", password_hash="x")
    session.add(unconfirmed)
    session.commit()

    with pytest.raises(HTTPException) as raised:
        get_current_user(user=unconfirmed)

    assert raised.value.status_code == 403
    assert raised.value.detail["code"] == EMAIL_UNVERIFIED


def test_a_confirmed_account_passes_the_same_check(session):
    from app.api.deps import get_current_user
    from app.services.auth_email import utcnow

    confirmed = User(
        email="fine@example.com",
        display_name="Fine",
        password_hash="x",
        email_verified_at=utcnow(),
    )
    session.add(confirmed)
    session.commit()

    assert get_current_user(user=confirmed) is confirmed


def test_no_session_is_still_a_401_not_a_403(session):
    """"Who are you" and "you may not" are different questions."""
    from fastapi import HTTPException

    from app.api.deps import get_current_user

    with pytest.raises(HTTPException) as raised:
        get_current_user(user=None)

    assert raised.value.status_code == 401

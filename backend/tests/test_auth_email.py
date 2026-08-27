"""Signup verification, address changes, and forgotten passwords.

Driven through a real FastAPI app rather than by calling the route functions
directly, because half of what is being tested here is HTTP-shaped: the status
code a spent link produces, the header a rate limit carries, and above all the
requirement that two different situations produce byte-for-byte the same
response.

The app is assembled from the two routers under test rather than imported from
`app.main`, whose lifespan seeds a database and loads two ~19 MB ONNX models.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1 import auth as auth_routes
from app.api.v1 import users as user_routes
from app.core.security import verify_password
from app.db.base import Base
from app.db.session import get_db
from app.models import User
from app.models.email import EmailCategory, EmailMessage, EmailState
from app.models.token import SecurityToken, TokenPurpose
from app.services import auth_email


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def client(db_session):
    api = FastAPI()
    api.include_router(auth_routes.router, prefix="/v1/auth")
    api.include_router(user_routes.router, prefix="/v1/users")
    api.dependency_overrides[get_db] = lambda: db_session
    # Limiters are module-level and would otherwise carry counts between tests,
    # making whichever test ran fourth fail for reasons of its own.
    auth_routes.reset_rate_limits()
    with TestClient(api) as client:
        yield client
    auth_routes.reset_rate_limits()


def _signup(client, email="alex@example.com", password="hunter2hunter2"):
    """Create an account. Returns the signup body - there is no session in it."""
    response = client.post(
        "/v1/auth/signup",
        json={"email": email, "password": password, "display_name": "Alex"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _confirm(client, minted, db_session) -> None:
    """Open the newest verification link, so the account can sign in."""
    raw = _latest(minted, TokenPurpose.EMAIL_VERIFICATION)
    response = client.post("/v1/auth/verify-email", json={"token": raw})
    assert response.status_code == 200, response.text
    db_session.expire_all()


def _signed_in(client, minted, db_session, email="alex@example.com",
               password="hunter2hunter2") -> dict:
    """A confirmed account, signed in. Returns the session body."""
    _signup(client, email=email, password=password)
    _confirm(client, minted, db_session)
    response = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _queued(db_session, category=EmailCategory.SECURITY) -> list[EmailMessage]:
    return list(
        db_session.scalars(
            select(EmailMessage).where(EmailMessage.category == category)
        ).all()
    )


def _token_from(db_session, purpose: TokenPurpose) -> SecurityToken:
    return db_session.scalars(
        select(SecurityToken)
        .where(SecurityToken.purpose == purpose, SecurityToken.used_at.is_(None))
        .order_by(SecurityToken.created_at.desc())
    ).first()


@pytest.fixture
def minted(monkeypatch):
    """Every raw token issued during a test, in order.

    Wraps `auth_email.issue` rather than reading the database, because the raw
    value is deliberately not stored anywhere. This is the only way to hold a
    working link, which is exactly the guarantee under test.
    """
    captured: list[tuple[TokenPurpose, str]] = []
    original = auth_email.issue

    def spy(db, user, purpose, **kwargs):
        token, raw = original(db, user, purpose, **kwargs)
        captured.append((purpose, raw))
        return token, raw

    monkeypatch.setattr(auth_email, "issue", spy)
    return captured


def _latest(minted, purpose: TokenPurpose) -> str:
    for kind, raw in reversed(minted):
        if kind is purpose:
            return raw
    raise AssertionError(f"no {purpose} token was issued")


# ------------------------------------------------------------------- signup


def test_signing_up_queues_a_verification_email(client, db_session, minted):
    _signup(client)

    messages = _queued(db_session)
    assert len(messages) == 1
    assert messages[0].to_email == "alex@example.com"
    assert messages[0].state is EmailState.QUEUED
    assert _latest(minted, TokenPurpose.EMAIL_VERIFICATION)


def test_signing_up_does_not_hand_back_a_session(client, db_session):
    """An account that cannot sign in must not be handed a token by signup.

    Returning one here while `/login` refuses the same account would be two
    rules disagreeing, and the one that let people in would be the one that
    mattered.
    """
    body = _signup(client)

    assert "token" not in body
    assert body["verification_required"] is True
    assert body["email"] == "alex@example.com"
    assert "confirmation link" in body["detail"]
    assert db_session.scalars(select(User)).one().email_verified_at is None


def test_an_unconfirmed_account_cannot_sign_in(client, db_session):
    """The rule. A correct password is not enough on its own."""
    _signup(client)

    response = client.post(
        "/v1/auth/login", json={"email": "alex@example.com", "password": "hunter2hunter2"}
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == auth_routes.EMAIL_UNVERIFIED
    assert "Confirm your email address" in detail["message"]


def test_confirming_the_address_is_what_lets_somebody_in(client, db_session, minted):
    _signup(client)
    assert (
        client.post(
            "/v1/auth/login", json={"email": "alex@example.com", "password": "hunter2hunter2"}
        ).status_code
        == 403
    )

    _confirm(client, minted, db_session)

    response = client.post(
        "/v1/auth/login", json={"email": "alex@example.com", "password": "hunter2hunter2"}
    )
    assert response.status_code == 200
    assert response.json()["token"]


def test_the_wrong_password_on_an_unconfirmed_account_says_nothing_about_it(
    client, db_session
):
    """The confirmation check comes AFTER the password, and that ordering matters.

    Refusing on the address alone would answer "does this account exist, and is
    it unconfirmed?" to anybody who typed the address - the enumeration hole the
    rest of this module is built to avoid. Reaching the confirmation check means
    the password was right, so the caller already knew the account existed.
    """
    _signup(client)

    response = client.post(
        "/v1/auth/login", json={"email": "alex@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


def test_a_banned_unconfirmed_account_is_told_about_the_ban(client, db_session):
    """The ban is the real answer; "confirm your address" would be a false lead."""
    from app.models.user import AccountStatus

    _signup(client)
    user = db_session.scalars(select(User)).one()
    user.account_status = AccountStatus.BANNED
    db_session.commit()

    response = client.post(
        "/v1/auth/login", json={"email": "alex@example.com", "password": "hunter2hunter2"}
    )

    assert response.status_code == 403
    assert "banned" in response.json()["detail"]


def test_a_resend_still_works_for_an_account_that_cannot_sign_in(client, db_session, minted):
    """This is the way out of a blocked sign-in, so it must not need a session."""
    _signup(client)
    before = _latest(minted, TokenPurpose.EMAIL_VERIFICATION)

    response = client.post(
        "/v1/auth/verify-email/resend", json={"email": "alex@example.com"}
    )

    assert response.status_code == 202
    assert _latest(minted, TokenPurpose.EMAIL_VERIFICATION) != before


def test_a_verification_link_confirms_the_address(client, db_session, minted):
    _signup(client)
    raw = _latest(minted, TokenPurpose.EMAIL_VERIFICATION)

    response = client.post("/v1/auth/verify-email", json={"token": raw})

    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert response.json()["email_changed"] is False
    db_session.expire_all()
    assert db_session.scalars(select(User)).one().email_verified_at is not None


def test_a_verification_link_works_exactly_once(client, db_session, minted):
    _signup(client)
    raw = _latest(minted, TokenPurpose.EMAIL_VERIFICATION)

    assert client.post("/v1/auth/verify-email", json={"token": raw}).status_code == 200
    second = client.post("/v1/auth/verify-email", json={"token": raw})

    assert second.status_code == 410
    assert "already been used" in second.json()["detail"]


def test_an_expired_verification_link_says_so(client, db_session, minted):
    _signup(client)
    raw = _latest(minted, TokenPurpose.EMAIL_VERIFICATION)
    token = db_session.scalars(select(SecurityToken)).one()
    token.expires_at = auth_email.utcnow() - timedelta(minutes=1)
    db_session.commit()

    response = client.post("/v1/auth/verify-email", json={"token": raw})

    assert response.status_code == 410
    assert "expired" in response.json()["detail"]


def test_a_made_up_link_is_refused_without_a_hint(client, db_session):
    _signup(client)
    response = client.post("/v1/auth/verify-email", json={"token": "not-a-real-token"})

    assert response.status_code == 400
    assert "not valid" in response.json()["detail"]


def test_the_raw_token_is_never_stored(client, db_session, minted):
    """A database dump must not be a set of working links."""
    _signup(client)
    raw = _latest(minted, TokenPurpose.EMAIL_VERIFICATION)
    token = db_session.scalars(select(SecurityToken)).one()

    assert token.token_hash != raw
    assert raw not in token.token_hash
    assert len(token.token_hash) == 64


# -------------------------------------------------------------------- resend


def test_a_resend_issues_a_new_link_and_kills_the_old_one(client, db_session, minted):
    _signup(client)
    first = _latest(minted, TokenPurpose.EMAIL_VERIFICATION)

    response = client.post(
        "/v1/auth/verify-email/resend", json={"email": "alex@example.com"}
    )
    assert response.status_code == 202
    second = _latest(minted, TokenPurpose.EMAIL_VERIFICATION)
    assert second != first

    # The superseded link is dead; the new one works.
    assert client.post("/v1/auth/verify-email", json={"token": first}).status_code == 410
    assert client.post("/v1/auth/verify-email", json={"token": second}).status_code == 200


def test_a_resend_says_the_same_thing_for_an_address_we_do_not_know(client, db_session):
    """Any difference here is a way to test whether an address is registered."""
    _signup(client)

    known = client.post("/v1/auth/verify-email/resend", json={"email": "alex@example.com"})
    unknown = client.post("/v1/auth/verify-email/resend", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_nothing_is_queued_for_an_address_we_do_not_know(client, db_session):
    client.post("/v1/auth/verify-email/resend", json={"email": "nobody@example.com"})
    assert _queued(db_session) == []


def test_a_verified_account_is_not_sent_another_link(client, db_session, minted):
    """Otherwise this endpoint is a way to post mail at any registered address."""
    _signup(client)
    _confirm(client, minted, db_session)
    before = len(_queued(db_session))

    client.post("/v1/auth/verify-email/resend", json={"email": "alex@example.com"})

    assert len(_queued(db_session)) == before


# ---------------------------------------------------------- forgotten password


def test_forgot_password_queues_a_reset_for_a_real_account(client, db_session, minted):
    _signup(client)
    response = client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})

    assert response.status_code == 202
    assert _latest(minted, TokenPurpose.PASSWORD_RESET)
    assert any("Reset" in message.subject for message in _queued(db_session))


def test_forgot_password_answers_identically_for_an_unknown_address(client, db_session):
    _signup(client)

    known = client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    unknown = client.post("/v1/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_a_reset_for_an_unconfirmed_account_also_confirms_the_address(
    client, db_session, minted
):
    """Clicking a link in the inbox proves the inbox, whichever link it was.

    Somebody who never opened their confirmation email but can complete a
    password reset has demonstrated exactly the thing confirmation asks for.
    Making them go and find the other email as well would be ceremony, and
    would leave them still unable to sign in with the password they just set.
    """
    _signup(client)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    raw = _latest(minted, TokenPurpose.PASSWORD_RESET)

    response = client.post(
        "/v1/auth/reset-password", json={"token": raw, "new_password": "brand-new-secret"}
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.scalars(select(User)).one().email_verified_at is not None
    # And the account can now sign in normally.
    assert (
        client.post(
            "/v1/auth/login",
            json={"email": "alex@example.com", "password": "brand-new-secret"},
        ).status_code
        == 200
    )


def test_a_reset_link_sets_the_password_and_signs_the_person_in(client, db_session, minted):
    _signup(client)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    raw = _latest(minted, TokenPurpose.PASSWORD_RESET)

    response = client.post(
        "/v1/auth/reset-password", json={"token": raw, "new_password": "brand-new-secret"}
    )

    assert response.status_code == 200
    assert response.json()["token"]
    db_session.expire_all()
    user = db_session.scalars(select(User)).one()
    assert verify_password("brand-new-secret", user.password_hash)
    assert not verify_password("hunter2hunter2", user.password_hash)


def test_a_reset_link_works_exactly_once(client, db_session, minted):
    _signup(client)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    raw = _latest(minted, TokenPurpose.PASSWORD_RESET)

    first = client.post(
        "/v1/auth/reset-password", json={"token": raw, "new_password": "first-password"}
    )
    second = client.post(
        "/v1/auth/reset-password", json={"token": raw, "new_password": "second-password"}
    )

    assert first.status_code == 200
    assert second.status_code == 410
    db_session.expire_all()
    user = db_session.scalars(select(User)).one()
    assert verify_password("first-password", user.password_hash)


def test_using_a_reset_kills_every_other_outstanding_one(client, db_session, minted):
    """An older link still sitting in an inbox must not be a second way in."""
    _signup(client)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    first = _latest(minted, TokenPurpose.PASSWORD_RESET)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    second = _latest(minted, TokenPurpose.PASSWORD_RESET)

    # Only the newest works at all - issuing supersedes.
    assert (
        client.post(
            "/v1/auth/reset-password", json={"token": first, "new_password": "aaaaaaaa1"}
        ).status_code
        == 410
    )
    assert (
        client.post(
            "/v1/auth/reset-password", json={"token": second, "new_password": "bbbbbbbb1"}
        ).status_code
        == 200
    )


def test_an_expired_reset_link_says_so(client, db_session, minted):
    _signup(client)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    raw = _latest(minted, TokenPurpose.PASSWORD_RESET)
    token = _token_from(db_session, TokenPurpose.PASSWORD_RESET)
    token.expires_at = auth_email.utcnow() - timedelta(seconds=1)
    db_session.commit()

    response = client.post(
        "/v1/auth/reset-password", json={"token": raw, "new_password": "brand-new-secret"}
    )

    assert response.status_code == 410
    assert "expired" in response.json()["detail"]


def test_a_short_password_is_refused_before_the_token_is_spent(client, db_session, minted):
    """A rejected password must not cost somebody their only working link."""
    _signup(client)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    raw = _latest(minted, TokenPurpose.PASSWORD_RESET)

    assert (
        client.post(
            "/v1/auth/reset-password", json={"token": raw, "new_password": "short"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/auth/reset-password", json={"token": raw, "new_password": "long-enough-now"}
        ).status_code
        == 200
    )


def test_a_reset_token_is_not_accepted_as_a_verification_token(client, db_session, minted):
    """Purposes are separate so a forwarded link cannot do more than it says."""
    _signup(client)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    raw = _latest(minted, TokenPurpose.PASSWORD_RESET)

    assert client.post("/v1/auth/verify-email", json={"token": raw}).status_code == 400


# ------------------------------------------------------------- rate limiting


def test_asking_for_too_many_reset_emails_is_refused(client, db_session):
    _signup(client)
    codes = [
        client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"}).status_code
        for _ in range(5)
    ]

    assert codes[:3] == [202, 202, 202]
    assert 429 in codes


def test_a_rate_limited_answer_says_when_to_come_back(client, db_session):
    _signup(client)
    for _ in range(4):
        response = client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_the_limit_is_per_address_not_global(client, db_session):
    """One person exhausting their own allowance must not lock out everybody else."""
    _signup(client)
    _signup(client, email="sam@example.com")
    for _ in range(4):
        client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})

    other = client.post("/v1/auth/forgot-password", json={"email": "sam@example.com"})

    assert other.status_code == 202


def test_a_rate_limited_address_leaks_nothing_about_whether_it_exists(client, db_session):
    _signup(client)
    for _ in range(4):
        known = client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    for _ in range(4):
        unknown = client.post("/v1/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 429
    assert known.json() == unknown.json()


# ----------------------------------------------------------- changing address


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_changing_an_address_does_not_change_it_yet(client, db_session, minted):
    """A typo saved straight onto the account is how somebody is locked out."""
    session = _signed_in(client, minted, db_session)

    response = client.patch(
        "/v1/users/me", json={"email": "new@example.com"}, headers=_auth(session["token"])
    )

    assert response.status_code == 200
    assert response.json()["email"] == "alex@example.com"
    assert response.json()["pending_email"] == "new@example.com"


def test_the_confirmation_goes_to_the_new_address(client, db_session, minted):
    session = _signed_in(client, minted, db_session)
    client.patch(
        "/v1/users/me", json={"email": "new@example.com"}, headers=_auth(session["token"])
    )

    recipients = [message.to_email for message in _queued(db_session)]
    assert "new@example.com" in recipients


def test_confirming_the_new_address_moves_the_account_to_it(client, db_session, minted):
    session = _signed_in(client, minted, db_session)
    client.patch(
        "/v1/users/me", json={"email": "new@example.com"}, headers=_auth(session["token"])
    )
    raw = _latest(minted, TokenPurpose.EMAIL_CHANGE)

    response = client.post("/v1/auth/verify-email", json={"token": raw})

    assert response.status_code == 200
    assert response.json()["email_changed"] is True
    db_session.expire_all()
    user = db_session.scalars(select(User)).one()
    assert user.email == "new@example.com"
    assert user.pending_email is None


def test_a_change_link_works_exactly_once(client, db_session, minted):
    session = _signed_in(client, minted, db_session)
    client.patch(
        "/v1/users/me", json={"email": "new@example.com"}, headers=_auth(session["token"])
    )
    raw = _latest(minted, TokenPurpose.EMAIL_CHANGE)

    assert client.post("/v1/auth/verify-email", json={"token": raw}).status_code == 200
    assert client.post("/v1/auth/verify-email", json={"token": raw}).status_code == 410


def test_an_address_already_taken_is_refused_up_front(client, db_session, minted):
    session = _signed_in(client, minted, db_session)
    _signup(client, email="sam@example.com")

    response = client.patch(
        "/v1/users/me", json={"email": "sam@example.com"}, headers=_auth(session["token"])
    )

    assert response.status_code == 409


def test_asking_for_the_current_address_cancels_a_pending_change(
    client, db_session, minted
):
    session = _signed_in(client, minted, db_session)
    client.patch(
        "/v1/users/me", json={"email": "new@example.com"}, headers=_auth(session["token"])
    )
    raw = _latest(minted, TokenPurpose.EMAIL_CHANGE)

    response = client.patch(
        "/v1/users/me", json={"email": "alex@example.com"}, headers=_auth(session["token"])
    )

    assert response.json()["pending_email"] is None
    # The link that was in flight is dead, so a change somebody thought better
    # of cannot still land a week later.
    assert client.post("/v1/auth/verify-email", json={"token": raw}).status_code == 410


def test_the_rest_of_the_profile_still_saves_alongside_an_address_change(
    client, db_session, minted
):
    session = _signed_in(client, minted, db_session)

    response = client.patch(
        "/v1/users/me",
        json={"email": "new@example.com", "display_name": "Alexandra"},
        headers=_auth(session["token"]),
    )

    assert response.json()["display_name"] == "Alexandra"
    assert response.json()["email"] == "alex@example.com"


# ------------------------------------------------------------ what we can send


def test_the_delivery_endpoint_reports_the_outbox_when_there_is_no_smtp(
    client, monkeypatch
):
    """The settings page must never claim mail is going out when it is not.

    The sender is forced rather than left to whatever `.env` happens to hold.
    Reading the ambient configuration made this test pass only on machines with
    no SMTP set up, and fail the moment a developer configured a real relay -
    which is exactly when they would least want a mystery failure.
    """
    from app.services import email as email_module

    sender = email_module.EmailSender()
    sender.host = ""
    monkeypatch.setattr(email_module, "_sender", sender)

    response = client.get("/v1/auth/email-delivery")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["mode"] == "outbox"
    # Nothing else. The endpoint is public, so it answers whether mail can be
    # sent and volunteers no addresses to whoever asked.
    assert set(body) == {"available", "mode"}


def test_the_delivery_endpoint_reports_smtp_when_it_is_configured(client, monkeypatch):
    from app.services import email as email_module

    sender = email_module.EmailSender()
    sender.host = "mail.example.com"
    monkeypatch.setattr(email_module, "_sender", sender)

    body = client.get("/v1/auth/email-delivery").json()

    assert body["available"] is True
    assert body["mode"] == "smtp"


# ------------------------------------------------------------------- password


def test_an_existing_password_is_still_changed_the_old_way(client, db_session, minted):
    """The signed-in change is untouched by any of this."""
    session = _signed_in(client, minted, db_session)

    response = client.post(
        "/v1/users/me/password",
        json={"current_password": "hunter2hunter2", "new_password": "another-secret"},
        headers=_auth(session["token"]),
    )

    assert response.status_code == 204
    db_session.expire_all()
    assert verify_password("another-secret", db_session.scalars(select(User)).one().password_hash)


def test_a_reset_for_a_banned_account_is_not_sent(client, db_session):
    """It could only ever be a dead end - login refuses a ban outright."""
    from app.models.user import AccountStatus

    _signup(client)
    user = db_session.scalars(select(User)).one()
    user.account_status = AccountStatus.BANNED
    db_session.commit()
    before = len(_queued(db_session))

    response = client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})

    assert response.status_code == 202
    assert len(_queued(db_session)) == before


def test_a_password_hash_never_appears_in_a_queued_email(client, db_session, minted):
    _signup(client)
    client.post("/v1/auth/forgot-password", json={"email": "alex@example.com"})
    user = db_session.scalars(select(User)).one()

    for message in _queued(db_session):
        assert user.password_hash not in (message.text_body or "")
        assert user.password_hash not in (message.html_body or "")

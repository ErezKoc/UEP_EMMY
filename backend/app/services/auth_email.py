"""Issuing and spending the one-time links that email has to carry.

Three flows share one shape, so they share one module: prove an address after
signup, prove a new address before it replaces the old one, and reset a
forgotten password. In each case a long random secret goes out in an email, its
SHA-256 goes into the database, and the link works exactly once inside a
window.

The rules that are easy to get wrong, in one place:

* **Superseding.** Issuing a new token of a purpose revokes every earlier
  unused one of that purpose. Asking for a second password reset because the
  first email has not arrived must not leave two working links; the one in the
  newest email is the one that works.
* **One use.** Spending a token stamps `used_at`. The row is kept rather than
  deleted, because "this link has already been used" is a far more useful
  sentence than "this link is not valid", and only a kept row can tell the two
  apart.
* **Spending invalidates the rest.** A completed password reset revokes every
  other outstanding reset for that account, so an older link found in an inbox
  a week later is dead.
* **No enumeration.** Nothing here reports whether an address belongs to an
  account. The endpoints answer identically either way, and the only difference
  is whether a row is written - which the caller cannot observe.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import generate_link_token, hash_link_token
from app.models.token import SecurityToken, TokenPurpose
from app.models.user import User
from app.services import email_queue
from app.services.email import mask_email
from app.services.email_templates import password_reset, verify_email, verify_new_email

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    """Now, in UTC. One function so every timestamp this module writes agrees."""
    return datetime.now(timezone.utc)


def _now() -> datetime:
    return utcnow()


def _ttl(purpose: TokenPurpose) -> timedelta:
    settings = get_settings()
    if purpose is TokenPurpose.PASSWORD_RESET:
        # Short. For the minutes it lives, this link IS the password.
        return timedelta(minutes=settings.password_reset_ttl_minutes)
    # Long. Proof of an address is not a credential, and a link that dies
    # overnight is one people find expired the next morning.
    return timedelta(hours=settings.verify_email_ttl_hours)


def revoke_outstanding(db: Session, user: User, purpose: TokenPurpose) -> int:
    """Kill every unused token of this purpose for this account.

    Returns how many were revoked. Called before issuing a new one, and again
    after a successful use.
    """
    rows = db.scalars(
        select(SecurityToken).where(
            SecurityToken.user_id == user.id,
            SecurityToken.purpose == purpose,
            SecurityToken.used_at.is_(None),
        )
    ).all()
    stamp = _now()
    for row in rows:
        row.used_at = stamp
    return len(rows)


def issue(
    db: Session,
    user: User,
    purpose: TokenPurpose,
    *,
    new_email: str | None = None,
) -> tuple[SecurityToken, str]:
    """Mint a token. Returns the row and the RAW secret, which is not stored.

    The raw value is handed back exactly once, to be put in an email. Nothing
    else in the system can recover it, which is the point of storing only the
    hash.
    """
    revoke_outstanding(db, user, purpose)
    raw = generate_link_token()
    token = SecurityToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=hash_link_token(raw),
        new_email=new_email,
        expires_at=_now() + _ttl(purpose),
    )
    db.add(token)
    db.flush()
    return token, raw


class TokenProblem(str):
    """Why a token was refused, as a short machine-readable word.

    A string rather than an exception because every caller wants to turn it
    into a specific message for the person holding the link - "this has
    expired" and "this has already been used" need different pages, and a
    single "invalid" would send somebody hunting for a link that worked fine
    and was simply spent.
    """


INVALID = TokenProblem("invalid")
EXPIRED = TokenProblem("expired")
USED = TokenProblem("used")


def find(
    db: Session, raw: str, purpose: TokenPurpose
) -> tuple[SecurityToken | None, TokenProblem | None]:
    """Look a raw token up. Returns (token, None) or (None-ish, why not).

    A used or expired token is returned alongside its problem, so a caller can
    still say which account it belonged to if it ever needs to; nothing in the
    API does, and nothing should.
    """
    if not raw or not raw.strip():
        return None, INVALID
    token = db.scalars(
        select(SecurityToken).where(
            SecurityToken.token_hash == hash_link_token(raw.strip()),
            SecurityToken.purpose == purpose,
        )
    ).first()
    if token is None:
        return None, INVALID
    if token.is_used:
        return token, USED
    if token.is_expired():
        return token, EXPIRED
    return token, None


def spend(db: Session, token: SecurityToken) -> None:
    """Mark a token used, and revoke every sibling of the same purpose.

    Both halves matter. Without the first, a link works forever; without the
    second, an older email still in an inbox is a second working link to the
    same account.
    """
    token.used_at = _now()
    user = db.get(User, token.user_id)
    if user is not None:
        revoke_outstanding(db, user, token.purpose)


# ------------------------------------------------------------------- sending


def send_verification(db: Session, user: User) -> bool:
    """Queue "confirm your address" for the account's current address.

    Returns whether anything was queued. Does not commit - the caller owns the
    transaction, so a signup that fails to save cannot leave a verification
    email behind for an account that does not exist.
    """
    if not user.email:
        return False
    token, raw = issue(db, user, TokenPurpose.EMAIL_VERIFICATION)
    queued = email_queue.enqueue_security_email(
        db,
        to=user.email,
        rendered=verify_email(recipient_name=user.display_name, token=raw),
        # The token id, not the user id: a resend is a new token and therefore a
        # new message, which is the whole point of asking for one. Keying on the
        # account would make the second request a silent no-op.
        dedupe_key=f"verify-email:{token.id}",
        user=user,
    )
    logger.info("Queued an address verification for %s.", mask_email(user.email))
    return queued is not None


def send_email_change(db: Session, user: User, new_email: str) -> bool:
    """Queue "confirm your new address", sent TO the new address.

    Sent to the new address rather than the old one on purpose: the question
    being asked is "can you read this inbox", and only the new inbox can answer
    it. The account keeps its current address until the link is used.
    """
    token, raw = issue(db, user, TokenPurpose.EMAIL_CHANGE, new_email=new_email)
    queued = email_queue.enqueue_security_email(
        db,
        to=new_email,
        rendered=verify_new_email(
            recipient_name=user.display_name, token=raw, new_email=new_email
        ),
        dedupe_key=f"verify-new-email:{token.id}",
        user=user,
    )
    logger.info("Queued a new-address verification for %s.", mask_email(new_email))
    return queued is not None


def send_password_reset(db: Session, user: User) -> bool:
    """Queue a reset link. Only ever called for an account that exists.

    The endpoint above this answers the same way whether or not the address is
    registered; this function is simply not reached in the second case, which
    is what keeps the two responses indistinguishable.
    """
    if not user.email:
        return False
    token, raw = issue(db, user, TokenPurpose.PASSWORD_RESET)
    queued = email_queue.enqueue_security_email(
        db,
        to=user.email,
        rendered=password_reset(recipient_name=user.display_name, token=raw),
        dedupe_key=f"password-reset:{token.id}",
        user=user,
    )
    logger.info("Queued a password reset for %s.", mask_email(user.email))
    return queued is not None

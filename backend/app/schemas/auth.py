from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.user import CurrentUserRead


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    # Deliberately not `UserRole`: admin accounts must never be self-registered.
    role: Literal[UserRole.OWNER, UserRole.VETERINARIAN] = UserRole.OWNER
    # Veterinarian-only profile fields; ignored for pet owners.
    clinic_name: str | None = Field(default=None, max_length=255)
    license_number: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: CurrentUserRead


class SignupResponse(BaseModel):
    """What signing up returns now that an unconfirmed account cannot sign in.

    Deliberately NOT an `AuthResponse`. Handing back a working session at the
    end of signup, while `/login` refuses the same account until its address is
    confirmed, would be two rules disagreeing about the same question - and the
    one that let people in would be the one that mattered.

    Carries the address so the page can say "we have sent a link to <this>",
    which is the single most useful thing to show somebody about to go and look
    for it.
    """

    email: EmailStr
    #: Always true today. A field rather than an implication so a client can
    #: branch on it, and so relaxing the rule later does not need a new shape.
    verification_required: bool = True
    detail: str


# ------------------------------------------------- email verification & resets


class TokenPayload(BaseModel):
    """A raw link token, as it came out of an email."""

    # Long enough to hold `secrets.token_urlsafe(32)` with room to spare, and
    # bounded so a multi-megabyte "token" cannot be posted at the lookup.
    token: str = Field(min_length=1, max_length=512)


class ResetPasswordRequest(TokenPayload):
    new_password: str = Field(min_length=8, max_length=128)


class EmailRequest(BaseModel):
    """An address somebody typed, for a resend or a forgotten password.

    Answered identically whether or not it belongs to an account - see the
    endpoints. The field exists to be validated as an address, not to be
    confirmed as a user.
    """

    email: EmailStr


class AcceptedResponse(BaseModel):
    """The deliberately uninformative answer to an unauthenticated request.

    One message for "we have sent you a link" and for "there is no such
    account", because any difference between the two - the words, the status
    code, even the response time - is a way to test whether an address is
    registered here.
    """

    detail: str


class EmailVerificationResult(BaseModel):
    """What a verification link did."""

    #: The address now on the account.
    email: EmailStr
    verified: bool
    #: True when this link moved the account to a new address, rather than
    #: confirming the one it already had.
    email_changed: bool = False
    detail: str


class EmailDeliveryStatus(BaseModel):
    """Whether this deployment can actually send email.

    Reported to the settings page so nobody is told an email is on its way by
    an installation that has no mail server. `available` is the only field the
    interface should branch on; `mode` is there so an operator reading the API
    can tell which backend answered.
    """

    #: True only when SMTP is configured. False means messages go to the local
    #: outbox: they are written down, and they do not reach an inbox.
    available: bool
    #: "smtp" or "outbox".
    mode: str

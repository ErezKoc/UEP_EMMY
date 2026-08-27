"""Signing up, signing in, and the email flows that keep an account reachable.

Three properties the unauthenticated routes here are built around.

**No account enumeration.** `/forgot-password` and `/verify-email/resend`
answer identically whether or not the address belongs to an account. Somebody
who can tell the two apart has a way to test any address against this platform,
and a veterinary practice's client list is exactly the sort of thing worth
testing. The work differs behind the scenes; the answer does not.

**Rate limits.** Every route that causes an email to be sent is limited, per
address and per caller. Without that, one script turns this API into a way to
post mail at somebody, and the platform's sending reputation is spent on it.

**Nothing waits on SMTP.** These endpoints queue; the background sweep delivers.
A mail server that is down makes a message late, never a signup slow.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import EMAIL_UNVERIFIED, get_current_user, suspension_message
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter, key_for
from app.core.security import create_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User, UserRole
from app.models.token import TokenPurpose
from app.schemas import AuthResponse, CurrentUserRead, LoginRequest, SignupRequest
from app.schemas.auth import (
    AcceptedResponse,
    EmailDeliveryStatus,
    EmailRequest,
    EmailVerificationResult,
    ResetPasswordRequest,
    SignupResponse,
    TokenPayload,
)
from app.services import auth_email

router = APIRouter()

#: Per address. Three verification or reset emails an hour is more than anybody
#: needs and far less than a mail-bomb: the honest case is "it did not arrive,
#: try again", which is one or two clicks, not thirty.
_EMAIL_LIMITER = RateLimiter(limit=3, window_seconds=3600)
#: Per caller. Stops one client walking a list of addresses at one request each,
#: which the per-address limiter alone would happily allow.
_CLIENT_LIMITER = RateLimiter(limit=20, window_seconds=3600)
#: Reset attempts, per token. A token is 256 bits of randomness, so this is not
#: what makes guessing infeasible - it is here so a client that has found a
#: token cannot use this endpoint to test passwords or hammer the database.
_RESET_LIMITER = RateLimiter(limit=10, window_seconds=900)

#: The single answer both enumeration-sensitive routes give.
_SENT_IF_EXISTS = (
    "If that address has an account with us, we have sent it an email. "
    "Check your inbox, and your spam folder."
)

#: `EMAIL_UNVERIFIED` is imported from `deps`, which also raises it - see there.
#:
#: `/login` answers 403 for two unrelated reasons, a banned account and an
#: unconfirmed address, and they need opposite endings: one is final, the other
#: is a link away from being fixed. Matching on the message text would tie the
#: interface to the wording, so the code travels beside it.


def _client_key(request: Request) -> str:
    """Who is calling, as well as this deployment can tell.

    `request.client.host` is the proxy's address when there is a proxy in
    front, which would put every caller in one bucket. That is a deliberate
    limitation rather than an oversight: trusting `X-Forwarded-For` without
    knowing the proxy is worse, because anybody can set it and each forged
    value is a fresh bucket - which is the limiter switched off.
    """
    client = request.client
    return key_for("client", client.host if client else "unknown")


def guard_email_rate(request: Request, address: str, *, action: str) -> None:
    """Refuse a request that is asking for too much email, too fast.

    Raises 429 with a Retry-After. The message deliberately says nothing about
    whether the address exists.
    """
    address_key = key_for(f"{action}:email", address)
    client_key = _client_key(request)
    if not _EMAIL_LIMITER.allow(address_key) or not _CLIENT_LIMITER.allow(client_key):
        retry = max(
            _EMAIL_LIMITER.retry_after(address_key),
            _CLIENT_LIMITER.retry_after(client_key),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests for this address. Please wait a few minutes.",
            headers={"Retry-After": str(retry)},
        )


def reset_rate_limits() -> None:
    """Clear every limiter. For tests, which would otherwise leak state."""
    _EMAIL_LIMITER.reset()
    _CLIENT_LIMITER.reset()
    _RESET_LIMITER.reset()


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    """Create an account. Does NOT sign anybody in.

    The address has to be confirmed first, so there is no session to hand back
    yet - see `SignupResponse`.
    """
    email = payload.email.lower()
    exists = db.scalars(select(User).where(func.lower(User.email) == email)).first()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    is_vet = payload.role == UserRole.VETERINARIAN
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        clinic_name=payload.clinic_name if is_vet else None,
        license_number=payload.license_number if is_vet else None,
    )
    db.add(user)
    db.flush()

    # Queued inside the signup transaction, so an account that fails to save
    # cannot leave a verification link behind for an account that never existed.
    #
    # This link is the ONLY way into the account: `/login` refuses it until the
    # address is confirmed. With no SMTP server the message still exists as a
    # file - `python -m app.scripts.outbox --links` - so a local deployment is
    # not locked out, it just reads its mail differently.
    auth_email.send_verification(db, user)

    db.commit()
    db.refresh(user)

    return SignupResponse(
        email=user.email,
        verification_required=True,
        detail=(
            f"Account created. We have sent a confirmation link to {user.email}. "
            "Open it to finish setting up your account and sign in."
        ),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.lower()
    user = db.scalars(select(User).where(func.lower(User.email) == email)).first()
    # Same error for "no such user" and "wrong password" so the endpoint
    # doesn't reveal which emails are registered.
    if (
        user is None
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    # A ban ends access entirely; a suspension still allows signing in so the
    # member can read the reason and wait it out.
    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=suspension_message(user))
    # An unconfirmed address cannot sign in.
    #
    # Checked AFTER the password, deliberately. Refusing on the address alone
    # would answer "does this account exist and is it unconfirmed?" to anybody
    # who typed the address, which is the enumeration hole the rest of this
    # module is built to avoid. Reaching this line means the password was right,
    # so the caller already knows the account exists.
    #
    # Checked after the ban too: a banned account is not owed a verification
    # link, and "confirm your address" would be a false lead for somebody whose
    # real problem is that they are banned.
    if not user.email_is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": EMAIL_UNVERIFIED,
                "message": (
                    "Confirm your email address before signing in. We sent you a link "
                    "when you signed up - ask for another if you cannot find it."
                ),
            },
        )
    return AuthResponse(token=create_token(user.id), user=CurrentUserRead.model_validate(user))


@router.get("/me", response_model=CurrentUserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the user for the presented token (used to restore sessions)."""
    return current_user


# --------------------------------------------------------- proving an address


@router.post("/verify-email", response_model=EmailVerificationResult)
def verify_email(payload: TokenPayload, db: Session = Depends(get_db)) -> EmailVerificationResult:
    """Spend a verification link.

    Handles both kinds in one route because the person clicking cannot tell
    them apart and should not have to: a link from signup confirms the address
    already on the account, a link from a requested change moves the account to
    the new one.

    Unauthenticated on purpose. The link is very often opened in a different
    browser from the one that is signed in - a phone, a work machine - and
    requiring a session would make the common case fail.
    """
    token, problem = auth_email.find(db, payload.token, TokenPurpose.EMAIL_VERIFICATION)
    if problem is not None:
        # Not a verification token, or not usable as one. Try the change flow
        # before giving up: the two are separate purposes and the same link
        # cannot be both, so at most one of these lookups can succeed.
        change, change_problem = auth_email.find(db, payload.token, TokenPurpose.EMAIL_CHANGE)
        if change is not None:
            token, problem = change, change_problem
    if problem is not None:
        raise HTTPException(status_code=_status_for(problem), detail=_message_for(problem))

    if token is None:  # unreachable: `problem is None` implies a row
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_message_for("invalid"))
    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That account no longer exists."
        )

    changed = False
    if token.purpose is TokenPurpose.EMAIL_CHANGE and token.new_email:
        taken = db.scalars(
            select(User).where(
                func.lower(User.email) == token.new_email.lower(), User.id != user.id
            )
        ).first()
        if taken is not None:
            # Somebody else claimed the address between the request and the
            # click. The token is spent either way - it has done all it can -
            # and the account keeps the address it has.
            auth_email.spend(db, token)
            user.pending_email = None
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That address now belongs to another account. Your address is unchanged.",
            )
        user.email = token.new_email.lower()
        user.pending_email = None
        changed = True

    user.email_verified_at = auth_email.utcnow()
    auth_email.spend(db, token)
    db.commit()
    db.refresh(user)

    return EmailVerificationResult(
        email=user.email,
        verified=True,
        email_changed=changed,
        detail=(
            "Your new email address is confirmed and is now the address you sign in with."
            if changed
            else "Thank you - your email address is confirmed."
        ),
    )


@router.post(
    "/verify-email/resend",
    response_model=AcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resend_verification(
    payload: EmailRequest, request: Request, db: Session = Depends(get_db)
) -> AcceptedResponse:
    """Send another verification link, without saying whether one was needed.

    Unauthenticated, because the person who cannot prove their address is
    frequently the person who cannot get past a sign-in form either. The cost
    is that it must not confirm an address exists - hence the fixed answer.
    """
    address = payload.email.lower()
    guard_email_rate(request, address, action="resend")

    user = db.scalars(select(User).where(func.lower(User.email) == address)).first()
    # An account with a proven address gets nothing: re-proving it is busywork,
    # and sending anyway would make this endpoint a way to post mail to any
    # address that happens to be registered. This is also the route out of a
    # blocked sign-in, so it has to work for an account that cannot log in.
    if user is not None and not user.email_is_verified:
        auth_email.send_verification(db, user)
        db.commit()
    return AcceptedResponse(detail=_SENT_IF_EXISTS)


# --------------------------------------------------------- forgotten password


@router.post(
    "/forgot-password", response_model=AcceptedResponse, status_code=status.HTTP_202_ACCEPTED
)
def forgot_password(
    payload: EmailRequest, request: Request, db: Session = Depends(get_db)
) -> AcceptedResponse:
    """Ask for a reset link. Answers the same way for any address."""
    address = payload.email.lower()
    guard_email_rate(request, address, action="reset")

    user = db.scalars(select(User).where(func.lower(User.email) == address)).first()
    # A banned account gets no link. Resetting the password would not get them
    # back in - login refuses a ban outright - so the email could only ever be
    # a confusing dead end.
    if user is not None and not user.is_banned:
        auth_email.send_password_reset(db, user)
        db.commit()
    return AcceptedResponse(detail=_SENT_IF_EXISTS)


@router.post("/reset-password", response_model=AuthResponse)
def reset_password(
    payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)
) -> AuthResponse:
    """Spend a reset link and set a new password.

    Signs the person in on success. They have just proved they hold the inbox
    and chosen a password; sending them to a login form to type it again is a
    step that protects nobody.
    """
    if not _RESET_LIMITER.allow(_client_key(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a few minutes.",
            headers={"Retry-After": str(_RESET_LIMITER.retry_after(_client_key(request)))},
        )

    token, problem = auth_email.find(db, payload.token, TokenPurpose.PASSWORD_RESET)
    if problem is not None:
        raise HTTPException(status_code=_status_for(problem), detail=_message_for(problem))

    if token is None:  # unreachable: `problem is None` implies a row
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_message_for("invalid"))
    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That account no longer exists."
        )
    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=suspension_message(user))

    user.password_hash = hash_password(payload.new_password)
    # Reaching this link proves the inbox, which is the same thing a
    # verification link proves. Making somebody click a second email to say so
    # again would be ceremony.
    if user.email_verified_at is None:
        user.email_verified_at = auth_email.utcnow()
    # Spending revokes every other outstanding reset for this account, so an
    # older email still sitting in the inbox is dead.
    auth_email.spend(db, token)
    db.commit()
    db.refresh(user)

    return AuthResponse(token=create_token(user.id), user=CurrentUserRead.model_validate(user))


# ------------------------------------------------------------------ plumbing


def _status_for(problem: str) -> int:
    """410 for a link that was real and is finished; 400 for one that never was.

    The distinction is for the page, not for a machine: "this link has expired"
    and "this link is not valid" send somebody to two different next steps, and
    collapsing them into one status would leave the frontend guessing.
    """
    return status.HTTP_410_GONE if problem in ("expired", "used") else status.HTTP_400_BAD_REQUEST


def _message_for(problem: str) -> str:
    if problem == "expired":
        return "This link has expired. Ask for a new one and we will send another."
    if problem == "used":
        return "This link has already been used. Ask for a new one if you still need it."
    return "This link is not valid. Check you copied the whole address from the email."


@router.get("/email-delivery", response_model=EmailDeliveryStatus)
def email_delivery(response: Response) -> EmailDeliveryStatus:
    """Whether this deployment can send mail at all.

    Public and unauthenticated because the sign-up, resend and forgotten-password
    screens all need it and none of them has a session yet.

    Two booleans and nothing else, deliberately. It used to include the From
    address so the settings page could suggest allow-listing it, which put a
    real address behind an endpoint anybody can call - free to harvest, and of
    no use to the reader, who cannot act on it anyway. Whether mail can be sent
    is the whole question.
    """
    from app.services.email import get_email_sender

    sender = get_email_sender()
    # Configuration, not data: a client may hold it for a while, but not so long
    # that turning SMTP on leaves the interface saying it is off.
    response.headers["Cache-Control"] = "public, max-age=60"
    return EmailDeliveryStatus(
        available=sender.configured,
        mode="smtp" if sender.configured else "outbox",
    )

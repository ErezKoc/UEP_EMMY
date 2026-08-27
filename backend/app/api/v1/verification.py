"""Veterinarian credential verification.

A veterinarian uploads proof of licence; an administrator approves or rejects it.
Only approved accounts get the "Verified veterinarian" badge across the app, which
is what makes professional advice here trustworthy.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_admin, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import User, UserRole, VerificationStatus, VetVerification
from app.models.notification import NotificationKind
from app.schemas import VerificationDecision, VetVerificationRead
from app.services.notifications import notify
from app.services.storage import StorageService, get_storage_service

router = APIRouter()

# Licence documents are usually photos or scans; PDF is accepted too.
_DOCUMENT_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


@router.post("", response_model=VetVerificationRead, status_code=status.HTTP_201_CREATED)
async def submit_verification(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
) -> VetVerification:
    """Submit (or resubmit) licence proof for review."""
    if current_user.role != UserRole.VETERINARIAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only veterinarian accounts can request verification.",
        )
    if current_user.verification_status == VerificationStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Your account is already verified.",
        )
    if current_user.verification_status == VerificationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A verification request is already under review.",
        )

    settings = get_settings()
    if file.content_type not in _DOCUMENT_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported document type {file.content_type!r}. "
            f"Allowed: {', '.join(sorted(_DOCUMENT_CONTENT_TYPES))}.",
        )
    document_bytes = await file.read()
    if not document_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    if len(document_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Document exceeds the {settings.max_upload_mb} MB upload limit.",
        )

    key = storage.build_key("verifications", file.filename or "document")
    stored = storage.put_object(key, document_bytes, file.content_type)

    verification = VetVerification(
        user_id=current_user.id,
        document_key=stored.key,
        document_url=stored.url,
        license_number=current_user.license_number,
        status=VerificationStatus.PENDING,
    )
    current_user.verification_status = VerificationStatus.PENDING
    db.add(verification)
    db.commit()
    db.refresh(verification)
    _ = verification.user  # load for serialization before the session closes
    return verification


@router.get("/me", response_model=list[VetVerificationRead])
def my_verifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[VetVerification]:
    """The caller's own submissions, newest first (empty when never submitted)."""
    statement = (
        select(VetVerification)
        .options(
            selectinload(VetVerification.user),
            selectinload(VetVerification.reviewed_by),
        )
        .where(VetVerification.user_id == current_user.id)
        .order_by(VetVerification.created_at.desc())
    )
    return list(db.scalars(statement).all())


@router.get("", response_model=list[VetVerificationRead])
def list_verifications(
    status_filter: VerificationStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[VetVerification]:
    """Review queue: all submissions, oldest first so the longest wait is handled first."""
    statement = (
        select(VetVerification)
        .options(
            selectinload(VetVerification.user),
            selectinload(VetVerification.reviewed_by),
        )
        .order_by(VetVerification.created_at)
    )
    if status_filter is not None:
        statement = statement.where(VetVerification.status == status_filter)
    return list(db.scalars(statement).all())


@router.patch("/{verification_id}", response_model=VetVerificationRead)
def decide_verification(
    verification_id: uuid.UUID,
    payload: VerificationDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> VetVerification:
    """Approve, reject, or correct a decision, mirroring the result onto the account.

    A decision is not final: an approval given by mistake can be revoked by
    deciding the same submission again the other way. Only the veterinarian's
    most recent submission is decidable, so the account status always reflects
    the newest record.
    """
    if payload.status not in {VerificationStatus.VERIFIED, VerificationStatus.REJECTED}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A decision must be either 'verified' or 'rejected'.",
        )

    verification = db.get(VetVerification, verification_id)
    if verification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification {verification_id} not found.",
        )
    if verification.status == payload.status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request is already {verification.status.value}.",
        )

    latest_id = db.scalars(
        select(VetVerification.id)
        .where(VetVerification.user_id == verification.user_id)
        .order_by(VetVerification.created_at.desc())
        .limit(1)
    ).first()
    if latest_id != verification.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A newer submission from this veterinarian supersedes this one; decide that instead.",
        )

    # Whether the badge is being taken away, worked out BEFORE the account is
    # written. A rejection of a submission that was already approved is a
    # revocation, and reading it as a plain rejection would tell a practice
    # their application was turned down when in fact their badge has gone -
    # two different things to explain, and only one of them is news.
    revoked = (
        payload.status == VerificationStatus.REJECTED
        and verification.user.verification_status == VerificationStatus.VERIFIED
    )

    verification.status = payload.status
    verification.review_note = payload.review_note
    verification.reviewed_by_id = admin.id
    verification.reviewed_at = datetime.now(timezone.utc)
    verification.user.verification_status = payload.status

    _announce_decision(db, verification, revoked=revoked)

    db.commit()
    db.refresh(verification)
    # Load both relationships while the session is open so serialization of the
    # submitter and the reviewing admin never triggers a detached lazy load.
    _ = verification.user, verification.reviewed_by
    return verification


def _announce_decision(
    db: Session, verification: VetVerification, *, revoked: bool
) -> None:
    """Tell the veterinarian what was decided about their licence.

    Inside the same transaction as the decision, so a decision that fails to
    save cannot leave an announcement behind saying it was made.

    The review note is included where there is one. A rejection without a
    reason is a dead end - the veterinarian cannot tell whether to resubmit a
    clearer scan or to give up - and the note is the only part of this that
    tells them what to do next.
    """
    subject = verification.user
    note = (verification.review_note or "").strip() or None

    if verification.status == VerificationStatus.VERIFIED:
        kind = NotificationKind.VERIFICATION_APPROVED
        title = "Your veterinarian account is verified"
        body = (
            "An administrator has checked your licence document. The verified "
            "veterinarian badge now appears on your profile and beside everything "
            "you post."
        )
    elif revoked:
        kind = NotificationKind.VERIFICATION_REVOKED
        title = "Your verified veterinarian badge has been removed"
        body = (
            "An administrator has withdrawn the verification on your account, so "
            "the verified badge no longer appears beside your name. You can submit "
            "a new licence document for review at any time."
        )
    else:
        kind = NotificationKind.VERIFICATION_REJECTED
        title = "Your verification request was not approved"
        body = (
            "An administrator reviewed your licence document and could not verify "
            "it. You can submit another document for review."
        )
    if note:
        body += f" They said: {note}"

    facts: list[tuple[str, str]] = [("Decision", verification.status.value)]
    if verification.license_number:
        facts.append(("Licence number", verification.license_number))
    if verification.reviewed_at:
        facts.append(("Reviewed", f"{verification.reviewed_at:%d %b %Y}"))

    notify(
        db,
        user=subject,
        kind=kind,
        title=title,
        body=body,
        # Keyed on the submission AND the verdict: a decision reversed later is
        # genuinely new news, and a key naming only the submission would
        # silence the reversal forever.
        dedupe_key=f"verification:{verification.id}:{kind.value}",
        link="/profile",
        email_facts=facts,
    )

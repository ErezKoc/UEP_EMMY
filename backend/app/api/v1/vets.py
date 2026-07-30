from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, UserRole, VerificationStatus
from app.schemas import VeterinarianRead

router = APIRouter()


@router.get("", response_model=list[VeterinarianRead])
def list_veterinarians(
    q: str | None = Query(default=None, max_length=100),
    verified_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[User]:
    statement = select(User).where(User.role == UserRole.VETERINARIAN)
    if verified_only:
        statement = statement.where(User.verification_status == VerificationStatus.VERIFIED)
    if q and (term := q.strip()):
        pattern = f"%{term}%"
        statement = statement.where(
            or_(User.display_name.ilike(pattern), User.clinic_name.ilike(pattern), User.bio.ilike(pattern))
        )
    # Verified professionals first — the directory's value is trustworthy contacts.
    statement = statement.order_by(
        (User.verification_status != VerificationStatus.VERIFIED), User.display_name
    )
    return list(db.scalars(statement).all())

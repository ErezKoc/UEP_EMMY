from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, UserRole, VerificationStatus
from app.schemas import VeterinarianRead
from app.schemas.emergency import EmergencyContactsRead
from app.services.emergency_contacts import EMERGENCY_CONTACTS, EMERGENCY_NOTE

router = APIRouter()


# Declared before the parameterless list route below purely for readability;
# the paths do not collide.
@router.get("/emergency-contacts", response_model=EmergencyContactsRead)
def emergency_contacts() -> EmergencyContactsRead:
    """The numbers to call when no practice is open.

    Served from the backend rather than hard-coded in the client so the numbers
    live next to the source that states each one, and so correcting one is a
    single edit in a file that records where it came from.
    """
    return EmergencyContactsRead(note=EMERGENCY_NOTE, contacts=list(EMERGENCY_CONTACTS))


@router.get("", response_model=list[VeterinarianRead])
def list_veterinarians(
    q: str | None = Query(default=None, max_length=100),
    verified_only: bool = Query(default=False),
    accepting_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[User]:
    statement = select(User).where(User.role == UserRole.VETERINARIAN)
    if verified_only:
        statement = statement.where(User.verification_status == VerificationStatus.VERIFIED)
    if accepting_only:
        statement = statement.where(User.accepts_appointments.is_(True))
    if q and (term := q.strip()):
        pattern = f"%{term}%"
        # Place matters as much as name here: somebody looking for a vet is
        # usually looking for one they can get to, and before the address
        # existed the only way to search was by a clinic name you already knew.
        statement = statement.where(
            or_(
                User.display_name.ilike(pattern),
                User.clinic_name.ilike(pattern),
                User.bio.ilike(pattern),
                User.clinic_city.ilike(pattern),
                User.clinic_postcode.ilike(pattern),
                User.clinic_address_line.ilike(pattern),
            )
        )
    # Verified professionals first — the directory's value is trustworthy contacts.
    statement = statement.order_by(
        (User.verification_status != VerificationStatus.VERIFIED), User.display_name
    )
    return list(db.scalars(statement).all())

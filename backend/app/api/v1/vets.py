import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_active_user, get_current_user
from app.db.session import get_db
from app.models import AvailabilitySlot, User, UserRole, VerificationStatus
from app.schemas import VeterinarianRead
from app.schemas.availability import SlotCreate, SlotRead
from app.schemas.emergency import EmergencyContactsRead
from app.services.clinic_directory import (
    SPECIALTIES,
    distance_km,
    opening_status,
    specialty_labels,
)
from app.services.emergency_contacts import EMERGENCY_CONTACTS, EMERGENCY_NOTE

router = APIRouter()

#: How far ahead "has availability" looks by default.
DEFAULT_AVAILABILITY_WINDOW_DAYS = 14
#: The furthest ahead a practice may publish, and the furthest a search looks.
MAX_HORIZON_DAYS = 180


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


@router.get("/specialties", response_model=list[dict])
def list_specialties() -> list[dict]:
    """The catalogue, so no client has to hold its own copy and drift from it."""
    return [{"value": slug, "label": label} for slug, label in SPECIALTIES.items()]


def _open_slots(vet: User, today: date, horizon: date) -> list[AvailabilitySlot]:
    """This practice's published openings that still have room, soonest first."""
    return sorted(
        (
            slot
            for slot in vet.availability_slots
            if today <= slot.slot_date <= horizon and slot.is_open
        ),
        key=lambda slot: (slot.slot_date, slot.start_time),
    )


def _to_read(
    vet: User,
    *,
    lat: float | None,
    lng: float | None,
    today: date,
    horizon: date,
    moment: datetime | None = None,
) -> VeterinarianRead:
    """One practice, told from where the caller is standing and when.

    Distance, opening status and next opening all depend on the request rather
    than the row, so they are filled in here. None of them is stored: a cached
    "open now" is wrong within the hour.
    """
    data = VeterinarianRead.model_validate(vet)
    data.distance_km = distance_km(lat, lng, vet.clinic_latitude, vet.clinic_longitude)

    status_now = opening_status(vet.clinic_hours_grid, vet.clinic_timezone, moment)
    data.open_now = status_now.is_open
    data.closes_at = status_now.closes_at
    data.opens_at = status_now.opens_at
    data.opens_day = status_now.opens_day

    data.specialties = list(vet.specialties or [])
    data.specialty_labels = specialty_labels(vet.specialties)

    slots = _open_slots(vet, today, horizon)
    data.published_slot_count = len(slots)
    if slots:
        data.next_slot_date = slots[0].slot_date
        data.next_slot_time = slots[0].start_time
    return data


@router.get("", response_model=list[VeterinarianRead])
def list_veterinarians(
    q: str | None = Query(default=None, max_length=100),
    verified_only: bool = Query(default=False),
    accepting_only: bool = Query(default=False),
    #: Where the caller is. Both or neither - a latitude alone locates nothing.
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float | None = Query(default=None, gt=0, le=20_000),
    specialty: list[str] | None = Query(default=None),
    open_now: bool = Query(default=False),
    max_fee: float | None = Query(default=None, ge=0),
    has_availability: bool = Query(default=False),
    availability_days: int = Query(
        default=DEFAULT_AVAILABILITY_WINDOW_DAYS, ge=1, le=MAX_HORIZON_DAYS
    ),
    sort: str = Query(default="relevance", pattern="^(relevance|distance|price|soonest)$"),
    db: Session = Depends(get_db),
) -> list[VeterinarianRead]:
    """The directory, filtered the way somebody actually looks for a vet.

    Every filter here EXCLUDES rather than ranks, and every one of them leaves
    out practices that have not published the thing being filtered on. That is
    the sharp edge of this endpoint and it is deliberate: a clinic with no
    coordinates is not far away, one with no opening grid is not closed, and
    one with no published slots is not fully booked. Ranking those last with a
    made-up value would be the platform inventing facts about businesses that
    never told us anything - so an unfiltered search keeps showing them, and
    turning a filter on is an explicit choice to narrow to practices that have
    answered that question.
    """
    statement = (
        select(User)
        .options(selectinload(User.availability_slots))
        .where(User.role == UserRole.VETERINARIAN)
    )
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
    # A price ceiling is compared against the BOTTOM of the range, because that
    # is the only figure a practice quoting "400-900" has committed to. Using
    # the top would hide every clinic whose most expensive procedure exceeds
    # the budget, which is nearly all of them.
    if max_fee is not None:
        statement = statement.where(
            User.consultation_fee_min.is_not(None), User.consultation_fee_min <= max_fee
        )

    today = date.today()
    horizon = today + timedelta(days=availability_days)
    moment = datetime.now(timezone.utc)

    rows = [
        _to_read(vet, lat=lat, lng=lng, today=today, horizon=horizon, moment=moment)
        for vet in db.scalars(statement).unique().all()
    ]

    wanted = {item for item in (specialty or []) if item in SPECIALTIES}
    if wanted:
        rows = [row for row in rows if wanted.intersection(row.specialties)]
    if open_now:
        # `is True`, not truthiness: `None` here means "no hours published",
        # and a practice we know nothing about must not be presented as one we
        # have confirmed is open.
        rows = [row for row in rows if row.open_now is True]
    if has_availability:
        rows = [row for row in rows if row.published_slot_count > 0]
    if radius_km is not None and lat is not None and lng is not None:
        rows = [
            row for row in rows if row.distance_km is not None and row.distance_km <= radius_km
        ]

    verified_first = lambda row: 0 if row.is_verified_vet else 1  # noqa: E731

    if sort == "distance" and lat is not None and lng is not None:
        # Practices with no coordinates sink to the bottom rather than
        # disappearing - they are still real practices, and this is a sort, not
        # a filter. `radius_km` is how somebody says "only ones you can place".
        rows.sort(key=lambda row: (row.distance_km is None, row.distance_km or 0.0))
    elif sort == "price":
        rows.sort(
            key=lambda row: (
                row.consultation_fee_min is None,
                row.consultation_fee_min or 0.0,
            )
        )
    elif sort == "soonest":
        rows.sort(
            key=lambda row: (
                row.next_slot_date is None,
                row.next_slot_date or date.max,
                row.next_slot_time or datetime.max.time(),
            )
        )
    else:
        # Verified professionals first - the directory's value is trustworthy
        # contacts. Kept as the default so an owner who sets no filters gets
        # the ordering the directory has always had.
        rows.sort(key=lambda row: (verified_first(row), row.display_name.lower()))

    return rows


# ------------------------------------------------------- published openings


def _vet_or_404(db: Session, vet_id: uuid.UUID) -> User:
    vet = db.get(User, vet_id)
    if vet is None or vet.role != UserRole.VETERINARIAN:
        raise HTTPException(status_code=404, detail="Veterinarian not found.")
    return vet


@router.get("/{vet_id}/slots", response_model=list[SlotRead])
def list_slots(
    vet_id: uuid.UUID,
    days: int = Query(default=DEFAULT_AVAILABILITY_WINDOW_DAYS, ge=1, le=MAX_HORIZON_DAYS),
    include_full: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[SlotRead]:
    """The openings this practice has published, soonest first.

    Public, like the rest of the directory: the times a practice advertises are
    advertising. Past slots are never returned - an opening that has gone is
    not availability, and leaving them in would let a stale page send somebody
    to request yesterday.
    """
    vet = _vet_or_404(db, vet_id)
    today = date.today()
    horizon = today + timedelta(days=days)

    chosen = [
        slot
        for slot in vet.availability_slots
        if today <= slot.slot_date <= horizon and (include_full or slot.is_open)
    ]
    chosen.sort(key=lambda slot: (slot.slot_date, slot.start_time))
    return [
        SlotRead(
            **{
                field: getattr(slot, field)
                for field in ("id", "vet_id", "slot_date", "start_time", "end_time", "capacity", "note")
            },
            taken=slot.taken,
            is_open=slot.is_open,
        )
        for slot in chosen
    ]


@router.post("/me/slots", response_model=list[SlotRead], status_code=status.HTTP_201_CREATED)
def publish_slots(
    payload: SlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> list[SlotRead]:
    """Publish an opening, optionally repeating it weekly.

    Only a veterinarian, and only onto their own diary. There is no route for
    publishing on somebody else's behalf: a slot is a practice saying "we are
    free then", and nobody else can say that for them.
    """
    if current_user.role != UserRole.VETERINARIAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a veterinary practice can publish openings.",
        )
    if payload.slot_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a date that has not already passed.",
        )
    if payload.slot_date > date.today() + timedelta(days=MAX_HORIZON_DAYS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Publish openings up to {MAX_HORIZON_DAYS} days ahead.",
        )

    existing = {
        (slot.slot_date, slot.start_time) for slot in current_user.availability_slots
    }
    created: list[AvailabilitySlot] = []
    for week in range(payload.repeat_weeks + 1):
        when = payload.slot_date + timedelta(weeks=week)
        if when > date.today() + timedelta(days=MAX_HORIZON_DAYS):
            break
        # Skipped rather than refused. A practice repeating a Tuesday slot for
        # eight weeks over one that already exists means "make sure these are
        # all published", and failing the whole run over week three would leave
        # them to work out which weeks landed.
        if (when, payload.start_time) in existing:
            continue
        slot = AvailabilitySlot(
            vet_id=current_user.id,
            slot_date=when,
            start_time=payload.start_time,
            end_time=payload.end_time,
            capacity=payload.capacity,
            note=(payload.note or "").strip() or None,
        )
        db.add(slot)
        created.append(slot)
        existing.add((when, payload.start_time))

    db.commit()
    for slot in created:
        db.refresh(slot)
    return [
        SlotRead(
            **{
                field: getattr(slot, field)
                for field in ("id", "vet_id", "slot_date", "start_time", "end_time", "capacity", "note")
            },
            taken=slot.taken,
            is_open=slot.is_open,
        )
        for slot in created
    ]


@router.delete("/me/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_slot(
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Take a published opening down.

    Refused once somebody has been confirmed into it. Withdrawing the slot
    would not cancel their appointment - it would only remove the record of
    what they were booked into, leaving an owner with a confirmation for a time
    the practice no longer shows. Cancelling the appointment is the honest way
    to undo that, and it tells the owner.
    """
    slot = db.get(AvailabilitySlot, slot_id)
    if slot is None or slot.vet_id != current_user.id:
        raise HTTPException(status_code=404, detail="Opening not found.")
    if slot.taken > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Somebody is booked into this opening. Cancel the appointment "
                "instead, so they are told."
            ),
        )
    db.delete(slot)
    db.commit()

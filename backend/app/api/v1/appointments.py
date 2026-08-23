"""Appointment requests: an owner asks, a practice answers.

Every route here is scoped to the two people on the appointment. A veterinarian
sees requests addressed to them and nobody else's; an owner sees their own. The
checks are per-row rather than per-role, because "is a vet" is not the question
— "is THIS appointment's vet" is.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_active_user, get_current_user
from app.db.session import get_db
from app.models import Animal, Reminder, ReminderType, User, UserRole
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDecision,
    AppointmentRead,
)

router = APIRouter()

_LOADED = (
    joinedload(Appointment.owner),
    joinedload(Appointment.vet),
    joinedload(Appointment.animal),
)


def _visible(db: Session, appointment_id: uuid.UUID, user: User) -> Appointment:
    """The appointment, if this user is one of the two people on it."""
    appointment = db.scalar(
        select(Appointment).options(*_LOADED).where(Appointment.id == appointment_id)
    )
    # 404 rather than 403 for someone else's appointment: whether a given id
    # exists is not something an unrelated account should be able to probe.
    if appointment is None or user.id not in (appointment.owner_id, appointment.vet_id):
        raise HTTPException(status_code=404, detail="Appointment not found.")
    return appointment


@router.get("", response_model=list[AppointmentRead])
def list_appointments(
    open_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Appointment]:
    """Whichever side of the appointment the caller is on.

    One route rather than /mine and /inbox: an account can legitimately be both
    (a veterinarian owns pets too), and splitting it would hide one list from
    them depending on which URL they happened to open.
    """
    statement = (
        select(Appointment)
        .options(*_LOADED)
        .where(
            or_(
                Appointment.owner_id == current_user.id,
                Appointment.vet_id == current_user.id,
            )
        )
    )
    if open_only:
        statement = statement.where(Appointment.status == AppointmentStatus.REQUESTED)
    # Unanswered first, then soonest. A practice opening this needs the queue;
    # an owner needs the visit that is coming up.
    statement = statement.order_by(
        (Appointment.status != AppointmentStatus.REQUESTED),
        Appointment.preferred_date,
    )
    return list(db.scalars(statement).unique().all())


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def request_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> Appointment:
    vet = db.get(User, payload.vet_id)
    if vet is None or vet.role != UserRole.VETERINARIAN:
        raise HTTPException(status_code=404, detail="Veterinarian not found.")
    if not vet.accepts_appointments:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This practice is not taking appointment requests here.",
        )
    if vet.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot book an appointment with yourself.",
        )
    # A past date cannot be honoured and the practice would have to decline it,
    # which wastes the one round trip this flow has.
    if payload.preferred_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a date that has not already passed.",
        )

    animal: Animal | None = None
    if payload.animal_id is not None:
        animal = db.get(Animal, payload.animal_id)
        if animal is None or animal.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Pet not found.")

    appointment = Appointment(
        owner_id=current_user.id,
        vet_id=vet.id,
        animal_id=animal.id if animal else None,
        reason=payload.reason.strip(),
        preferred_date=payload.preferred_date,
        preferred_time_note=(payload.preferred_time_note or "").strip() or None,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/{appointment_id}/respond", response_model=AppointmentRead)
def respond_to_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> Appointment:
    """The practice's answer. Only the veterinarian it was sent to may give it."""
    appointment = _visible(db, appointment_id, current_user)
    if appointment.vet_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the practice this was sent to can answer it.",
        )
    if appointment.status is not AppointmentStatus.REQUESTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request has already been {appointment.status.value}.",
        )

    note = (payload.vet_note or "").strip() or None
    appointment.responded_at = datetime.now(timezone.utc)
    appointment.vet_note = note

    if not payload.confirm:
        appointment.status = AppointmentStatus.DECLINED
        db.commit()
        db.refresh(appointment)
        return appointment

    scheduled = payload.scheduled_date or appointment.preferred_date
    if scheduled < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a date that has not already passed.",
        )
    appointment.status = AppointmentStatus.CONFIRMED
    appointment.scheduled_date = scheduled

    # The confirmation is what puts this on the owner's calendar — nothing
    # appears there while a practice has not answered, because a request is not
    # an appointment and a calendar entry says it is.
    if appointment.animal_id is not None:
        practice = appointment.vet.clinic_name or appointment.vet.display_name
        reminder = Reminder(
            title=f"Vet appointment — {practice}"[:150],
            reminder_type=ReminderType.CHECKUP,
            due_date=scheduled,
            notes=_reminder_note(appointment, note),
            animal_id=appointment.animal_id,
            owner_id=appointment.owner_id,
        )
        db.add(reminder)
        db.flush()
        appointment.reminder_id = reminder.id

    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Appointment:
    """Either side may call it off, including after a confirmation.

    Cancelling stays open to a suspended account, unlike requesting: leaving
    somebody unable to withdraw an appointment they can no longer attend helps
    nobody, least of all the practice holding the slot.
    """
    appointment = _visible(db, appointment_id, current_user)
    if appointment.status in (AppointmentStatus.CANCELLED, AppointmentStatus.DECLINED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This request has already been {appointment.status.value}.",
        )

    # The calendar entry goes with it. A reminder for a cancelled appointment is
    # worse than none: the owner turns up.
    if appointment.reminder_id is not None:
        reminder = db.get(Reminder, appointment.reminder_id)
        if reminder is not None:
            db.delete(reminder)
        appointment.reminder_id = None

    appointment.status = AppointmentStatus.CANCELLED
    appointment.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(appointment)
    return appointment


def _reminder_note(appointment: Appointment, vet_note: str | None) -> str:
    """One line, not several.

    This text lands in a reminder, and the calendar page edits a reminder's
    notes in a single-line `<input>`. HTML strips newlines out of an input
    value, so a note written across three lines arrived with them run together
    into one unreadable string - "...three days.You asked for..." - which is
    worse than the same content with something visible between the parts.

    The separator is a dash for that reason. It also survives the calendar's
    ICS and Google Calendar exports unchanged, which a newline does not.
    """
    parts = [f"Reason given: {appointment.reason}"]
    if appointment.scheduled_date != appointment.preferred_date:
        parts.append(
            f"You asked for {appointment.preferred_date:%d %b %Y}; the practice confirmed "
            f"{appointment.scheduled_date:%d %b %Y}."
        )
    if vet_note:
        parts.append(f"From the practice: {vet_note}")
    contact = appointment.vet.clinic_phone
    if contact:
        parts.append(f"Practice number: {contact}")
    return " - ".join(parts)

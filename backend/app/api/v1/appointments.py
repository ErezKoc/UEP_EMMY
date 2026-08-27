"""Appointment requests: an owner asks, a practice answers.

Every route here is scoped to the two people on the appointment. A veterinarian
sees requests addressed to them and nobody else's; an owner sees their own. The
checks are per-row rather than per-role, because "is a vet" is not the question
- "is THIS appointment's vet" is.
"""

import hashlib
import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_active_user, get_current_user
from app.db.session import get_db
from app.models import Animal, Reminder, ReminderType, User, UserRole
from app.models import AvailabilitySlot
from app.models.appointment import Appointment, AppointmentMessage, AppointmentStatus
from app.models.notification import NotificationKind
from app.services.notifications import notify
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDecision,
    AppointmentMessageCreate,
    AppointmentMessageRead,
    AppointmentNote,
    AppointmentRead,
    AppointmentReschedule,
    RescheduleDecision,
)

router = APIRouter()

_LOADED = (
    joinedload(Appointment.owner),
    joinedload(Appointment.vet),
    joinedload(Appointment.animal),
    selectinload(Appointment.messages),
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


def _other_party(appointment: Appointment, user: User) -> User:
    """Whoever is on the far side of this appointment from `user`."""
    return appointment.vet if user.id == appointment.owner_id else appointment.owner


def _when(day: date, clock: time | None) -> str:
    """One phrase for a date and its time, for notifications and calendar notes.

    Falls back to the bare date rather than inventing a time, because rows
    confirmed before `scheduled_time` existed genuinely have none and printing
    "00:00" for them would be a lie with a number in it.
    """
    if clock is None:
        return f"{day:%d %b %Y}"
    return f"{day:%d %b %Y} at {clock:%H:%M}"


def _for_viewer(appointment: Appointment, viewer: User) -> AppointmentRead:
    """One appointment, told from the reader's side of it.

    `unread_message_count` cannot come off the row on its own - it depends on
    who is asking - so it is filled in here rather than left for each client to
    work out from a thread it would have to fetch first.
    """
    data = AppointmentRead.model_validate(appointment)
    data.message_count = len(appointment.messages)
    data.unread_message_count = sum(
        1
        for message in appointment.messages
        if message.sender_id != viewer.id and message.read_at is None
    )
    return data


def _facts(
    appointment: Appointment, *, when: str | None = None, extra: list[tuple[str, str]] | None = None
) -> list[tuple[str, str]]:
    """The labelled details an email carries that a one-line alert cannot.

    An in-app alert is read in front of the appointment it is about; an email is
    read on a phone at a bus stop, days later, with no list beside it. The pet's
    name and the practice are what make it possible to act on without opening
    anything.

    Nothing here is invented. A field the appointment does not have is a row
    that is not printed.
    """
    facts: list[tuple[str, str]] = []
    if appointment.animal is not None:
        facts.append(("Pet", appointment.animal.name))
    practice = appointment.vet.clinic_name or appointment.vet.display_name
    facts.append(("Practice", practice))
    if when:
        facts.append(("When", when))
    facts.append(("Reason given", appointment.reason))
    if appointment.vet.clinic_phone:
        facts.append(("Practice number", appointment.vet.clinic_phone))
    facts.extend(extra or [])
    return facts


@router.get("", response_model=list[AppointmentRead])
def list_appointments(
    open_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AppointmentRead]:
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
    rows = list(db.scalars(statement).unique().all())
    return [_for_viewer(row, current_user) for row in rows]


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def request_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> AppointmentRead:
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

    # A picked opening supplies the date and time, overriding whatever the form
    # sent. Trusting the client's copy would let a stale page request a time the
    # practice moved or withdrew hours ago.
    slot: AvailabilitySlot | None = None
    if payload.slot_id is not None:
        slot = db.get(AvailabilitySlot, payload.slot_id)
        if slot is None or slot.vet_id != vet.id:
            raise HTTPException(status_code=404, detail="That opening is no longer listed.")
        if slot.slot_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That opening has already passed.",
            )
        if not slot.is_open:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Somebody has taken that opening. Pick another time.",
            )

    appointment = Appointment(
        owner_id=current_user.id,
        vet_id=vet.id,
        animal_id=animal.id if animal else None,
        reason=payload.reason.strip(),
        preferred_date=slot.slot_date if slot else payload.preferred_date,
        preferred_time=slot.start_time if slot else payload.preferred_time,
        preferred_time_note=(payload.preferred_time_note or "").strip() or None,
        slot_id=slot.id if slot else None,
    )
    db.add(appointment)
    db.flush()

    # Inside the same transaction as the request itself. A practice told about
    # an appointment that then failed to save would be worse than not being
    # told at all.
    pet = f" about {animal.name}" if animal else ""
    asked = (
        _when(appointment.preferred_date, appointment.preferred_time)
        if appointment.preferred_time
        # Said out loud rather than left blank, so the practice knows the owner
        # is flexible instead of wondering whether a time failed to send.
        else f"{appointment.preferred_date:%d %b %Y} (no particular time)"
    )
    notify(
        db,
        user=vet,
        kind=NotificationKind.APPOINTMENT_REQUESTED,
        title="New appointment request",
        body=(
            f"{current_user.display_name} asked for an appointment{pet} on "
            f"{asked}. Reason: {appointment.reason}"
        ),
        dedupe_key=f"appointment:{appointment.id}:requested",
        link="/appointments",
        email_facts=_facts(appointment, when=asked, extra=[("From", current_user.display_name)]),
    )

    db.commit()
    db.refresh(appointment)
    return _for_viewer(appointment, current_user)


@router.post("/{appointment_id}/respond", response_model=AppointmentRead)
def respond_to_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> AppointmentRead:
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
        practice = appointment.vet.clinic_name or appointment.vet.display_name
        notify(
            db,
            user=appointment.owner,
            kind=NotificationKind.APPOINTMENT_DECLINED,
            title="Appointment request declined",
            body=(
                f"{practice} could not take your appointment on "
                f"{appointment.preferred_date:%d %b %Y}."
                + (f" They said: {note}" if note else "")
            ),
            dedupe_key=f"appointment:{appointment.id}:declined",
            link="/appointments",
            email_facts=_facts(
                appointment,
                when=f"{appointment.preferred_date:%d %b %Y} (the day you asked for)",
            ),
        )
        db.commit()
        db.refresh(appointment)
        return _for_viewer(appointment, current_user)

    scheduled = payload.scheduled_date or appointment.preferred_date
    if scheduled < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a date that has not already passed.",
        )
    appointment.status = AppointmentStatus.CONFIRMED
    appointment.scheduled_date = scheduled
    # Guaranteed present: AppointmentDecision refuses a confirmation without one.
    appointment.scheduled_time = payload.scheduled_time

    # The confirmation is what puts this on the owner's calendar - nothing
    # appears there while a practice has not answered, because a request is not
    # an appointment and a calendar entry says it is.
    if appointment.animal_id is not None:
        _sync_reminder(db, appointment, note)

    practice = appointment.vet.clinic_name or appointment.vet.display_name
    moved = scheduled != appointment.preferred_date
    notify(
        db,
        user=appointment.owner,
        kind=NotificationKind.APPOINTMENT_CONFIRMED,
        title="Appointment confirmed",
        body=(
            f"{practice} confirmed your appointment for "
            f"{_when(scheduled, appointment.scheduled_time)}."
            # The changed day is the single most important thing in this
            # message, so it is said in the message rather than left for the
            # owner to notice by comparing two dates.
            + (
                f" This is a different day from the {appointment.preferred_date:%d %b %Y} you asked for."
                if moved
                else ""
            )
            + (f" They said: {note}" if note else "")
        ),
        dedupe_key=f"appointment:{appointment.id}:confirmed",
        link="/appointments",
        email_facts=_facts(
            appointment, when=_when(scheduled, appointment.scheduled_time)
        ),
    )

    db.commit()
    db.refresh(appointment)
    return _for_viewer(appointment, current_user)


# ------------------------------------------------------------------ moving it


@router.post("/{appointment_id}/reschedule", response_model=AppointmentRead)
def propose_reschedule(
    appointment_id: uuid.UUID,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> AppointmentRead:
    """Ask to move a confirmed appointment. Either side may.

    The agreed appointment does not move here. It keeps its date, its time and
    its calendar entry until the other party accepts, because a proposal is not
    an agreement and an owner whose calendar quietly shifted under them would
    turn up on a day nobody promised.

    Only from CONFIRMED. Moving something the practice has not answered yet is
    not rescheduling - the request is still open and its date can simply be
    answered with a different one.
    """
    appointment = _visible(db, appointment_id, current_user)
    if appointment.status is not AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only a confirmed appointment can be moved. This one is "
                f"{appointment.status.value.replace('_', ' ')}."
            ),
        )
    if payload.new_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a date that has not already passed.",
        )
    if (
        payload.new_date == appointment.scheduled_date
        and payload.new_time == appointment.scheduled_time
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That is the time it is already booked for.",
        )

    appointment.status = AppointmentStatus.RESCHEDULE_PROPOSED
    appointment.proposed_date = payload.new_date
    appointment.proposed_time = payload.new_time
    appointment.proposed_by_id = current_user.id
    appointment.proposed_note = (payload.note or "").strip() or None

    other = _other_party(appointment, current_user)
    notify(
        db,
        user=other,
        kind=NotificationKind.APPOINTMENT_RESCHEDULE_PROPOSED,
        title="A new time has been suggested",
        body=(
            f"{current_user.display_name} asked to move the appointment from "
            f"{_when(appointment.scheduled_date, appointment.scheduled_time)} to "
            f"{_when(payload.new_date, payload.new_time)}. It stays as it is until you answer."
            + (f" They said: {appointment.proposed_note}" if appointment.proposed_note else "")
        ),
        # Keyed on the proposed slot, not just the appointment: a second
        # proposal after a declined first one is genuinely new news, and a bare
        # "appointment:<id>:reschedule" key would silence it forever.
        dedupe_key=(
            f"appointment:{appointment.id}:reschedule:{payload.new_date}T{payload.new_time}"
        ),
        link="/appointments",
        email_facts=_facts(
            appointment,
            when=_when(appointment.scheduled_date, appointment.scheduled_time),
            extra=[("Suggested", _when(payload.new_date, payload.new_time))],
        ),
    )

    db.commit()
    db.refresh(appointment)
    return _for_viewer(appointment, current_user)


@router.post("/{appointment_id}/reschedule/respond", response_model=AppointmentRead)
def respond_to_reschedule(
    appointment_id: uuid.UUID,
    payload: RescheduleDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> AppointmentRead:
    """Accept or refuse a proposed move. Only the side that did not propose it.

    Either answer ends with a CONFIRMED appointment: accepting moves it,
    refusing leaves it exactly where it was. There is no state in which the
    appointment stops existing because two people disagreed about a time - if
    somebody wants it gone they cancel it, which is a different button with a
    different consequence.
    """
    appointment = _visible(db, appointment_id, current_user)
    if appointment.status is not AppointmentStatus.RESCHEDULE_PROPOSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is no proposed time waiting on this appointment.",
        )
    if appointment.proposed_by_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You suggested this time - the other side has to answer it.",
        )

    note = (payload.note or "").strip() or None
    proposed_date = appointment.proposed_date
    proposed_time = appointment.proposed_time
    other = _other_party(appointment, current_user)
    appointment.responded_at = datetime.now(timezone.utc)

    if not payload.accept:
        appointment.status = AppointmentStatus.CONFIRMED
        _clear_proposal(appointment)
        notify(
            db,
            user=other,
            kind=NotificationKind.APPOINTMENT_RESCHEDULE_DECLINED,
            title="Your suggested time was turned down",
            body=(
                f"{current_user.display_name} could not do "
                f"{_when(proposed_date, proposed_time)}. The appointment stays as it was, on "
                f"{_when(appointment.scheduled_date, appointment.scheduled_time)}."
                + (f" They said: {note}" if note else "")
            ),
            dedupe_key=(
                f"appointment:{appointment.id}:reschedule-declined:"
                f"{proposed_date}T{proposed_time}"
            ),
            link="/appointments",
            email_facts=_facts(
                appointment,
                when=_when(appointment.scheduled_date, appointment.scheduled_time),
                extra=[("Turned down", _when(proposed_date, proposed_time))],
            ),
        )
        db.commit()
        db.refresh(appointment)
        return _for_viewer(appointment, current_user)

    was = _when(appointment.scheduled_date, appointment.scheduled_time)
    appointment.status = AppointmentStatus.CONFIRMED
    appointment.scheduled_date = proposed_date
    appointment.scheduled_time = proposed_time
    _clear_proposal(appointment)

    # The calendar entry moves WITH the appointment rather than being deleted
    # and made again, so anything the owner added to it themselves survives and
    # its id stays stable for anyone holding a reference.
    if appointment.animal_id is not None:
        _sync_reminder(db, appointment, appointment.vet_note)

    notify(
        db,
        user=other,
        kind=NotificationKind.APPOINTMENT_RESCHEDULED,
        title="Appointment moved",
        body=(
            f"{current_user.display_name} accepted the new time. The appointment has moved "
            f"from {was} to {_when(proposed_date, proposed_time)}."
            + (f" They said: {note}" if note else "")
        ),
        dedupe_key=f"appointment:{appointment.id}:rescheduled:{proposed_date}T{proposed_time}",
        link="/appointments",
        email_facts=_facts(
            appointment,
            when=_when(proposed_date, proposed_time),
            extra=[("Was", was)],
        ),
    )

    db.commit()
    db.refresh(appointment)
    return _for_viewer(appointment, current_user)


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AppointmentRead:
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
    # A proposal on a cancelled appointment is a question about a thing that no
    # longer exists, so it goes with it.
    _clear_proposal(appointment)
    appointment.responded_at = datetime.now(timezone.utc)

    # The other party, whoever that is. Telling the person who just pressed
    # Cancel that it was cancelled is noise; the one who did not press it is
    # the one who needs to know.
    other = _other_party(appointment, current_user)
    when = _when(
        appointment.scheduled_date or appointment.preferred_date,
        appointment.scheduled_time or appointment.preferred_time,
    )
    notify(
        db,
        user=other,
        kind=NotificationKind.APPOINTMENT_CANCELLED,
        title="Appointment cancelled",
        body=f"{current_user.display_name} cancelled the appointment on {when}.",
        dedupe_key=f"appointment:{appointment.id}:cancelled",
        link="/appointments",
        email_facts=_facts(appointment, when=when),
    )
    db.commit()
    db.refresh(appointment)
    return _for_viewer(appointment, current_user)


# ------------------------------------------------------- what the practice said


@router.post("/{appointment_id}/note", response_model=AppointmentRead)
def add_vet_note(
    appointment_id: uuid.UUID,
    payload: AppointmentNote,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> AppointmentRead:
    """The practice writes something down about the visit, and the owner is told.

    Only the veterinarian on the appointment. A note here is a record attributed
    to a practice - it lands in the owner's calendar entry and in their inbox -
    and an owner writing one would be putting words in the practice's mouth.

    Open on every status except a request nobody has answered yet. Before an
    answer, the note belongs on the answer: `respond` already takes one, and
    accepting a second route into the same field would let a practice add advice
    to a request they have not agreed to.

    Replacing an existing note is allowed and re-announced, because a correction
    to clinical wording is the message most worth delivering.
    """
    appointment = _visible(db, appointment_id, current_user)
    if appointment.vet_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the practice on this appointment can add a note to it.",
        )
    if appointment.status is AppointmentStatus.REQUESTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Answer the request first - a note goes with your answer.",
        )

    note = payload.note.strip()
    appointment.vet_note = note

    # The calendar entry carries the note, so the owner reads it on the morning
    # of the visit rather than having to remember which email it was in.
    if appointment.reminder_id is not None and appointment.animal_id is not None:
        _sync_reminder(db, appointment, note)

    practice = appointment.vet.clinic_name or appointment.vet.display_name
    pet = f" about {appointment.animal.name}" if appointment.animal else ""
    when = _when(
        appointment.scheduled_date or appointment.preferred_date,
        appointment.scheduled_time or appointment.preferred_time,
    )
    notify(
        db,
        user=appointment.owner,
        kind=NotificationKind.VET_NOTE_ADDED,
        title=f"A note from {practice}",
        body=f"{practice} added a note{pet} about the appointment on {when}: {note[:400]}",
        # The note's content is in the key, so an edited note is announced again
        # and the same note saved twice is not. A digest rather than the text:
        # the key is 200 characters and a note is up to a thousand.
        dedupe_key=(
            f"vet-note:{appointment.id}:"
            f"{hashlib.sha256(note.encode()).hexdigest()[:16]}"
        ),
        link="/appointments",
        email_facts=_facts(appointment, when=when, extra=[("Note", note[:200])]),
    )

    db.commit()
    db.refresh(appointment)
    return _for_viewer(appointment, current_user)


# -------------------------------------------------------------- the same page


@router.get("/{appointment_id}/messages", response_model=list[AppointmentMessageRead])
def list_messages(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AppointmentMessage]:
    """The thread, and reading it marks the other side's messages as read.

    Marking on read rather than on a separate "mark read" call, because there is
    exactly one way to see these messages and it is this one. A second endpoint
    would only add a way for the badge to disagree with what the person has
    actually looked at.
    """
    appointment = _visible(db, appointment_id, current_user)
    now = datetime.now(timezone.utc)
    for message in appointment.messages:
        if message.sender_id != current_user.id and message.read_at is None:
            message.read_at = now
    db.commit()
    return list(appointment.messages)


@router.post(
    "/{appointment_id}/messages",
    response_model=AppointmentMessageRead,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    appointment_id: uuid.UUID,
    payload: AppointmentMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
) -> AppointmentMessage:
    """Say something to the other side, about this appointment.

    Open on every status, deliberately - including declined and cancelled. "Why
    was this turned down?" and "sorry, we had to close today" are exactly the
    messages worth having, and they can only be sent after the thing that
    prompted them.
    """
    appointment = _visible(db, appointment_id, current_user)
    body = payload.body.strip()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Write something first.",
        )

    other = _other_party(appointment, current_user)
    # Whether they have anything unread from us ALREADY, worked out before this
    # message joins the list.
    already_waiting = any(
        message.sender_id == current_user.id and message.read_at is None
        for message in appointment.messages
    )

    message = AppointmentMessage(
        appointment_id=appointment.id, sender_id=current_user.id, body=body
    )
    db.add(message)
    db.flush()

    # One alert per unread conversation, not one per line typed.
    #
    # Somebody writing three sentences as three messages is having a
    # conversation, not sending three announcements, and a phone that buzzes
    # for each is a phone that gets muted - which costs us the one alert that
    # mattered. So we tell them when the thread goes from read to unread, and
    # stay quiet until they have looked. The key carries the message id so the
    # NEXT unread stretch is announced again rather than deduped away forever.
    if not already_waiting:
        pet = f" about {appointment.animal.name}" if appointment.animal else ""
        notify(
            db,
            user=other,
            kind=NotificationKind.APPOINTMENT_MESSAGE,
            title=f"Message from {current_user.display_name}",
            body=f"About the appointment{pet}: {body[:300]}",
            dedupe_key=f"appointment:{appointment.id}:message:{message.id}",
            link="/appointments",
            email_facts=_facts(
                appointment,
                when=_when(
                    appointment.scheduled_date or appointment.preferred_date,
                    appointment.scheduled_time or appointment.preferred_time,
                ),
                extra=[("From", current_user.display_name)],
            ),
        )

    db.commit()
    db.refresh(message)
    return message


# ---------------------------------------------------------------- calendaring


def _clear_proposal(appointment: Appointment) -> None:
    appointment.proposed_date = None
    appointment.proposed_time = None
    appointment.proposed_by_id = None
    appointment.proposed_note = None


def _sync_reminder(db: Session, appointment: Appointment, vet_note: str | None) -> None:
    """Put the confirmed appointment on the owner's calendar, or move it there.

    Updates the existing entry when there is one rather than deleting and
    recreating it. A reschedule that replaced the row would throw away anything
    the owner had typed into it and break any reference to its id, for no gain
    over changing three fields.
    """
    practice = appointment.vet.clinic_name or appointment.vet.display_name
    # The time goes in the TITLE, because reminders are day-grained: the
    # calendar, its month grid and both exports show a title and a date and
    # have nowhere else to put a clock time. An entry reading "Vet appointment
    # - Riverside" on the 12th is the same shrug the owner came here to avoid.
    clock = f"{appointment.scheduled_time:%H:%M} " if appointment.scheduled_time else ""
    title = f"Vet appointment {clock}- {practice}"[:150]
    notes = _reminder_note(appointment, vet_note)

    reminder = (
        db.get(Reminder, appointment.reminder_id) if appointment.reminder_id else None
    )
    if reminder is None:
        reminder = Reminder(
            title=title,
            reminder_type=ReminderType.CHECKUP,
            due_date=appointment.scheduled_date,
            notes=notes,
            animal_id=appointment.animal_id,
            owner_id=appointment.owner_id,
        )
        db.add(reminder)
        db.flush()
        appointment.reminder_id = reminder.id
        return

    reminder.title = title
    reminder.due_date = appointment.scheduled_date
    reminder.notes = notes


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
    parts = []
    if appointment.scheduled_time is not None:
        # First, ahead of the reason. This is the one fact an owner opens the
        # entry to check on the morning of the visit.
        parts.append(f"Arrive at {appointment.scheduled_time:%H:%M}")
    parts.append(f"Reason given: {appointment.reason}")
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

"""Appointment requests, and the two things that must never go wrong.

An appointment nobody agreed to must never appear on a calendar, and a
cancelled one must never stay there. Both are ways an owner ends up standing
outside a clinic that is not expecting them, which is worse than the platform
having no booking at all.
"""

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.appointments import (
    cancel_appointment,
    list_appointments,
    request_appointment,
    respond_to_appointment,
)
from app.db.base import Base
from app.models import AgeCategory, Animal, Reminder, User, UserRole, VerificationStatus
from app.models.appointment import AppointmentStatus
from app.schemas.appointment import AppointmentCreate, AppointmentDecision

TOMORROW = date.today() + timedelta(days=1)
NEXT_WEEK = date.today() + timedelta(days=7)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def owner(session):
    user = User(email="owner@example.com", display_name="Owner")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def vet(session):
    user = User(
        email="vet@example.com",
        display_name="Dr. Vet",
        role=UserRole.VETERINARIAN,
        clinic_name="Riverside Veterinary Clinic",
        clinic_phone="(555) 014-2280",
        verification_status=VerificationStatus.VERIFIED,
        accepts_appointments=True,
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def closed_vet(session):
    """A practice that has not opted in to taking requests here."""
    user = User(
        email="closed@example.com",
        display_name="Dr. Elsewhere",
        role=UserRole.VETERINARIAN,
        accepts_appointments=False,
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def dog(session, owner):
    animal = Animal(
        name="Buddy", species="dog", age_category=AgeCategory.ADULT, owner_id=owner.id
    )
    session.add(animal)
    session.commit()
    return animal


def _request(session, owner, vet, animal=None, when=TOMORROW):
    return request_appointment(
        AppointmentCreate(
            vet_id=vet.id,
            reason="Limping on the back left leg for three days.",
            preferred_date=when,
            preferred_time_note="mornings if possible",
            animal_id=animal.id if animal else None,
        ),
        db=session,
        current_user=owner,
    )


# ------------------------------------------------------------------ requesting


def test_an_owner_can_ask_a_practice_for_an_appointment(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)

    assert appointment.status is AppointmentStatus.REQUESTED
    assert appointment.preferred_date == TOMORROW
    assert appointment.preferred_time_note == "mornings if possible"
    assert appointment.scheduled_date is None


def test_a_request_alone_puts_nothing_on_the_calendar(session, owner, vet, dog):
    """The whole point of a request rather than a booking.

    Nobody at the practice has seen this yet, so an entry saying the pet has an
    appointment would be the platform inventing an agreement.
    """
    _request(session, owner, vet, dog)

    assert session.scalars(select(Reminder)).all() == []


def test_a_practice_that_has_not_opted_in_cannot_be_requested(session, owner, closed_vet, dog):
    with pytest.raises(HTTPException) as raised:
        _request(session, owner, closed_vet, dog)
    assert raised.value.status_code == 409


def test_a_date_that_has_already_passed_is_refused(session, owner, vet, dog):
    with pytest.raises(HTTPException) as raised:
        _request(session, owner, vet, dog, when=date.today() - timedelta(days=1))
    assert raised.value.status_code == 400


def test_you_cannot_book_with_yourself(session, vet):
    with pytest.raises(HTTPException) as raised:
        _request(session, vet, vet)
    assert raised.value.status_code == 400


def test_a_pet_belonging_to_someone_else_cannot_be_attached(session, owner, vet, dog):
    stranger = User(email="stranger@example.com", display_name="Stranger")
    session.add(stranger)
    session.commit()

    with pytest.raises(HTTPException) as raised:
        request_appointment(
            AppointmentCreate(
                vet_id=vet.id,
                reason="Checking someone else's dog.",
                preferred_date=TOMORROW,
                animal_id=dog.id,
            ),
            db=session,
            current_user=stranger,
        )
    assert raised.value.status_code == 404


# ------------------------------------------------------------------ answering


def test_confirming_puts_it_on_the_owners_calendar(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)

    confirmed = respond_to_appointment(
        appointment.id, AppointmentDecision(confirm=True), db=session, current_user=vet
    )

    assert confirmed.status is AppointmentStatus.CONFIRMED
    assert confirmed.scheduled_date == TOMORROW
    reminder = session.get(Reminder, confirmed.reminder_id)
    assert reminder is not None
    assert reminder.owner_id == owner.id
    assert reminder.animal_id == dog.id
    assert reminder.due_date == TOMORROW
    assert "Riverside Veterinary Clinic" in reminder.title
    # The practice's number travels with the entry: an owner looking at the
    # reminder the morning of the visit should not have to go and find it.
    assert "(555) 014-2280" in reminder.notes


def test_a_practice_may_confirm_a_different_day_without_losing_the_one_asked_for(
    session, owner, vet, dog
):
    appointment = _request(session, owner, vet, dog)

    confirmed = respond_to_appointment(
        appointment.id,
        AppointmentDecision(confirm=True, scheduled_date=NEXT_WEEK, vet_note="Fully booked before then."),
        db=session,
        current_user=vet,
    )

    assert confirmed.scheduled_date == NEXT_WEEK
    assert confirmed.preferred_date == TOMORROW
    reminder = session.get(Reminder, confirmed.reminder_id)
    assert reminder.due_date == NEXT_WEEK
    # The owner must be able to see that the day moved, on the entry itself.
    assert "you asked for" in reminder.notes.lower()
    assert "Fully booked before then." in reminder.notes


def test_the_calendar_note_stays_on_one_line(session, owner, vet, dog):
    """The calendar edits a reminder's notes in a single-line input.

    HTML strips newlines out of an input value, so a multi-line note came back
    with its parts run together into one unreadable string. Anything this
    function joins has to be joined by something that survives that.
    """
    appointment = _request(session, owner, vet, dog)
    confirmed = respond_to_appointment(
        appointment.id,
        AppointmentDecision(confirm=True, scheduled_date=NEXT_WEEK, vet_note="Bring test results."),
        db=session,
        current_user=vet,
    )

    notes = session.get(Reminder, confirmed.reminder_id).notes

    assert "\n" not in notes and "\r" not in notes
    # All four parts still present, and still separated by something visible.
    assert "Reason given:" in notes
    assert "You asked for" in notes
    assert "Bring test results." in notes
    assert "(555) 014-2280" in notes


def test_declining_leaves_the_calendar_alone(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)

    declined = respond_to_appointment(
        appointment.id,
        AppointmentDecision(confirm=False, vet_note="We are not taking new patients."),
        db=session,
        current_user=vet,
    )

    assert declined.status is AppointmentStatus.DECLINED
    assert declined.reminder_id is None
    assert session.scalars(select(Reminder)).all() == []


def test_a_request_without_a_pet_confirms_but_creates_no_reminder(session, owner, vet):
    """A reminder belongs to a pet, and we do not invent one."""
    appointment = _request(session, owner, vet, animal=None)

    confirmed = respond_to_appointment(
        appointment.id, AppointmentDecision(confirm=True), db=session, current_user=vet
    )

    assert confirmed.status is AppointmentStatus.CONFIRMED
    assert confirmed.reminder_id is None


def test_only_the_practice_it_was_sent_to_can_answer(session, owner, vet, closed_vet, dog):
    appointment = _request(session, owner, vet, dog)

    # Another veterinarian entirely: not their appointment, and not their
    # business that it exists.
    with pytest.raises(HTTPException) as raised:
        respond_to_appointment(
            appointment.id, AppointmentDecision(confirm=True), db=session, current_user=closed_vet
        )
    assert raised.value.status_code == 404

    # The owner is on the appointment, so they can see it — but answering on the
    # practice's behalf is exactly the confirmation this flow exists to prevent.
    with pytest.raises(HTTPException) as raised:
        respond_to_appointment(
            appointment.id, AppointmentDecision(confirm=True), db=session, current_user=owner
        )
    assert raised.value.status_code == 403


def test_a_request_cannot_be_answered_twice(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)
    respond_to_appointment(
        appointment.id, AppointmentDecision(confirm=True), db=session, current_user=vet
    )

    with pytest.raises(HTTPException) as raised:
        respond_to_appointment(
            appointment.id, AppointmentDecision(confirm=False), db=session, current_user=vet
        )
    assert raised.value.status_code == 409


# ----------------------------------------------------------------- cancelling


def test_cancelling_a_confirmed_appointment_removes_the_calendar_entry(
    session, owner, vet, dog
):
    appointment = _request(session, owner, vet, dog)
    confirmed = respond_to_appointment(
        appointment.id, AppointmentDecision(confirm=True), db=session, current_user=vet
    )
    reminder_id = confirmed.reminder_id

    cancelled = cancel_appointment(appointment.id, db=session, current_user=owner)

    assert cancelled.status is AppointmentStatus.CANCELLED
    assert cancelled.reminder_id is None
    assert session.get(Reminder, reminder_id) is None


def test_the_practice_can_also_cancel(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)
    respond_to_appointment(
        appointment.id, AppointmentDecision(confirm=True), db=session, current_user=vet
    )

    cancelled = cancel_appointment(appointment.id, db=session, current_user=vet)
    assert cancelled.status is AppointmentStatus.CANCELLED
    assert session.scalars(select(Reminder)).all() == []


# --------------------------------------------------------------------- listing


def test_each_side_sees_the_appointment_and_nobody_else_does(session, owner, vet, dog):
    _request(session, owner, vet, dog)
    stranger = User(email="nosy@example.com", display_name="Nosy")
    session.add(stranger)
    session.commit()

    assert len(list_appointments(db=session, current_user=owner)) == 1
    assert len(list_appointments(db=session, current_user=vet)) == 1
    assert list_appointments(db=session, current_user=stranger) == []


def test_open_only_hides_everything_already_answered(session, owner, vet, dog):
    answered = _request(session, owner, vet, dog)
    respond_to_appointment(
        answered.id, AppointmentDecision(confirm=False), db=session, current_user=vet
    )
    _request(session, owner, vet, dog, when=NEXT_WEEK)

    still_open = list_appointments(open_only=True, db=session, current_user=vet)

    assert len(still_open) == 1
    assert still_open[0].preferred_date == NEXT_WEEK

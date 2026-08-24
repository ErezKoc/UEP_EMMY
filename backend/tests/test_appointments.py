"""Appointment requests, and the two things that must never go wrong.

An appointment nobody agreed to must never appear on a calendar, and a
cancelled one must never stay there. Both are ways an owner ends up standing
outside a clinic that is not expecting them, which is worse than the platform
having no booking at all.
"""

from datetime import date, time, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.appointments import (
    cancel_appointment,
    list_appointments,
    list_messages,
    propose_reschedule,
    request_appointment,
    respond_to_appointment,
    respond_to_reschedule,
    send_message,
)
from app.db.base import Base
from app.models import (
    AgeCategory,
    Animal,
    Notification,
    NotificationKind,
    Reminder,
    User,
    UserRole,
    VerificationStatus,
)
from app.models.appointment import Appointment, AppointmentMessage, AppointmentStatus
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDecision,
    AppointmentMessageCreate,
    AppointmentReschedule,
    RescheduleDecision,
)

TOMORROW = date.today() + timedelta(days=1)
NEXT_WEEK = date.today() + timedelta(days=7)
AT_TEN = time(10, 0)
AT_HALF_TWO = time(14, 30)


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


def _request(session, owner, vet, animal=None, when=TOMORROW, at=AT_TEN):
    return request_appointment(
        AppointmentCreate(
            vet_id=vet.id,
            reason="Limping on the back left leg for three days.",
            preferred_date=when,
            preferred_time=at,
            animal_id=animal.id if animal else None,
        ),
        db=session,
        current_user=owner,
    )


def _confirm(session, vet, appointment, at=AT_TEN, on=None, note=None):
    return respond_to_appointment(
        appointment.id,
        AppointmentDecision(
            confirm=True, scheduled_date=on, scheduled_time=at, vet_note=note
        ),
        db=session,
        current_user=vet,
    )


# ------------------------------------------------------------------ requesting


def test_an_owner_can_ask_a_practice_for_an_appointment(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)

    assert appointment.status is AppointmentStatus.REQUESTED
    assert appointment.preferred_date == TOMORROW
    assert appointment.preferred_time == AT_TEN
    assert appointment.scheduled_date is None
    assert appointment.scheduled_time is None


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
        appointment.id, AppointmentDecision(confirm=True, scheduled_time=AT_TEN), db=session, current_user=vet
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
        AppointmentDecision(
            confirm=True,
            scheduled_date=NEXT_WEEK,
            scheduled_time=AT_TEN,
            vet_note="Fully booked before then.",
        ),
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
        AppointmentDecision(
            confirm=True,
            scheduled_date=NEXT_WEEK,
            scheduled_time=AT_TEN,
            vet_note="Bring test results.",
        ),
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
        appointment.id, AppointmentDecision(confirm=True, scheduled_time=AT_TEN), db=session, current_user=vet
    )

    assert confirmed.status is AppointmentStatus.CONFIRMED
    assert confirmed.reminder_id is None


def test_only_the_practice_it_was_sent_to_can_answer(session, owner, vet, closed_vet, dog):
    appointment = _request(session, owner, vet, dog)

    # Another veterinarian entirely: not their appointment, and not their
    # business that it exists.
    with pytest.raises(HTTPException) as raised:
        respond_to_appointment(
            appointment.id, AppointmentDecision(confirm=True, scheduled_time=AT_TEN), db=session, current_user=closed_vet
        )
    assert raised.value.status_code == 404

    # The owner is on the appointment, so they can see it — but answering on the
    # practice's behalf is exactly the confirmation this flow exists to prevent.
    with pytest.raises(HTTPException) as raised:
        respond_to_appointment(
            appointment.id, AppointmentDecision(confirm=True, scheduled_time=AT_TEN), db=session, current_user=owner
        )
    assert raised.value.status_code == 403


def test_a_request_cannot_be_answered_twice(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)
    respond_to_appointment(
        appointment.id, AppointmentDecision(confirm=True, scheduled_time=AT_TEN), db=session, current_user=vet
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
        appointment.id, AppointmentDecision(confirm=True, scheduled_time=AT_TEN), db=session, current_user=vet
    )
    reminder_id = confirmed.reminder_id

    cancelled = cancel_appointment(appointment.id, db=session, current_user=owner)

    assert cancelled.status is AppointmentStatus.CANCELLED
    assert cancelled.reminder_id is None
    assert session.get(Reminder, reminder_id) is None


def test_the_practice_can_also_cancel(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)
    respond_to_appointment(
        appointment.id, AppointmentDecision(confirm=True, scheduled_time=AT_TEN), db=session, current_user=vet
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


# ------------------------------------------------------------- an exact time


def test_a_confirmation_must_name_a_time(session, owner, vet, dog):
    """The whole reason the time fields exist.

    "Confirmed for 12 September" is not an appointment: the owner still has to
    telephone to find out when to arrive, which is the question the
    confirmation was supposed to answer. Refused at the schema, so it cannot be
    stored half-answered and then be indistinguishable from a complete one.
    """
    _request(session, owner, vet, dog)

    with pytest.raises(ValidationError):
        AppointmentDecision(confirm=True)


def test_a_decline_needs_no_time(session, owner, vet, dog):
    """Nothing is being booked, so there is nothing to name a time for."""
    appointment = _request(session, owner, vet, dog)

    declined = respond_to_appointment(
        appointment.id,
        AppointmentDecision(confirm=False, vet_note="Fully booked."),
        db=session,
        current_user=vet,
    )

    assert declined.status is AppointmentStatus.DECLINED


def test_an_owner_may_have_no_preferred_time(session, owner, vet, dog):
    """Any time that day is a real answer, and the commonest one."""
    appointment = _request(session, owner, vet, dog, at=None)

    assert appointment.preferred_time is None
    # And the practice can still confirm it with a definite time of their own.
    confirmed = _confirm(session, vet, appointment, at=AT_HALF_TWO)
    assert confirmed.scheduled_time == AT_HALF_TWO


def test_the_confirmed_time_reaches_the_calendar_entry(session, owner, vet, dog):
    """A reminder is day-grained, so the time has to survive in the text.

    The owner opening their calendar on the morning of the visit gets the clock
    time from the entry itself, not from remembering an email.
    """
    appointment = _request(session, owner, vet, dog)

    confirmed = _confirm(session, vet, appointment, at=AT_HALF_TWO)

    reminder = session.get(Reminder, confirmed.reminder_id)
    assert "14:30" in reminder.title
    assert "Arrive at 14:30" in reminder.notes
    # Still one line, for the same reason as before: the calendar edits notes
    # in a single-line input.
    assert "\n" not in reminder.notes


# --------------------------------------------------------------- rescheduling


def test_either_side_can_propose_a_new_time(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)
    _confirm(session, vet, appointment)

    moved = propose_reschedule(
        appointment.id,
        AppointmentReschedule(
            new_date=NEXT_WEEK, new_time=AT_HALF_TWO, note="Something has come up."
        ),
        db=session,
        current_user=owner,
    )

    assert moved.status is AppointmentStatus.RESCHEDULE_PROPOSED
    assert moved.proposed_date == NEXT_WEEK
    assert moved.proposed_time == AT_HALF_TWO
    assert moved.proposed_by_id == owner.id


def test_a_proposal_does_not_move_the_appointment_or_the_calendar(session, owner, vet, dog):
    """The agreed appointment stands until somebody agrees to the new one.

    An owner whose calendar shifted on the strength of a suggestion nobody
    accepted would turn up on a day the practice never promised.
    """
    appointment = _request(session, owner, vet, dog)
    confirmed = _confirm(session, vet, appointment)
    reminder_id = confirmed.reminder_id

    propose_reschedule(
        appointment.id,
        AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_HALF_TWO),
        db=session,
        current_user=vet,
    )

    reminder = session.get(Reminder, reminder_id)
    assert reminder.due_date == TOMORROW
    assert "10:00" in reminder.title


def test_accepting_moves_the_appointment_and_the_same_calendar_entry(
    session, owner, vet, dog
):
    """Updated in place, not deleted and remade.

    Recreating the row would throw away anything the owner typed into it and
    break every reference to its id, for no gain over changing three fields.
    """
    appointment = _request(session, owner, vet, dog)
    confirmed = _confirm(session, vet, appointment)
    reminder_id = confirmed.reminder_id

    propose_reschedule(
        appointment.id,
        AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_HALF_TWO),
        db=session,
        current_user=vet,
    )
    agreed = respond_to_reschedule(
        appointment.id, RescheduleDecision(accept=True), db=session, current_user=owner
    )

    assert agreed.status is AppointmentStatus.CONFIRMED
    assert agreed.scheduled_date == NEXT_WEEK
    assert agreed.scheduled_time == AT_HALF_TWO
    # The proposal is spent and must not linger as a second answer waiting.
    assert agreed.proposed_date is None
    assert agreed.proposed_by_id is None

    assert agreed.reminder_id == reminder_id
    reminder = session.get(Reminder, reminder_id)
    assert reminder.due_date == NEXT_WEEK
    assert "14:30" in reminder.title
    assert session.scalars(select(Reminder)).all() == [reminder]


def test_declining_a_move_leaves_the_appointment_exactly_as_it_was(session, owner, vet, dog):
    """Two people disagreeing about a time must not destroy the booking."""
    appointment = _request(session, owner, vet, dog)
    _confirm(session, vet, appointment)

    propose_reschedule(
        appointment.id,
        AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_HALF_TWO),
        db=session,
        current_user=owner,
    )
    kept = respond_to_reschedule(
        appointment.id,
        RescheduleDecision(accept=False, note="We are closed that afternoon."),
        db=session,
        current_user=vet,
    )

    assert kept.status is AppointmentStatus.CONFIRMED
    assert kept.scheduled_date == TOMORROW
    assert kept.scheduled_time == AT_TEN
    assert kept.proposed_date is None


def test_you_cannot_accept_your_own_proposal(session, owner, vet, dog):
    """Otherwise rescheduling is one party moving the other's appointment."""
    appointment = _request(session, owner, vet, dog)
    _confirm(session, vet, appointment)
    propose_reschedule(
        appointment.id,
        AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_HALF_TWO),
        db=session,
        current_user=owner,
    )

    with pytest.raises(HTTPException) as raised:
        respond_to_reschedule(
            appointment.id,
            RescheduleDecision(accept=True),
            db=session,
            current_user=owner,
        )
    assert raised.value.status_code == 403


def test_only_a_confirmed_appointment_can_be_moved(session, owner, vet, dog):
    """A request nobody has answered has no agreed time to move away from."""
    appointment = _request(session, owner, vet, dog)

    with pytest.raises(HTTPException) as raised:
        propose_reschedule(
            appointment.id,
            AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_HALF_TWO),
            db=session,
            current_user=owner,
        )
    assert raised.value.status_code == 409


def test_a_move_into_the_past_is_refused(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)
    _confirm(session, vet, appointment)

    with pytest.raises(HTTPException) as raised:
        propose_reschedule(
            appointment.id,
            AppointmentReschedule(
                new_date=date.today() - timedelta(days=1), new_time=AT_HALF_TWO
            ),
            db=session,
            current_user=vet,
        )
    assert raised.value.status_code == 400


def test_proposing_the_time_it_already_has_is_refused(session, owner, vet, dog):
    """It would put the appointment into a waiting state that changes nothing."""
    appointment = _request(session, owner, vet, dog)
    _confirm(session, vet, appointment)

    with pytest.raises(HTTPException) as raised:
        propose_reschedule(
            appointment.id,
            AppointmentReschedule(new_date=TOMORROW, new_time=AT_TEN),
            db=session,
            current_user=vet,
        )
    assert raised.value.status_code == 400


def test_cancelling_during_a_proposal_clears_it(session, owner, vet, dog):
    """A question about a thing that no longer exists goes with the thing."""
    appointment = _request(session, owner, vet, dog)
    confirmed = _confirm(session, vet, appointment)
    reminder_id = confirmed.reminder_id
    propose_reschedule(
        appointment.id,
        AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_HALF_TWO),
        db=session,
        current_user=vet,
    )

    cancelled = cancel_appointment(appointment.id, db=session, current_user=owner)

    assert cancelled.status is AppointmentStatus.CANCELLED
    assert cancelled.proposed_date is None
    assert session.get(Reminder, reminder_id) is None


# ------------------------------------------------------------------- messages


def test_both_sides_can_write_and_both_sides_see_it(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)

    send_message(
        appointment.id,
        AppointmentMessageCreate(body="Is he still limping this morning?"),
        db=session,
        current_user=vet,
    )
    send_message(
        appointment.id,
        AppointmentMessageCreate(body="A little, but he is eating."),
        db=session,
        current_user=owner,
    )

    seen_by_owner = list_messages(appointment.id, db=session, current_user=owner)
    seen_by_vet = list_messages(appointment.id, db=session, current_user=vet)

    assert [m.body for m in seen_by_owner] == [
        "Is he still limping this morning?",
        "A little, but he is eating.",
    ]
    assert len(seen_by_vet) == 2


def test_a_stranger_can_neither_read_nor_write_the_thread(session, owner, vet, dog):
    appointment = _request(session, owner, vet, dog)
    stranger = User(email="nosy@example.com", display_name="Nosy")
    session.add(stranger)
    session.commit()

    with pytest.raises(HTTPException) as raised:
        list_messages(appointment.id, db=session, current_user=stranger)
    assert raised.value.status_code == 404

    with pytest.raises(HTTPException) as raised:
        send_message(
            appointment.id,
            AppointmentMessageCreate(body="Hello?"),
            db=session,
            current_user=stranger,
        )
    assert raised.value.status_code == 404


def test_unread_counts_are_per_reader(session, owner, vet, dog):
    """The count is personal: your own messages are never unread to you."""
    appointment = _request(session, owner, vet, dog)
    send_message(
        appointment.id,
        AppointmentMessageCreate(body="Please bring his previous notes."),
        db=session,
        current_user=vet,
    )

    for_owner = list_appointments(db=session, current_user=owner)[0]
    for_vet = list_appointments(db=session, current_user=vet)[0]

    assert for_owner.message_count == 1
    assert for_owner.unread_message_count == 1
    assert for_vet.unread_message_count == 0

    list_messages(appointment.id, db=session, current_user=owner)

    assert list_appointments(db=session, current_user=owner)[0].unread_message_count == 0


def test_a_run_of_messages_raises_one_alert_not_one_each(session, owner, vet, dog):
    """A phone that buzzes per sentence gets muted, which costs us the alert
    that mattered. One per unread stretch; another once they have looked."""
    appointment = _request(session, owner, vet, dog)

    for line in ("Is he limping?", "Also, is he eating?", "And drinking?"):
        send_message(
            appointment.id,
            AppointmentMessageCreate(body=line),
            db=session,
            current_user=vet,
        )

    def alerts():
        return [
            n
            for n in session.scalars(select(Notification)).all()
            if n.kind is NotificationKind.APPOINTMENT_MESSAGE and n.user_id == owner.id
        ]

    assert len(alerts()) == 1

    # Once the owner has read them, the next message is news again.
    list_messages(appointment.id, db=session, current_user=owner)
    send_message(
        appointment.id,
        AppointmentMessageCreate(body="Any change overnight?"),
        db=session,
        current_user=vet,
    )

    assert len(alerts()) == 2


def test_the_thread_stays_open_after_a_decline(session, owner, vet, dog):
    """Why was this turned down? can only be asked after the decline."""
    appointment = _request(session, owner, vet, dog)
    respond_to_appointment(
        appointment.id,
        AppointmentDecision(confirm=False, vet_note="Fully booked."),
        db=session,
        current_user=vet,
    )

    sent = send_message(
        appointment.id,
        AppointmentMessageCreate(body="Could you take him later in the week?"),
        db=session,
        current_user=owner,
    )

    assert sent.body == "Could you take him later in the week?"


def test_deleting_an_appointment_takes_its_messages(session, owner, vet, dog):
    """No orphaned conversation about an appointment nobody can open."""
    appointment = _request(session, owner, vet, dog)
    send_message(
        appointment.id,
        AppointmentMessageCreate(body="See you then."),
        db=session,
        current_user=owner,
    )

    session.delete(session.get(Appointment, appointment.id))
    session.commit()

    assert session.scalars(select(AppointmentMessage)).all() == []

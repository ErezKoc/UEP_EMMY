"""Every event the platform emails about, exercised end to end.

The unit tests elsewhere check the queue and the templates in isolation. What
this file checks is the wiring: that the endpoint which changes something
actually queues the message, addressed to the right person, carrying the pet
and the date, and that it does so inside the same transaction as the change so
neither can exist without the other.

The routes are called directly rather than over HTTP. These are not
HTTP-shaped questions - no status codes, no headers - and going through a
client would only add a fixture between the test and the thing being tested.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.appointments import (
    add_vet_note,
    cancel_appointment,
    propose_reschedule,
    request_appointment,
    respond_to_appointment,
    respond_to_reschedule,
    send_message,
)
from app.api.v1.reports import decide_report
from app.api.v1.verification import decide_verification
from app.db.base import Base
from app.models import (
    AgeCategory,
    Animal,
    ModerationAction,
    Notification,
    NotificationKind,
    Recurrence,
    Reminder,
    ReminderType,
    ReportTargetType,
    User,
    UserReport,
    UserRole,
    VerificationStatus,
    VetVerification,
)
from app.models.email import EmailCategory, EmailMessage, EmailState
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDecision,
    AppointmentMessageCreate,
    AppointmentNote,
    AppointmentReschedule,
    RescheduleDecision,
)
from app.schemas.moderation import ReportDecision
from app.schemas.verification import VerificationDecision
from app.services.notifications import due_reminder_notifications

TOMORROW = date.today() + timedelta(days=1)
NEXT_WEEK = date.today() + timedelta(days=7)
AT_TEN = time(10, 0)
AT_NOON = time(12, 0)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def owner(session):
    user = User(email="owner@example.com", display_name="Alex", notify_time=time(0, 0))
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
        notify_time=time(0, 0),
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def admin(session):
    user = User(email="admin@example.com", display_name="Admin", role=UserRole.ADMIN)
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


def _emails(session, *, to: str | None = None) -> list[EmailMessage]:
    rows = session.scalars(
        select(EmailMessage).order_by(EmailMessage.created_at)
    ).all()
    return [row for row in rows if to is None or row.to_email == to]


def _only(session, *, to: str) -> EmailMessage:
    messages = _emails(session, to=to)
    assert len(messages) == 1, f"expected one email to {to}, got {len(messages)}"
    return messages[0]


def _requested(session, owner, vet, dog):
    return request_appointment(
        AppointmentCreate(
            vet_id=vet.id,
            animal_id=dog.id,
            reason="Limping on the back left leg",
            preferred_date=TOMORROW,
            preferred_time=AT_TEN,
        ),
        db=session,
        current_user=owner,
    )


def _confirmed(session, owner, vet, dog):
    appointment = _requested(session, owner, vet, dog)
    respond_to_appointment(
        appointment.id,
        AppointmentDecision(confirm=True, scheduled_date=TOMORROW, scheduled_time=AT_TEN),
        db=session,
        current_user=vet,
    )
    return appointment


# ------------------------------------------------------------- appointments


def test_a_request_emails_the_practice(session, owner, vet, dog):
    _requested(session, owner, vet, dog)

    message = _only(session, to=vet.email)
    assert message.state is EmailState.QUEUED
    assert message.category is EmailCategory.NOTIFICATION
    assert "Buddy" in message.text_body
    assert "Limping on the back left leg" in message.text_body
    assert _emails(session, to=owner.email) == []


def test_a_confirmation_emails_the_owner_with_the_time(session, owner, vet, dog):
    _confirmed(session, owner, vet, dog)

    message = _only(session, to=owner.email)
    assert "Appointment confirmed" in message.subject
    assert "Buddy" in message.text_body
    assert "Riverside Veterinary Clinic" in message.text_body
    assert f"{TOMORROW:%d %b %Y}" in message.text_body
    assert "10:00" in message.text_body


def test_a_decline_emails_the_owner_with_the_reason(session, owner, vet, dog):
    appointment = _requested(session, owner, vet, dog)
    respond_to_appointment(
        appointment.id,
        AppointmentDecision(confirm=False, vet_note="Fully booked that day."),
        db=session,
        current_user=vet,
    )

    message = _only(session, to=owner.email)
    assert "declined" in message.subject.lower()
    assert "Fully booked that day." in message.text_body


def test_a_proposed_new_time_emails_the_other_side(session, owner, vet, dog):
    appointment = _confirmed(session, owner, vet, dog)
    propose_reschedule(
        appointment.id,
        AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_NOON, note="Vet is away."),
        db=session,
        current_user=vet,
    )

    # One for the confirmation, one for the proposal - both to the owner.
    messages = _emails(session, to=owner.email)
    assert len(messages) == 2
    assert "suggested" in messages[-1].subject.lower()
    assert f"{NEXT_WEEK:%d %b %Y}" in messages[-1].text_body


def test_accepting_a_new_time_emails_whoever_proposed_it(session, owner, vet, dog):
    appointment = _confirmed(session, owner, vet, dog)
    propose_reschedule(
        appointment.id,
        AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_NOON),
        db=session,
        current_user=owner,
    )
    respond_to_reschedule(
        appointment.id, RescheduleDecision(accept=True), db=session, current_user=vet
    )

    message = _emails(session, to=owner.email)[-1]
    assert "moved" in message.subject.lower()
    assert f"{NEXT_WEEK:%d %b %Y}" in message.text_body


def test_refusing_a_new_time_emails_whoever_proposed_it(session, owner, vet, dog):
    appointment = _confirmed(session, owner, vet, dog)
    propose_reschedule(
        appointment.id,
        AppointmentReschedule(new_date=NEXT_WEEK, new_time=AT_NOON),
        db=session,
        current_user=owner,
    )
    respond_to_reschedule(
        appointment.id,
        RescheduleDecision(accept=False, note="Sorry, we are closed."),
        db=session,
        current_user=vet,
    )

    message = _emails(session, to=owner.email)[-1]
    assert "turned down" in message.subject.lower()
    assert "Sorry, we are closed." in message.text_body


def test_a_cancellation_emails_the_other_side_only(session, owner, vet, dog):
    appointment = _confirmed(session, owner, vet, dog)
    cancel_appointment(appointment.id, db=session, current_user=owner)

    # Telling the person who pressed Cancel that it was cancelled is noise.
    to_vet = _emails(session, to=vet.email)
    assert "cancelled" in to_vet[-1].subject.lower()
    assert not any("cancelled" in m.subject.lower() for m in _emails(session, to=owner.email))


def test_a_message_emails_the_other_side(session, owner, vet, dog):
    appointment = _confirmed(session, owner, vet, dog)
    send_message(
        appointment.id,
        AppointmentMessageCreate(body="Please bring her previous blood results."),
        db=session,
        current_user=vet,
    )

    message = _emails(session, to=owner.email)[-1]
    assert "Message from Dr. Vet" in message.subject
    assert "previous blood results" in message.text_body


def test_a_second_message_in_an_unread_thread_does_not_email_again(
    session, owner, vet, dog
):
    """One alert per unread conversation, not one per line typed."""
    appointment = _confirmed(session, owner, vet, dog)
    for body in ("First thought.", "Second thought.", "Third."):
        send_message(
            appointment.id,
            AppointmentMessageCreate(body=body),
            db=session,
            current_user=vet,
        )

    messages = [m for m in _emails(session, to=owner.email) if "Message from" in m.subject]
    assert len(messages) == 1


# ----------------------------------------------------------------- vet notes


def test_a_vet_note_emails_the_owner(session, owner, vet, dog):
    appointment = _confirmed(session, owner, vet, dog)
    add_vet_note(
        appointment.id,
        AppointmentNote(note="The swelling has gone down; keep her rested for a week."),
        db=session,
        current_user=vet,
    )

    message = _emails(session, to=owner.email)[-1]
    assert "note from Riverside Veterinary Clinic" in message.subject
    assert "keep her rested" in message.text_body
    assert "Buddy" in message.text_body


def test_a_vet_note_says_it_is_not_a_diagnosis(session, owner, vet, dog):
    from app.services.email_templates import NOT_A_DIAGNOSIS

    appointment = _confirmed(session, owner, vet, dog)
    add_vet_note(
        appointment.id,
        AppointmentNote(note="Mild sprain."),
        db=session,
        current_user=vet,
    )

    message = _emails(session, to=owner.email)[-1]
    assert NOT_A_DIAGNOSIS in message.text_body


def test_the_same_note_saved_twice_is_emailed_once(session, owner, vet, dog):
    appointment = _confirmed(session, owner, vet, dog)
    for _ in range(2):
        add_vet_note(
            appointment.id, AppointmentNote(note="Mild sprain."), db=session, current_user=vet
        )

    notes = [m for m in _emails(session, to=owner.email) if "note from" in m.subject]
    assert len(notes) == 1


def test_an_edited_note_is_emailed_again(session, owner, vet, dog):
    """A correction to clinical wording is the message most worth delivering."""
    appointment = _confirmed(session, owner, vet, dog)
    add_vet_note(appointment.id, AppointmentNote(note="Mild sprain."), db=session, current_user=vet)
    add_vet_note(
        appointment.id,
        AppointmentNote(note="Correction: a hairline fracture, not a sprain."),
        db=session,
        current_user=vet,
    )

    notes = [m for m in _emails(session, to=owner.email) if "note from" in m.subject]
    assert len(notes) == 2
    assert "hairline fracture" in notes[-1].text_body


def test_only_the_practice_on_the_appointment_may_add_a_note(session, owner, vet, dog):
    from fastapi import HTTPException

    appointment = _confirmed(session, owner, vet, dog)
    with pytest.raises(HTTPException) as raised:
        add_vet_note(
            appointment.id, AppointmentNote(note="I feel fine"), db=session, current_user=owner
        )
    assert raised.value.status_code == 403


# -------------------------------------------------------------- verification


def _submission(session, user) -> VetVerification:
    verification = VetVerification(
        user_id=user.id,
        document_key="k",
        document_url="http://example/doc.png",
        license_number="VET-1234",
        status=VerificationStatus.PENDING,
    )
    user.verification_status = VerificationStatus.PENDING
    session.add(verification)
    session.commit()
    return verification


def test_an_approval_emails_the_veterinarian(session, vet, admin):
    vet.verification_status = VerificationStatus.UNVERIFIED
    verification = _submission(session, vet)

    decide_verification(
        verification.id,
        VerificationDecision(status=VerificationStatus.VERIFIED),
        db=session,
        admin=admin,
    )

    message = _only(session, to=vet.email)
    assert "verified" in message.subject.lower()
    assert "VET-1234" in message.text_body


def test_a_rejection_emails_the_veterinarian_with_the_reason(session, vet, admin):
    vet.verification_status = VerificationStatus.UNVERIFIED
    verification = _submission(session, vet)

    decide_verification(
        verification.id,
        VerificationDecision(
            status=VerificationStatus.REJECTED, review_note="The scan is unreadable."
        ),
        db=session,
        admin=admin,
    )

    message = _only(session, to=vet.email)
    assert "not approved" in message.subject.lower()
    assert "The scan is unreadable." in message.text_body


def test_revoking_an_approval_says_the_badge_has_gone(session, vet, admin):
    """Not the same message as a rejection: the badge was there and has gone."""
    vet.verification_status = VerificationStatus.UNVERIFIED
    verification = _submission(session, vet)
    decide_verification(
        verification.id,
        VerificationDecision(status=VerificationStatus.VERIFIED),
        db=session,
        admin=admin,
    )
    decide_verification(
        verification.id,
        VerificationDecision(
            status=VerificationStatus.REJECTED, review_note="Licence has lapsed."
        ),
        db=session,
        admin=admin,
    )

    messages = _emails(session, to=vet.email)
    assert len(messages) == 2
    assert "removed" in messages[-1].subject.lower()
    assert "Licence has lapsed." in messages[-1].text_body

    kinds = [n.kind for n in session.scalars(select(Notification)).all()]
    assert NotificationKind.VERIFICATION_REVOKED in kinds
    assert NotificationKind.VERIFICATION_REJECTED not in kinds


# --------------------------------------------------------------- moderation


def _report(session, reporter, reported) -> UserReport:
    report = UserReport(
        reporter_id=reporter.id,
        reported_user_id=reported.id,
        target_type=ReportTargetType.USER,
        reasons=["harassment"],
    )
    session.add(report)
    session.commit()
    return report


def test_a_suspension_emails_the_member(session, owner, vet, admin):
    report = _report(session, reporter=vet, reported=owner)

    decide_report(
        report.id,
        ReportDecision(
            action=ModerationAction.SUSPEND, suspend_days=7, review_note="Repeated abuse."
        ),
        db=session,
        admin=admin,
    )

    message = _only(session, to=owner.email)
    assert "suspended" in message.subject.lower()
    assert "Repeated abuse." in message.text_body


def test_a_ban_emails_the_member(session, owner, vet, admin):
    report = _report(session, reporter=vet, reported=owner)

    decide_report(
        report.id,
        ReportDecision(action=ModerationAction.BAN, review_note="Impersonating a vet."),
        db=session,
        admin=admin,
    )

    message = _only(session, to=owner.email)
    assert "banned" in message.subject.lower()


def test_a_reinstatement_emails_the_member(session, owner, vet, admin):
    report = _report(session, reporter=vet, reported=owner)
    decide_report(
        report.id,
        ReportDecision(action=ModerationAction.SUSPEND, suspend_days=7, review_note="Abuse."),
        db=session,
        admin=admin,
    )
    decide_report(
        report.id,
        ReportDecision(action=ModerationAction.REINSTATE, review_note="Appeal upheld."),
        db=session,
        admin=admin,
    )

    messages = _emails(session, to=owner.email)
    assert len(messages) == 2
    assert "reinstated" in messages[-1].subject.lower()


def test_a_dismissed_report_emails_nobody(session, owner, vet, admin):
    """The member never knew a report existed; telling them creates a grievance."""
    report = _report(session, reporter=vet, reported=owner)

    decide_report(report.id, ReportDecision(dismiss=True), db=session, admin=admin)

    assert _emails(session) == []


# ----------------------------------------------------------------- reminders


def _reminder(session, owner, dog, **kwargs) -> Reminder:
    defaults = dict(
        title="Rabies booster",
        reminder_type=ReminderType.VACCINE,
        due_date=TOMORROW,
        recurrence=Recurrence.NONE,
        owner_id=owner.id,
        animal_id=dog.id,
    )
    defaults.update(kwargs)
    reminder = Reminder(**defaults)
    session.add(reminder)
    session.commit()
    return reminder


def test_a_due_reminder_emails_the_owner_with_the_pet_and_the_date(session, owner, dog):
    _reminder(session, owner, dog)

    due_reminder_notifications(session, today=date.today())

    message = _only(session, to=owner.email)
    assert "Rabies booster" in message.subject
    assert "Buddy" in message.text_body
    assert f"{TOMORROW:%d %b %Y}" in message.text_body
    assert "/calendar" in message.text_body


def test_a_reminder_is_emailed_once_however_often_the_sweep_runs(session, owner, dog):
    _reminder(session, owner, dog)

    for _ in range(5):
        due_reminder_notifications(session, today=date.today())

    assert len(_emails(session, to=owner.email)) == 1


def test_each_configured_lead_time_gets_its_own_email(session, owner, dog):
    """"A week before AND the night before" is one preference, not two rivals."""
    owner.notify_leads = [7, 1]
    session.commit()
    due = date.today() + timedelta(days=7)
    _reminder(session, owner, dog, due_date=due)

    # A week out: only the seven-day lead has come round.
    due_reminder_notifications(session, today=date.today())
    assert len(_emails(session, to=owner.email)) == 1

    # Sweeping again on the same day changes nothing.
    due_reminder_notifications(session, today=date.today())
    assert len(_emails(session, to=owner.email)) == 1

    # The day before, the second lead speaks up in its own right.
    due_reminder_notifications(session, today=due - timedelta(days=1))
    assert len(_emails(session, to=owner.email)) == 2


def test_a_reminders_own_lead_time_overrides_the_account_list(session, owner, dog):
    """A booster set to a week means a week, not a week and everything else."""
    owner.notify_leads = [7, 3, 1]
    session.commit()
    due = date.today() + timedelta(days=7)
    _reminder(session, owner, dog, due_date=due, notify_lead_days=1)

    due_reminder_notifications(session, today=date.today())
    assert _emails(session, to=owner.email) == []

    due_reminder_notifications(session, today=due - timedelta(days=1))
    assert len(_emails(session, to=owner.email)) == 1


def test_the_sending_hour_is_read_on_the_owners_own_clock(session, owner, dog):
    """09:00 in Auckland is not 09:00 on a server in UTC."""
    owner.notify_time = time(9, 0)
    owner.notify_timezone = "Pacific/Auckland"
    session.commit()
    _reminder(session, owner, dog)

    # 20:00 UTC is 08:00 the next morning in Auckland - before their hour.
    before = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
    due_reminder_notifications(session, today=date.today(), moment=before)
    assert _emails(session, to=owner.email) == []

    # 22:00 UTC is 10:00 there, and the alert goes.
    after = datetime(2026, 9, 11, 22, 0, tzinfo=timezone.utc)
    due_reminder_notifications(session, today=date.today(), moment=after)
    assert len(_emails(session, to=owner.email)) == 1


def test_due_today_is_worked_out_on_the_owners_own_date(session, owner, dog):
    """A server a day behind must not announce "tomorrow" for something due today.

    With no `today` forced, each owner's own date decides. Auckland is thirteen
    hours ahead of UTC in September, so at 12:00 UTC it is already the next day
    there - and a reminder due on that next day is due TODAY for them.
    """
    owner.notify_timezone = "Pacific/Auckland"
    owner.notify_time = time(0, 0)
    session.commit()
    _reminder(session, owner, dog, due_date=TOMORROW, notify_lead_days=0)

    noon_utc = datetime.combine(date.today(), time(12, 0), tzinfo=timezone.utc)
    due_reminder_notifications(session, moment=noon_utc)

    message = _only(session, to=owner.email)
    assert "due today" in message.text_body


def test_an_owner_with_email_off_still_gets_the_in_app_alert(session, owner, dog):
    owner.notify_email = False
    session.commit()
    _reminder(session, owner, dog)

    assert due_reminder_notifications(session, today=date.today()) == 1
    assert _emails(session) == []
    stored = session.scalars(select(Notification)).one()
    assert stored.email_state is EmailState.NOT_REQUESTED


# ---------------------------------------------------- transactional integrity


def test_a_refused_change_queues_no_email(session, owner, vet, dog):
    """The email is queued inside the transaction that changes the appointment.

    Answering an already-answered request is refused before anything is
    written, and that has to include the email: an owner told twice that their
    appointment was confirmed cannot tell which confirmation to believe.
    """
    from fastapi import HTTPException

    decision = AppointmentDecision(
        confirm=True, scheduled_date=TOMORROW, scheduled_time=AT_TEN
    )
    appointment = _requested(session, owner, vet, dog)
    respond_to_appointment(appointment.id, decision, db=session, current_user=vet)

    with pytest.raises(HTTPException) as raised:
        respond_to_appointment(appointment.id, decision, db=session, current_user=vet)
    assert raised.value.status_code == 409

    assert len([m for m in _emails(session) if "confirmed" in m.subject.lower()]) == 1

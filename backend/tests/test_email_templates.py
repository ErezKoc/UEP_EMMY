"""Both bodies, for every message the platform sends.

The property under test throughout is that the HTML and the plain text say the
same thing. An HTML-only email is unreadable to a text client, a screen reader
in plain-text mode, and every "view original" pane; an email whose text part
quietly drops the link is worse than one with no text part at all, because it
looks fine until somebody tries to act on it.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.models.notification import NotificationKind
from app.services.email import EmailSender
from app.services.email_templates import (
    NOT_A_DIAGNOSIS,
    EmailContent,
    absolute_url,
    html_to_text,
    notification_email,
    password_reset,
    render,
    verify_email,
    verify_new_email,
)

#: One representative call per event the platform emails about. The list is the
#: test: an event added to `NotificationKind` without a line here fails
#: `test_every_notification_kind_is_covered`, which is how a new event stops
#: being silently un-emailed.
EVENTS = {
    NotificationKind.REMINDER_DUE: dict(
        title="Reminder: Rabies booster",
        body="Rabies booster for Buddy is due tomorrow (12 Sep 2026).",
        link="/calendar",
        facts=[("Pet", "Buddy"), ("Due", "12 Sep 2026 (tomorrow)")],
    ),
    NotificationKind.APPOINTMENT_REQUESTED: dict(
        title="New appointment request",
        body="Alex asked for an appointment about Buddy on 12 Sep 2026 at 09:30.",
        link="/appointments",
        facts=[("Pet", "Buddy"), ("Practice", "Riverside Veterinary Clinic")],
    ),
    NotificationKind.APPOINTMENT_CONFIRMED: dict(
        title="Appointment confirmed",
        body="Riverside confirmed your appointment for 12 Sep 2026 at 09:30.",
        link="/appointments",
        facts=[("Pet", "Buddy"), ("When", "12 Sep 2026 at 09:30")],
    ),
    NotificationKind.APPOINTMENT_DECLINED: dict(
        title="Appointment request declined",
        body="Riverside could not take your appointment on 12 Sep 2026.",
        link="/appointments",
        facts=[("Pet", "Buddy")],
    ),
    NotificationKind.APPOINTMENT_CANCELLED: dict(
        title="Appointment cancelled",
        body="Alex cancelled the appointment on 12 Sep 2026 at 09:30.",
        link="/appointments",
        facts=[("Pet", "Buddy")],
    ),
    NotificationKind.APPOINTMENT_RESCHEDULE_PROPOSED: dict(
        title="A new time has been suggested",
        body="Riverside asked to move the appointment to 14 Sep 2026 at 11:00.",
        link="/appointments",
        facts=[("Suggested", "14 Sep 2026 at 11:00")],
    ),
    NotificationKind.APPOINTMENT_RESCHEDULED: dict(
        title="Appointment moved",
        body="The appointment has moved to 14 Sep 2026 at 11:00.",
        link="/appointments",
        facts=[("When", "14 Sep 2026 at 11:00")],
    ),
    NotificationKind.APPOINTMENT_RESCHEDULE_DECLINED: dict(
        title="Your suggested time was turned down",
        body="Riverside could not do 14 Sep 2026 at 11:00.",
        link="/appointments",
        facts=[("Turned down", "14 Sep 2026 at 11:00")],
    ),
    NotificationKind.APPOINTMENT_MESSAGE: dict(
        title="Message from Dr. Vet",
        body="About the appointment about Buddy: please bring the previous results.",
        link="/appointments",
        facts=[("Pet", "Buddy"), ("From", "Dr. Vet")],
    ),
    NotificationKind.VET_NOTE_ADDED: dict(
        title="A note from Riverside Veterinary Clinic",
        body="Riverside added a note about Buddy: the swelling has gone down.",
        link="/appointments",
        facts=[("Pet", "Buddy"), ("Note", "the swelling has gone down")],
    ),
    NotificationKind.VERIFICATION_APPROVED: dict(
        title="Your veterinarian account is verified",
        body="An administrator has checked your licence document.",
        link="/profile",
        facts=[("Decision", "verified")],
    ),
    NotificationKind.VERIFICATION_REJECTED: dict(
        title="Your verification request was not approved",
        body="An administrator could not verify your licence document.",
        link="/profile",
        facts=[("Decision", "rejected")],
    ),
    NotificationKind.VERIFICATION_REVOKED: dict(
        title="Your verified veterinarian badge has been removed",
        body="An administrator has withdrawn the verification on your account.",
        link="/profile",
        facts=[("Decision", "rejected")],
    ),
    NotificationKind.MODERATION_DECISION: dict(
        title="Your account has been suspended",
        body="An administrator has suspended your UEP EMMY account until 20 Sep 2026.",
        link="/profile",
        facts=[("Decision", "suspend"), ("Until", "20 Sep 2026")],
    ),
}


def test_every_notification_kind_is_covered():
    """A new event must not be able to ship without an email exercised for it."""
    assert set(EVENTS) == set(NotificationKind), (
        "Every NotificationKind needs a case in EVENTS, so its email is generated "
        "and checked at least once."
    )


@pytest.mark.parametrize("kind", list(EVENTS), ids=lambda kind: kind.value)
def test_both_bodies_are_produced_for_every_event(kind):
    rendered = notification_email(kind=kind, recipient_name="Alex", **EVENTS[kind])

    assert rendered.html.strip(), "no HTML body"
    assert rendered.text.strip(), "no plain-text body"
    assert "<" in rendered.html and ">" in rendered.html
    # The text part is text. An escaped-tag soup here would mean somebody had
    # passed the HTML through as the alternative.
    assert "<div" not in rendered.text and "<p " not in rendered.text


@pytest.mark.parametrize("kind", list(EVENTS), ids=lambda kind: kind.value)
def test_the_two_bodies_say_the_same_thing(kind):
    """Every fact and the body text appear in both forms."""
    case = EVENTS[kind]
    rendered = notification_email(kind=kind, recipient_name="Alex", **case)
    flattened = html_to_text(rendered.html)

    assert case["body"] in rendered.text
    assert case["body"] in flattened
    for label, value in case["facts"]:
        assert label in rendered.text and value in rendered.text
        assert label in flattened and value in flattened


@pytest.mark.parametrize("kind", list(EVENTS), ids=lambda kind: kind.value)
def test_every_email_links_back_to_the_page_it_is_about(kind):
    """A relative path is useless in an inbox; the link has to be absolute."""
    case = EVENTS[kind]
    rendered = notification_email(kind=kind, recipient_name="Alex", **case)
    expected = absolute_url(case["link"])

    assert expected is not None and expected.startswith("http")
    assert expected in rendered.html
    # In the text too, and on its own line: a link nobody can click is a link
    # somebody has to be able to copy.
    assert expected in rendered.text


@pytest.mark.parametrize("kind", list(EVENTS), ids=lambda kind: kind.value)
def test_the_subject_names_the_event_and_the_product(kind):
    rendered = notification_email(kind=kind, recipient_name="Alex", **EVENTS[kind])
    assert EVENTS[kind]["title"] in rendered.subject
    assert "UEP EMMY" in rendered.subject


def test_a_clinical_message_says_it_is_not_a_diagnosis():
    rendered = notification_email(
        kind=NotificationKind.VET_NOTE_ADDED, **EVENTS[NotificationKind.VET_NOTE_ADDED]
    )
    assert NOT_A_DIAGNOSIS in rendered.text
    assert NOT_A_DIAGNOSIS in html_to_text(rendered.html)


def test_a_purely_administrative_message_does_not():
    """The sentence has to mean something, which means not being on everything."""
    rendered = notification_email(
        kind=NotificationKind.MODERATION_DECISION,
        **EVENTS[NotificationKind.MODERATION_DECISION],
    )
    assert NOT_A_DIAGNOSIS not in rendered.text


def test_the_recipients_name_is_used_when_we_have_it():
    with_name = notification_email(
        kind=NotificationKind.APPOINTMENT_CONFIRMED,
        recipient_name="Alex",
        **EVENTS[NotificationKind.APPOINTMENT_CONFIRMED],
    )
    without = notification_email(
        kind=NotificationKind.APPOINTMENT_CONFIRMED,
        **EVENTS[NotificationKind.APPOINTMENT_CONFIRMED],
    )
    assert "Hello Alex," in with_name.text
    assert "Hello," in without.text


def test_content_is_escaped_rather_than_injected():
    """A pet called `<script>` must not become one."""
    rendered = notification_email(
        kind=NotificationKind.REMINDER_DUE,
        title="Reminder: <script>alert(1)</script>",
        body="Due for <b>Buddy & Co</b>.",
        link="/calendar",
    )
    assert "<script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html
    assert "&amp;" in rendered.html
    # The text part is not HTML, so it keeps the characters as typed.
    assert "<b>Buddy & Co</b>" in rendered.text


def test_a_notification_email_carries_a_reason_and_a_way_out():
    rendered = notification_email(
        kind=NotificationKind.REMINDER_DUE, **EVENTS[NotificationKind.REMINDER_DUE]
    )
    assert "You are receiving this because" in rendered.text
    assert absolute_url("/settings") in rendered.text


# ------------------------------------------------------------------- security


def test_the_verification_email_carries_the_link_and_the_expiry():
    rendered = verify_email(recipient_name="Alex", token="tok-123")
    expected = absolute_url("/verify-email?token=tok-123")

    assert expected in rendered.html and expected in rendered.text
    assert "expires" in rendered.text.lower()
    assert "Confirm" in rendered.subject


def test_the_change_email_is_addressed_to_the_new_address():
    rendered = verify_new_email(
        recipient_name="Alex", token="tok-456", new_email="new@example.com"
    )
    assert "new@example.com" in rendered.text
    assert absolute_url("/verify-email?token=tok-456") in rendered.text
    # Says plainly that nothing has changed yet, because that is the whole
    # difference between this email and the one above.
    assert "until you confirm" in rendered.text.lower()


def test_the_reset_email_says_what_to_do_if_it_was_not_you():
    rendered = password_reset(recipient_name="Alex", token="tok-789")
    assert absolute_url("/reset-password?token=tok-789") in rendered.text
    assert "did not ask for this" in rendered.text
    assert "only be used once" in rendered.text


@pytest.mark.parametrize(
    "rendered",
    [
        verify_email(recipient_name="Alex", token="t"),
        verify_new_email(recipient_name="Alex", token="t", new_email="new@example.com"),
        password_reset(recipient_name="Alex", token="t"),
    ],
    ids=["verify", "change", "reset"],
)
def test_security_email_never_offers_to_switch_itself_off(rendered):
    """These are not preferences. Offering a settings link would imply they are."""
    assert absolute_url("/settings") not in rendered.text
    assert absolute_url("/settings") not in rendered.html


def test_the_expiry_is_said_in_a_unit_a_person_would_use():
    reset = password_reset(recipient_name="Alex", token="t")
    verify = verify_email(recipient_name="Alex", token="t")
    settings = get_settings()

    assert f"{settings.password_reset_ttl_minutes} minute" in reset.text
    # 48 hours reads as "2 days", not "48 hours" and certainly not "2880 minutes".
    assert f"{settings.verify_email_ttl_hours // 24} day" in verify.text


# --------------------------------------------------------------- the envelope


def test_the_message_carries_text_and_html_as_alternatives():
    """`multipart/alternative`, text first: a client picks the last part it knows."""
    sender = EmailSender()
    message = sender.build_message(
        to="alex@example.com", subject="Hello", text="plain", html="<p>rich</p>"
    )

    assert message.get_content_type() == "multipart/alternative"
    parts = [part.get_content_type() for part in message.iter_parts()]
    assert parts == ["text/plain", "text/html"]


def test_a_message_with_no_html_is_still_a_valid_plain_message():
    sender = EmailSender()
    message = sender.build_message(to="alex@example.com", subject="Hello", text="plain")

    assert message.get_content_type() == "text/plain"
    assert "plain" in message.get_content()


def test_every_message_carries_the_configured_sender():
    sender = EmailSender()
    message = sender.build_message(to="alex@example.com", subject="Hi", text="x")

    assert message["From"] == get_settings().smtp_from
    # Marked as machine-generated, which is what keeps transactional mail out of
    # a promotions tab and stops an out-of-office replying to it.
    assert message["Auto-Submitted"] == "auto-generated"
    assert message["Message-ID"]


def test_an_absolute_link_is_left_alone():
    assert absolute_url("https://example.com/x") == "https://example.com/x"
    assert absolute_url(None) is None


def test_a_content_object_with_nothing_optional_still_renders():
    """The minimum: a heading and nothing else must not produce a broken page."""
    rendered = render(EmailContent(subject="s", heading="Just a heading"))
    assert "Just a heading" in rendered.text
    assert "Just a heading" in html_to_text(rendered.html)

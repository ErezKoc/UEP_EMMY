"""What our emails look like, in both of the forms a mail client may read.

One layout for everything the platform sends, and every message goes out as
`multipart/alternative` with a real plain-text part beside the HTML. That is
not a nicety: a mail client with images off, a screen reader in plain-text
mode, and every "view original" pane render the text part, and an HTML-only
message shows them nothing at all.

Two rules the templates are built around.

**The email says the same thing as the in-app alert.** The body a notification
already carries is the body the email carries, plus a heading, the details as
labelled facts, and a link back. Writing a second set of words per event is how
the two drift until "why does the email say something different" becomes a bug
report.

**Nothing here is a diagnosis, and messages carrying clinical wording say so.**
The platform's whole position is that it assists rather than decides; an email
is read away from the interface that says it, so the sentence travels with the
message.

There are no marketing emails. Every template here is transactional - the
consequence of something the reader or somebody they deal with did - which is
why the footer explains the cause rather than offering to sell anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape, unescape

from app.core.config import get_settings
from app.models.notification import NotificationKind

#: The sentence that has to travel with anything a veterinarian wrote or the
#: platform inferred. Deliberately one sentence and deliberately plain: a
#: paragraph of hedging at the bottom of every email is a paragraph nobody
#: reads.
NOT_A_DIAGNOSIS = (
    "This is a record of what was said on UEP EMMY, not a diagnosis. "
    "If your pet's condition changes or you are worried, contact your "
    "veterinary practice directly."
)

_BRAND = "UEP EMMY"
_TAGLINE = "AI-assisted veterinary platform"

# Colours pulled from the app's own palette so an email does not look like it
# came from somewhere else. Inline styles rather than a stylesheet: most mail
# clients strip <style> blocks, and a <head> is not guaranteed to survive at all.
_INK = "#1e293b"
_MUTED = "#64748b"
_LINE = "#e2e8f0"
_ACCENT = "#0d9488"
_PAGE = "#f1f5f9"


@dataclass(frozen=True)
class RenderedEmail:
    """One message, ready for the queue."""

    subject: str
    html: str
    text: str


@dataclass
class EmailContent:
    """What a message says, before it is dressed in a layout.

    Kept apart from the rendering so the two output forms cannot disagree:
    both are generated from this one object, and a fact added to the HTML
    without the text is not expressible.
    """

    subject: str
    heading: str
    #: Paragraphs, in order. Plain sentences - no markup.
    paragraphs: list[str] = field(default_factory=list)
    #: Labelled details: ("Pet", "Buddy"), ("When", "12 Sep 2026 at 09:30").
    #: A small table in HTML, "Label: value" lines in text.
    facts: list[tuple[str, str]] = field(default_factory=list)
    action_label: str | None = None
    #: App-relative ("/appointments") or absolute. Turned into a real URL
    #: against `frontend_base_url` at render time.
    action_path: str | None = None
    #: A highlighted caution, when there is one. The not-a-diagnosis sentence
    #: goes here.
    note: str | None = None
    #: Why this person is receiving this, in the footer. Every transactional
    #: email owes the reader that sentence.
    reason: str = "You are receiving this because of activity on your UEP EMMY account."
    #: Whether the footer points at the notification settings. False for
    #: security mail, which cannot be switched off and must not imply it can.
    show_preferences_link: bool = True


def absolute_url(path: str | None) -> str | None:
    """Turn "/calendar" into a link a mail client can actually open.

    Relative links do not work in email - there is no page to be relative to -
    so anything that is not already absolute is joined onto the configured
    frontend origin.
    """
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = get_settings().frontend_base_url.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def render(content: EmailContent) -> RenderedEmail:
    """One `EmailContent`, in both forms."""
    url = absolute_url(content.action_path)
    return RenderedEmail(
        subject=content.subject,
        html=_render_html(content, url),
        text=_render_text(content, url),
    )


# ------------------------------------------------------------------- rendering


def _render_html(content: EmailContent, url: str | None) -> str:
    parts: list[str] = []
    parts.append(
        f'<h1 style="margin:0 0 16px;font-size:20px;line-height:1.3;color:{_INK};'
        f'font-weight:700;">{escape(content.heading)}</h1>'
    )
    for paragraph in content.paragraphs:
        parts.append(
            f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;color:{_INK};">'
            f"{escape(paragraph)}</p>"
        )

    if content.facts:
        rows = "".join(
            f'<tr><td style="padding:6px 16px 6px 0;font-size:13px;color:{_MUTED};'
            f'vertical-align:top;white-space:nowrap;">{escape(label)}</td>'
            f'<td style="padding:6px 0;font-size:14px;color:{_INK};">{escape(value)}</td></tr>'
            for label, value in content.facts
        )
        parts.append(
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            f'style="width:100%;margin:0 0 18px;border-top:1px solid {_LINE};'
            f'border-bottom:1px solid {_LINE};padding:6px 0;">{rows}</table>'
        )

    if url and content.action_label:
        # A bordered anchor rather than a <button>: buttons do nothing in mail
        # clients, and several strip them entirely.
        parts.append(
            f'<p style="margin:0 0 18px;"><a href="{escape(url, quote=True)}" '
            f'style="display:inline-block;background:{_ACCENT};color:#ffffff;'
            f"text-decoration:none;padding:11px 20px;border-radius:8px;font-size:15px;"
            f'font-weight:600;">{escape(content.action_label)}</a></p>'
        )
        # The same link in the open, because a fair number of clients will not
        # make the block above clickable and "the button does nothing" is then
        # a dead end.
        parts.append(
            f'<p style="margin:0 0 18px;font-size:12px;line-height:1.5;color:{_MUTED};'
            f'word-break:break-all;">Or paste this into your browser:<br>'
            f'<a href="{escape(url, quote=True)}" style="color:{_ACCENT};">'
            f"{escape(url)}</a></p>"
        )

    if content.note:
        parts.append(
            f'<p style="margin:0 0 8px;padding:12px 14px;background:#fffbeb;'
            f'border-left:3px solid #f59e0b;border-radius:4px;font-size:13px;'
            f'line-height:1.55;color:#78350f;">{escape(content.note)}</p>'
        )

    body = "".join(parts)
    footer = escape(content.reason)
    if content.show_preferences_link:
        settings_url = absolute_url("/settings")
        footer += (
            f' You can change which emails you get in '
            f'<a href="{escape(settings_url or "", quote=True)}" '
            f'style="color:{_MUTED};">your notification settings</a>.'
        )

    return (
        f'<div style="margin:0;padding:24px 12px;background:{_PAGE};'
        f'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,'
        f'Helvetica,Arial,sans-serif;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:560px;margin:0 auto;width:100%;">'
        f'<tr><td style="padding:0 0 16px;">'
        f'<span style="font-size:15px;font-weight:700;color:{_ACCENT};'
        f'letter-spacing:0.02em;">{_BRAND}</span>'
        f'<span style="font-size:12px;color:{_MUTED};"> &middot; {_TAGLINE}</span>'
        f"</td></tr>"
        f'<tr><td style="background:#ffffff;border:1px solid {_LINE};border-radius:14px;'
        f'padding:28px 26px;">{body}</td></tr>'
        f'<tr><td style="padding:16px 4px 0;font-size:12px;line-height:1.55;'
        f'color:{_MUTED};">{footer}</td></tr>'
        f"</table></div>"
    )


def _render_text(content: EmailContent, url: str | None) -> str:
    lines: list[str] = [content.heading, "=" * min(len(content.heading), 60), ""]
    for paragraph in content.paragraphs:
        lines.extend([paragraph, ""])

    if content.facts:
        width = max(len(label) for label, _ in content.facts)
        lines.extend(f"{label.ljust(width)}  {value}" for label, value in content.facts)
        lines.append("")

    if url:
        if content.action_label:
            lines.append(f"{content.action_label}:")
        lines.extend([url, ""])

    if content.note:
        lines.extend([content.note, ""])

    lines.append("-" * 60)
    reason = content.reason
    if content.show_preferences_link:
        settings_url = absolute_url("/settings")
        reason += f" Change which emails you get: {settings_url}"
    lines.append(reason)
    lines.append(f"{_BRAND} - {_TAGLINE}")
    return "\n".join(lines).strip() + "\n"


# -------------------------------------------------------------- notifications

#: What the button says, per event. A specific verb beats "Open UEP EMMY":
#: the reader decides whether to click from this label alone.
_ACTION_LABELS: dict[NotificationKind, str] = {
    NotificationKind.REMINDER_DUE: "Open your calendar",
    NotificationKind.APPOINTMENT_REQUESTED: "Review the request",
    NotificationKind.APPOINTMENT_CONFIRMED: "See the appointment",
    NotificationKind.APPOINTMENT_DECLINED: "See the appointment",
    NotificationKind.APPOINTMENT_CANCELLED: "See the appointment",
    NotificationKind.APPOINTMENT_RESCHEDULE_PROPOSED: "Answer the new time",
    NotificationKind.APPOINTMENT_RESCHEDULED: "See the new time",
    NotificationKind.APPOINTMENT_RESCHEDULE_DECLINED: "See the appointment",
    NotificationKind.APPOINTMENT_MESSAGE: "Read and reply",
    NotificationKind.VET_NOTE_ADDED: "Read the note",
    NotificationKind.VERIFICATION_APPROVED: "See your verification",
    NotificationKind.VERIFICATION_REJECTED: "See your verification",
    NotificationKind.VERIFICATION_REVOKED: "See your verification",
    NotificationKind.MODERATION_DECISION: "Open your account",
}

#: Why this landed in their inbox, per event.
_REASONS: dict[NotificationKind, str] = {
    NotificationKind.REMINDER_DUE: (
        "You are receiving this because you asked to be reminded about your pet's care."
    ),
    NotificationKind.APPOINTMENT_MESSAGE: (
        "You are receiving this because you are on this appointment."
    ),
    NotificationKind.VET_NOTE_ADDED: (
        "You are receiving this because a note was added to your pet's record."
    ),
    NotificationKind.VERIFICATION_APPROVED: (
        "You are receiving this because you asked us to verify your veterinary licence."
    ),
    NotificationKind.VERIFICATION_REJECTED: (
        "You are receiving this because you asked us to verify your veterinary licence."
    ),
    NotificationKind.VERIFICATION_REVOKED: (
        "You are receiving this because it affects your veterinarian account."
    ),
    NotificationKind.MODERATION_DECISION: (
        "You are receiving this because it affects your UEP EMMY account."
    ),
}

#: Events where somebody clinical wrote something, or where the message
#: contains a judgement about an animal. These carry the disclaimer; a
#: cancellation or a request does not, because there is nothing clinical in it
#: and the sentence would just become wallpaper.
_NEEDS_DISCLAIMER = {
    NotificationKind.VET_NOTE_ADDED,
    NotificationKind.APPOINTMENT_MESSAGE,
    NotificationKind.APPOINTMENT_CONFIRMED,
    NotificationKind.APPOINTMENT_DECLINED,
    NotificationKind.REMINDER_DUE,
}


def notification_email(
    *,
    kind: NotificationKind,
    title: str,
    body: str,
    link: str | None = None,
    facts: list[tuple[str, str]] | None = None,
    recipient_name: str | None = None,
) -> RenderedEmail:
    """The email for one in-app notification.

    Built from the notification's own title and body on purpose. The
    alternative - a bespoke template per event - means two sets of words for
    every event, and the day somebody fixes the wording in one of them the
    email and the bell start disagreeing about what happened.

    `facts` is what an email can carry that a one-line alert cannot: the pet's
    name, the date, the practice. Callers pass what they have; nothing here
    invents a value it was not given.
    """
    greeting = f"Hello {recipient_name}," if recipient_name else "Hello,"
    return render(
        EmailContent(
            subject=f"{title} - {_BRAND}",
            heading=title,
            paragraphs=[greeting, body],
            facts=facts or [],
            action_label=_ACTION_LABELS.get(kind, "Open UEP EMMY"),
            action_path=link or "/dashboard",
            note=NOT_A_DIAGNOSIS if kind in _NEEDS_DISCLAIMER else None,
            reason=_REASONS.get(
                kind,
                "You are receiving this because of activity on your UEP EMMY account.",
            ),
        )
    )


# ------------------------------------------------------------------- security


def verify_email(*, recipient_name: str, token: str) -> RenderedEmail:
    """Prove the address an account signed up with."""
    return render(
        EmailContent(
            subject=f"Confirm your email address - {_BRAND}",
            heading="Confirm your email address",
            paragraphs=[
                f"Hello {recipient_name},",
                "Please confirm this is your address so we can send you reminders "
                "about your pets and updates about your appointments.",
                _expiry_sentence(get_settings().verify_email_ttl_hours * 60),
                "If you did not create a UEP EMMY account, you can ignore this "
                "message and nothing further will happen.",
            ],
            action_label="Confirm my email address",
            action_path=f"/verify-email?token={token}",
            reason="You are receiving this because this address was used to sign up "
            "for UEP EMMY.",
            show_preferences_link=False,
        )
    )


def verify_new_email(*, recipient_name: str, token: str, new_email: str) -> RenderedEmail:
    """Prove a NEW address before it replaces the one on the account."""
    return render(
        EmailContent(
            subject=f"Confirm your new email address - {_BRAND}",
            heading="Confirm your new email address",
            paragraphs=[
                f"Hello {recipient_name},",
                f"Somebody asked to change the email address on a UEP EMMY account "
                f"to {new_email}. The account keeps its current address until you "
                f"confirm this one.",
                _expiry_sentence(get_settings().verify_email_ttl_hours * 60),
                "If this was not you, ignore this message. The address on the "
                "account will not change.",
            ],
            action_label="Confirm this address",
            action_path=f"/verify-email?token={token}",
            reason="You are receiving this because this address was entered as a new "
            "sign-in address for a UEP EMMY account.",
            show_preferences_link=False,
        )
    )


def password_reset(*, recipient_name: str, token: str) -> RenderedEmail:
    """The one email in the system that is itself a credential."""
    minutes = get_settings().password_reset_ttl_minutes
    return render(
        EmailContent(
            subject=f"Reset your password - {_BRAND}",
            heading="Reset your password",
            paragraphs=[
                f"Hello {recipient_name},",
                "Somebody asked to reset the password for this UEP EMMY account. "
                "Use the link below to choose a new one.",
                _expiry_sentence(minutes)
                + " It can only be used once, and using it signs out nothing else "
                "you have open.",
                "If you did not ask for this, you can ignore this message - your "
                "password has not changed and nobody can use this link without "
                "your inbox.",
            ],
            action_label="Choose a new password",
            action_path=f"/reset-password?token={token}",
            reason="You are receiving this because a password reset was requested "
            "for this address.",
            show_preferences_link=False,
        )
    )


def _expiry_sentence(minutes: int) -> str:
    """"This link expires in 48 hours." - said in whichever unit reads naturally."""
    if minutes >= 120 and minutes % 60 == 0:
        hours = minutes // 60
        if hours % 24 == 0:
            days = hours // 24
            return f"This link expires in {days} day{'s' if days != 1 else ''}."
        return f"This link expires in {hours} hours."
    return f"This link expires in {minutes} minute{'s' if minutes != 1 else ''}."


def html_to_text(html: str) -> str:
    """Strip tags, for tests and for anything that needs a rough plain form.

    Not used to BUILD the text part - that is rendered from the same content
    object, which is the only way the two stay in step. This exists so a test
    can assert that a fact present in the HTML is present in the text.
    """
    without_tags = re.sub(r"<[^>]+>", " ", html)
    # Entities come back out. An apostrophe leaves the renderer as `&#x27;`,
    # and a comparison against the text part would fail on the punctuation
    # rather than on anything anybody cares about.
    return re.sub(r"\s+", " ", unescape(without_tags)).strip()

"""Handing one message to a mail server, or writing down the one we would send.

Two backends, chosen by whether SMTP is configured:

* **SMTP** when `smtp_host` is set. The real thing.
* **Outbox** otherwise: the message is written to a file as a complete `.eml`
  and logged. Nothing is silently dropped, and nothing pretends to have been
  delivered.

The outbox exists because this platform runs in Docker with no mail credentials
and has to be demonstrable anyway. The alternative designs are both worse: an
SMTP call that fails on every notification fills the logs with tracebacks and
teaches everyone to ignore them, and a no-op "sender" that returns success is a
lie the rest of the code then builds on.

Nothing here decides WHETHER to send, retries, or waits. This module puts one
message on the wire and reports what happened; `email_queue` owns the queue,
the backoff, and the preferences.

**Logging.** Recipients are masked and bodies are never logged. A password
reset link lives in a body, and an application log is the one place it must not
also live - it is copied to aggregators, tailed in shared terminals, and kept
long after the token has expired.
"""

from __future__ import annotations

import logging
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def mask_email(address: str) -> str:
    """Turn an address into something a log can carry.

    "alex.smith@example.com" becomes "al***@example.com": enough to recognise a
    row you are looking for, not enough to harvest. Used everywhere this module
    or the queue writes a log line.
    """
    address = (address or "").strip()
    local, separator, domain = address.partition("@")
    if not separator:
        return "***"
    keep = local[:2]
    return f"{keep}***@{domain}" if keep else f"***@{domain}"


@dataclass(frozen=True)
class SendResult:
    """What happened, in enough detail to explain it to somebody."""

    delivered: bool
    #: "smtp" or "outbox" - which backend handled it.
    backend: str
    #: Where it went, or why it did not go. Never contains a body or a
    #: credential: SMTP failures are reported as exception type plus message,
    #: and smtplib puts neither the password nor the payload in either.
    detail: str
    #: Whether this deployment can send mail at all. False means the outbox
    #: took it, which is not a failure and must never be reported as one - the
    #: distinction is what lets the interface say "this server cannot send
    #: email" instead of "your email failed".
    configured: bool = True

    @property
    def retryable(self) -> bool:
        """Is trying again later worth anything?

        Not for the outbox: with no SMTP host there is nothing to retry
        against, and re-queueing would write the same file every minute
        forever.
        """
        return self.configured and not self.delivered


class EmailSender:
    def __init__(self) -> None:
        settings = get_settings()
        self.host = (settings.smtp_host or "").strip()
        self.port = settings.smtp_port
        self.username = settings.smtp_username or None
        self.password = settings.smtp_password or None
        self.use_tls = settings.smtp_use_tls
        self.use_ssl = settings.smtp_use_ssl
        self.timeout = max(1, settings.smtp_timeout_seconds)
        self.sender = settings.smtp_from
        self.outbox = Path(settings.storage_root) / "outbox"

    @property
    def configured(self) -> bool:
        return bool(self.host)

    def build_message(
        self, *, to: str, subject: str, text: str, html: str | None = None
    ) -> EmailMessage:
        """One message carrying both bodies.

        Plain text is set first and HTML added as the alternative, which is the
        order `multipart/alternative` requires: a reader picks the LAST part it
        understands. Sending HTML only would leave a text-only client, a screen
        reader in plain-text mode, and every "show original" view with nothing
        readable at all.
        """
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=False)
        # A stable, unique id per message. Without one some servers generate
        # their own and threading breaks; with one, a delivery log can be
        # matched back to a row.
        message["Message-ID"] = make_msgid(domain="uepemmy.local")
        # These are transactional, never marketing (there are no marketing
        # emails in this system). The header says so, which is part of what
        # keeps a password reset out of the promotions tab.
        message["Auto-Submitted"] = "auto-generated"
        message.set_content(text)
        if html:
            message.add_alternative(html, subtype="html")
        return message

    def send(
        self,
        to: str,
        subject: str,
        body: str | None = None,
        *,
        text: str | None = None,
        html: str | None = None,
    ) -> SendResult:
        """Deliver one message.

        `body` is the original positional argument and is treated as the plain
        text part, so callers written before HTML existed keep working.
        """
        text_body = text if text is not None else (body or "")
        message = self.build_message(to=to, subject=subject, text=text_body, html=html)

        if not self.configured:
            return self._write_to_outbox(message, to, subject)

        try:
            with self._connect() as server:
                if self.use_tls and not self.use_ssl:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(message)
            logger.info("Email sent to %s via %s:%s.", mask_email(to), self.host, self.port)
            return SendResult(True, "smtp", f"sent via {self.host}:{self.port}")
        except Exception as error:
            # Never raised onwards. A notification whose email failed is still a
            # notification the person should see in the app, and letting this
            # propagate would abandon the in-app half over a mail server being
            # down. The failure is recorded, not hidden.
            #
            # Type and message only, and the recipient masked: an SMTP error can
            # echo the envelope back at us, and this line ends up in a log
            # aggregator.
            logger.warning(
                "Email to %s failed (%s): %s", mask_email(to), type(error).__name__, error
            )
            return SendResult(False, "smtp", f"{type(error).__name__}: {error}")

    def _connect(self) -> smtplib.SMTP:
        """Port 465 wants TLS from the first byte; 587 wants STARTTLS after EHLO."""
        if self.use_ssl:
            return smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
        return smtplib.SMTP(self.host, self.port, timeout=self.timeout)

    def _write_to_outbox(self, message: EmailMessage, to: str, subject: str) -> SendResult:
        try:
            self.outbox.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = self.outbox / f"{stamp}-{uuid.uuid4().hex[:8]}.eml"
            path.write_text(message.as_string(), encoding="utf-8")
            # Logged as well as written, so the demo can show it without going
            # into the container. The subject and a masked recipient are the
            # parts anybody watching actually wants; the body stays in the file,
            # because a verification link in the log is a verification link in
            # every system the log is shipped to.
            logger.info(
                "No SMTP configured; wrote %s - to %s: %s", path, mask_email(to), subject
            )
            return SendResult(False, "outbox", str(path), configured=False)
        except Exception as error:
            logger.warning("Could not write the outbox file: %s", error)
            return SendResult(
                False, "outbox", f"{type(error).__name__}: {error}", configured=False
            )


_sender: EmailSender | None = None


def get_email_sender() -> EmailSender:
    """One sender, built on first use so settings are read after the env is up."""
    global _sender
    if _sender is None:
        _sender = EmailSender()
    return _sender

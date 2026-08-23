"""Sending an email, or writing down the one we would have sent.

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
"""

from __future__ import annotations

import logging
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendResult:
    """What happened, in enough detail to explain it to somebody."""

    delivered: bool
    #: "smtp" or "outbox" - which backend handled it.
    backend: str
    #: Where it went, or why it did not go.
    detail: str


class EmailSender:
    def __init__(self) -> None:
        settings = get_settings()
        self.host = (settings.smtp_host or "").strip()
        self.port = settings.smtp_port
        self.username = settings.smtp_username or None
        self.password = settings.smtp_password or None
        self.use_tls = settings.smtp_use_tls
        self.sender = settings.smtp_from
        self.outbox = Path(settings.storage_root) / "outbox"

    @property
    def configured(self) -> bool:
        return bool(self.host)

    def send(self, to: str, subject: str, body: str) -> SendResult:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        message.set_content(body)

        if not self.configured:
            return self._write_to_outbox(message, to, subject)

        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(message)
            return SendResult(True, "smtp", f"sent to {to} via {self.host}:{self.port}")
        except Exception as error:
            # Never raised onwards. A notification whose email failed is still a
            # notification the person should see in the app, and letting this
            # propagate would abandon the in-app half over a mail server being
            # down. The failure is recorded, not hidden.
            logger.warning("Email to %s failed (%s): %s", to, type(error).__name__, error)
            return SendResult(False, "smtp", f"{type(error).__name__}: {error}")

    def _write_to_outbox(self, message: EmailMessage, to: str, subject: str) -> SendResult:
        try:
            self.outbox.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            path = self.outbox / f"{stamp}-{uuid.uuid4().hex[:8]}.eml"
            path.write_text(message.as_string(), encoding="utf-8")
            # Logged as well as written, so the demo can show it without going
            # into the container: the subject and recipient are the parts
            # anybody watching actually wants to see.
            logger.info("Email not sent (no SMTP configured). Wrote %s - to %s: %s", path, to, subject)
            return SendResult(False, "outbox", str(path))
        except Exception as error:
            logger.warning("Could not write the outbox file: %s", error)
            return SendResult(False, "outbox", f"{type(error).__name__}: {error}")


_sender: EmailSender | None = None


def get_email_sender() -> EmailSender:
    """One sender, built on first use so settings are read after the env is up."""
    global _sender
    if _sender is None:
        _sender = EmailSender()
    return _sender

"""The SMTP connectivity check.

Its whole job is to turn one unhelpful failure into one actionable sentence, so
what is worth testing is that it refuses the configurations that *look* fine and
are not — a blank password behind a set username connects and negotiates TLS
perfectly well, and then refuses every message that is ever sent.
"""

from __future__ import annotations

import smtplib
import socket

import pytest

from app.core.config import Settings, get_settings
from app.scripts import check_smtp


@pytest.fixture(autouse=True)
def settings_from(monkeypatch):
    """Replace the cached settings with whatever a test asks for."""

    def use(**overrides):
        settings = Settings(**overrides)
        monkeypatch.setattr(check_smtp, "get_settings", lambda: settings)
        # `EmailSender.__init__` reads the real accessor.
        monkeypatch.setattr("app.services.email.get_settings", lambda: settings)
        return settings

    yield use
    get_settings.cache_clear()


def test_no_host_is_reported_as_the_outbox_rather_than_an_error(settings_from, capsys):
    settings_from(smtp_host="")

    assert check_smtp.describe_configuration() is False

    printed = capsys.readouterr().out
    assert "does not send email" in printed
    assert "app.scripts.outbox" in printed


def test_a_username_with_no_password_is_refused(settings_from, capsys):
    """The failure this check exists for.

    Connecting and negotiating STARTTLS both succeed without a password, so a
    naive check prints "SMTP is working" about a server that will reject the
    first real message. Half-configured credentials have to fail here.
    """
    settings_from(smtp_host="smtp.example.com", smtp_username="me@example.com", smtp_password="")

    assert check_smtp.describe_configuration() is False

    printed = capsys.readouterr().out
    assert "SMTP_PASSWORD is empty" in printed
    assert "App Password" in printed


def test_a_password_with_no_username_is_refused(settings_from, capsys):
    settings_from(smtp_host="smtp.example.com", smtp_username="", smtp_password="secret")

    assert check_smtp.describe_configuration() is False
    assert "SMTP_USERNAME is empty" in capsys.readouterr().out


def test_a_complete_configuration_is_accepted(settings_from):
    settings_from(
        smtp_host="smtp.example.com",
        smtp_username="me@example.com",
        smtp_password="0123456789abcdef",
    )

    assert check_smtp.describe_configuration() is True


def test_the_password_is_never_printed(settings_from, capsys):
    """Not even back to the person who set it - this output gets pasted around."""
    settings_from(
        smtp_host="smtp.example.com",
        smtp_username="me@example.com",
        smtp_password="hunter2-secret-value",
    )

    check_smtp.describe_configuration()

    printed = capsys.readouterr().out
    assert "hunter2-secret-value" not in printed
    # The length is shown, which is what catches a stray space or leftover quotes.
    assert "20 characters" in printed


def test_whitespace_in_the_password_is_called_out(settings_from, capsys):
    """Gmail shows app passwords in groups of four; people paste the spaces."""
    settings_from(
        smtp_host="smtp.example.com",
        smtp_username="me@example.com",
        smtp_password="abcd efgh ijkl mnop ",
    )

    check_smtp.describe_configuration()

    assert "leading or trailing whitespace" in capsys.readouterr().out


@pytest.mark.parametrize(
    "error,expected",
    [
        (smtplib.SMTPAuthenticationError(535, b"nope"), "App Password"),
        (smtplib.SMTPNotSupportedError("no starttls"), "implicit TLS"),
        (socket.gaierror("name or service not known"), "could not be resolved"),
        (ConnectionRefusedError("refused"), "Nothing is listening"),
        (TimeoutError("timed out"), "firewall"),
    ],
    ids=["auth", "starttls", "dns", "refused", "timeout"],
)
def test_each_common_failure_gets_advice_naming_the_setting(error, expected):
    """The server's own message is usually useless; this is the translation."""
    assert expected in check_smtp._advise(error)


def test_an_unrecognised_failure_says_so_rather_than_guessing(settings_from):
    assert "No specific advice" in check_smtp._advise(RuntimeError("something odd"))


def test_a_failure_to_connect_is_reported_and_exits_nonzero(settings_from, capsys, monkeypatch):
    settings_from(
        smtp_host="smtp.example.com",
        smtp_username="me@example.com",
        smtp_password="0123456789abcdef",
    )

    def _refuse(self):
        raise ConnectionRefusedError("nothing there")

    monkeypatch.setattr("app.services.email.EmailSender._connect", _refuse)

    assert check_smtp.check() == 1

    printed = capsys.readouterr().out
    assert "FAILED at this step" in printed
    assert "Nothing is listening" in printed

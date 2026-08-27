"""Check that this deployment can actually reach its mail server.

Run this after putting SMTP settings in `.env` and before wondering why nothing
arrived. It does the same three things the queue does - connect, secure the
connection, authenticate - and says which one failed, in words that point at the
setting to change.

    python -m app.scripts.check_smtp                    # connect and log in
    python -m app.scripts.check_smtp --send you@you.com # and send one real email

Without this, a wrong app password and a blocked port and a bad `SMTP_FROM` all
look identical from inside the application: messages sit in `email_messages`
with `state = failed` and a one-line error nobody reads until somebody asks why
the platform is quiet.

**The password is never printed**, not even masked back to you in full, and it
is never taken as an argument - it is read from settings, which read `.env`.
Passing a credential on a command line writes it into shell history and into
the process list, where anybody on the machine can read it.
"""

from __future__ import annotations

import argparse
import smtplib
import socket
import ssl
import sys
from datetime import datetime, timezone

from app.core.config import get_settings
from app.services.email import EmailSender, mask_email

#: What each failure usually means, and the setting to look at. Keyed by
#: exception type, because the server's own message is frequently useless
#: ("5.7.8 Username and Password not accepted" tells you nothing about app
#: passwords).
_ADVICE: dict[type[BaseException], str] = {
    smtplib.SMTPAuthenticationError: (
        "The server refused SMTP_USERNAME / SMTP_PASSWORD.\n"
        "  * Gmail: this must be a 16-character App Password, not your account\n"
        "    password. App passwords need 2-Step Verification switched on first.\n"
        "  * Check the username is the full address, not just the local part."
    ),
    smtplib.SMTPNotSupportedError: (
        "The server does not support what was asked of it.\n"
        "  * If this happened at STARTTLS: the port probably wants implicit TLS.\n"
        "    Try SMTP_PORT=465 with SMTP_USE_SSL=true and SMTP_USE_TLS=false."
    ),
    smtplib.SMTPSenderRefused: (
        "The server would not accept SMTP_FROM as a sender.\n"
        "  * It usually has to match the authenticated account, or be a domain\n"
        "    the relay is allowed to send for."
    ),
    socket.gaierror: (
        "SMTP_HOST could not be resolved. Check it for typos, and check this\n"
        "  machine has DNS."
    ),
    ConnectionRefusedError: (
        "Nothing is listening on SMTP_HOST:SMTP_PORT.\n"
        "  * Wrong port, or the service is not running (Mailpit not started?)."
    ),
    TimeoutError: (
        "The connection timed out. Usually a firewall, or an ISP blocking\n"
        "  outbound port 25/587."
    ),
    ssl.SSLError: (
        "TLS failed while connecting.\n"
        "  * Port 587 wants SMTP_USE_TLS=true (STARTTLS after connecting).\n"
        "  * Port 465 wants SMTP_USE_SSL=true (TLS from the first byte).\n"
        "  * Setting both is not the same as setting one; SSL wins."
    ),
}


def _advise(error: BaseException) -> str:
    for kind, advice in _ADVICE.items():
        if isinstance(error, kind):
            return advice
    return "No specific advice for this one - the server's message is above."


def describe_configuration() -> bool:
    """Print the resolved settings. Returns whether sending is switched on."""
    settings = get_settings()
    sender = EmailSender()

    print("Configuration (from backend/.env):")
    print(f"  SMTP_HOST     {settings.smtp_host or '(empty)'}")
    print(f"  SMTP_PORT     {settings.smtp_port}")
    print(f"  SMTP_USERNAME {mask_email(settings.smtp_username) if settings.smtp_username else '(empty)'}")
    # Length only. Enough to catch a pasted password with a stray space or the
    # quotes left on, which is the common mistake, without printing a secret.
    password = settings.smtp_password or ""
    print(f"  SMTP_PASSWORD {f'set, {len(password)} characters' if password else '(empty)'}")
    print(f"  SMTP_USE_TLS  {settings.smtp_use_tls}")
    print(f"  SMTP_USE_SSL  {settings.smtp_use_ssl}")
    print(f"  SMTP_FROM     {settings.smtp_from}")
    print(f"  FRONTEND_BASE_URL {settings.frontend_base_url}")
    print()

    if not sender.configured:
        print("SMTP_HOST is empty, so this deployment does not send email.")
        print("Messages are written to the local outbox instead:")
        print(f"  {sender.outbox}")
        print("Read them with: python -m app.scripts.outbox --links")
        print()
        print("To send for real, set SMTP_HOST (and the rest) in backend/.env,")
        print("then restart the backend - settings are read once, at startup.")
        return False

    if password and password != password.strip():
        print("WARNING: SMTP_PASSWORD has leading or trailing whitespace.")
        print("  Gmail app passwords are shown in groups of four; paste them")
        print("  without the spaces.")
        print()

    # Half-configured credentials, which is the state a half-finished setup
    # leaves behind. Worth failing on rather than warning about: the connection
    # and STARTTLS both succeed without a password, so the check would
    # otherwise print "SMTP is working" about a server that will refuse every
    # message the moment one is actually sent.
    if settings.smtp_username and not password:
        print("SMTP_USERNAME is set but SMTP_PASSWORD is empty.")
        print()
        print("Almost every real mail server refuses to send without both. Put a")
        print("password in backend/.env and run this again:")
        print("  * Gmail wants a 16-character App Password, not your account")
        print("    password. Google Account -> Security -> 2-Step Verification")
        print("    -> App passwords. 2-Step Verification has to be on first.")
        print()
        print("(If your relay really does authenticate by IP, clear SMTP_USERNAME")
        print(" too, so the two settings agree.)")
        return False
    if password and not settings.smtp_username:
        print("SMTP_PASSWORD is set but SMTP_USERNAME is empty.")
        print("Set the username to the full address the password belongs to.")
        return False
    return True


def check(send_to: str | None = None) -> int:
    settings = get_settings()
    sender = EmailSender()

    print(f"Connecting to {sender.host}:{sender.port} ...")
    try:
        with sender._connect() as server:
            print("  connected.")
            if sender.use_tls and not sender.use_ssl:
                server.starttls()
                print("  STARTTLS negotiated.")
            elif sender.use_ssl:
                print("  TLS active from connect (implicit).")
            else:
                print("  WARNING: no TLS. Fine for a local capture server,")
                print("           never for a real one - the password crosses in clear.")

            if sender.username and sender.password:
                server.login(sender.username, sender.password)
                print("  authenticated.")
            else:
                print("  no credentials set; skipping login (relay must allow this).")

            if send_to:
                stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                message = sender.build_message(
                    to=send_to,
                    subject=f"UEP EMMY test message ({stamp})",
                    text=(
                        "This is a test from UEP EMMY.\n\n"
                        "If you are reading it, SMTP is configured correctly and "
                        "the platform can send verification links, password resets, "
                        "and reminder emails.\n\n"
                        f"Sent from {sender.host}:{sender.port} as {settings.smtp_from}.\n"
                        f"Links in real emails will point at {settings.frontend_base_url}\n"
                    ),
                    html=(
                        "<p>This is a test from <strong>UEP EMMY</strong>.</p>"
                        "<p>If you are reading it, SMTP is configured correctly and the "
                        "platform can send verification links, password resets, and "
                        "reminder emails.</p>"
                        f"<p style='color:#64748b;font-size:13px'>Sent from {sender.host}:"
                        f"{sender.port}. Links in real emails will point at "
                        f"{settings.frontend_base_url}</p>"
                    ),
                )
                server.send_message(message)
                print(f"  test message accepted for {mask_email(send_to)}.")
    except Exception as error:
        print()
        print(f"FAILED at this step: {type(error).__name__}: {error}")
        print()
        print(_advise(error))
        return 1

    print()
    print("SMTP is working.")
    if send_to:
        print(f"Check the inbox for {mask_email(send_to)} (and its spam folder).")
    print()
    print("Restart the backend if it is running - settings are read at startup.")
    if settings.frontend_base_url.startswith("http://localhost"):
        print()
        print("NOTE: FRONTEND_BASE_URL is still localhost, so links inside real")
        print("      emails only work on this machine. Fine for testing; set it")
        print("      to the public address before anybody else receives one.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.check_smtp",
        description="Check that the configured mail server can be reached and logged into.",
    )
    parser.add_argument(
        "--send",
        metavar="ADDRESS",
        help="Also send one real test message to this address.",
    )
    args = parser.parse_args(argv)

    if not describe_configuration():
        return 1
    return check(args.send)


if __name__ == "__main__":  # pragma: no cover - a command-line entry point
    sys.exit(main())

"""The local outbox: the fallback, and the way to read it.

With no SMTP server this is the entire delivery mechanism, so "can somebody
actually get the verification link out of it" is a functional question rather
than a convenience one — a link that only exists inside a quoted-printable blob
nobody can read is a link that does not exist.
"""

from __future__ import annotations

import pytest

from app.scripts import outbox as outbox_script
from app.services.email import EmailSender


@pytest.fixture
def sender(tmp_path, monkeypatch):
    """A sender with no SMTP host, writing into a temporary outbox."""
    made = EmailSender()
    made.host = ""
    made.outbox = tmp_path / "outbox"
    monkeypatch.setattr(outbox_script, "outbox_dir", lambda: made.outbox)
    return made


def test_a_message_with_no_smtp_is_written_rather_than_lost(sender):
    result = sender.send(
        to="alex@example.com",
        subject="Confirm your email address",
        text="Open http://localhost:5173/verify-email?token=abc",
        html="<p>Open it</p>",
    )

    assert result.delivered is False
    # Not a failure: there is nothing here to fail against, and reporting one
    # sends somebody looking for a fault that does not exist.
    assert result.configured is False
    assert result.retryable is False
    assert len(list(sender.outbox.glob("*.eml"))) == 1


def test_the_written_file_is_a_real_email_with_both_bodies(sender):
    sender.send(
        to="alex@example.com",
        subject="Confirm your email address",
        text="plain version",
        html="<p>rich version</p>",
    )

    path = next(iter(sender.outbox.glob("*.eml")))
    message = outbox_script.read(path)

    assert message["To"] == "alex@example.com"
    assert message["Subject"] == "Confirm your email address"
    assert "plain version" in outbox_script.body(message, "plain")
    assert "rich version" in outbox_script.body(message, "html")


def test_the_reader_pulls_the_link_out_for_clicking(sender):
    """The point of the tool: a token wrapped across two lines is unusable."""
    link = "http://localhost:5173/verify-email?token=" + "x" * 60
    sender.send(to="alex@example.com", subject="Confirm", text=f"Open {link} now.", html="")

    path = next(iter(sender.outbox.glob("*.eml")))
    assert outbox_script.links(outbox_script.read(path)) == [link]


def test_a_trailing_full_stop_is_not_part_of_the_link(sender):
    link = "http://localhost:5173/reset-password?token=abc"
    sender.send(to="alex@example.com", subject="Reset", text=f"Open {link}.", html="")

    path = next(iter(sender.outbox.glob("*.eml")))
    assert outbox_script.links(outbox_script.read(path)) == [link]


def test_listing_an_empty_outbox_says_so_rather_than_failing(sender, capsys):
    assert outbox_script.main([]) == 0
    assert "No messages" in capsys.readouterr().out


def test_the_listing_shows_who_each_message_was_for(sender, capsys):
    sender.send(to="alex@example.com", subject="First", text="one", html="")
    sender.send(to="sam@example.com", subject="Second", text="two", html="")

    assert outbox_script.main([]) == 0

    printed = capsys.readouterr().out
    assert "alex@example.com" in printed
    assert "sam@example.com" in printed
    assert "First" in printed and "Second" in printed


def test_showing_one_message_prints_both_bodies_and_its_links(sender, capsys):
    sender.send(
        to="alex@example.com",
        subject="Confirm",
        text="Open http://localhost:5173/verify-email?token=abc",
        html="<p>Open it</p>",
    )

    assert outbox_script.main(["--show", "1"]) == 0

    printed = capsys.readouterr().out
    assert "plain text" in printed
    assert "html (raw)" in printed
    assert "http://localhost:5173/verify-email?token=abc" in printed


def test_asking_for_a_message_that_is_not_there_fails_politely(sender, capsys):
    sender.send(to="alex@example.com", subject="Only one", text="x", html="")

    assert outbox_script.main(["--show", "9"]) == 1
    assert "no message 9" in capsys.readouterr().out.lower()


def test_the_links_flag_prints_only_links(sender, capsys):
    sender.send(
        to="alex@example.com",
        subject="Confirm",
        text="Hello. Open http://localhost:5173/verify-email?token=abc please.",
        html="",
    )

    assert outbox_script.main(["--links"]) == 0
    assert capsys.readouterr().out.strip() == "http://localhost:5173/verify-email?token=abc"


def test_an_unwritable_outbox_is_reported_rather_than_raised(sender, monkeypatch):
    """A broken outbox must not take the notification down with it."""

    def _refuse(*args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr("pathlib.Path.mkdir", _refuse)

    result = sender.send(to="alex@example.com", subject="Confirm", text="x", html="")

    assert result.delivered is False
    assert result.configured is False
    assert "OSError" in result.detail


def test_the_newest_message_wins_even_within_the_same_second(sender):
    """`--show 1` must be the one just written, not the one that sorts higher.

    The filenames carry a UTC timestamp to the second and then random hex, so
    two messages queued in the same second - a signup and a password reset, say
    - came out in an arbitrary order under a name sort. Somebody following the
    documented "read the newest one" workflow then read the wrong link.
    """
    import os

    sender.send(to="alex@example.com", subject="Older", text="one", html="")
    sender.send(to="alex@example.com", subject="Newer", text="two", html="")

    # Stamp the mtimes by which message each file actually holds. Both names
    # already carry the same second; the random suffix decides their name
    # order, which is precisely the thing that must not decide the listing.
    for path in sender.outbox.glob("*.eml"):
        subject = outbox_script.read(path)["Subject"]
        when = 1_000_000 if subject == "Older" else 1_000_001
        os.utime(path, (when, when))

    newest = outbox_script.read(outbox_script.messages()[0])
    assert newest["Subject"] == "Newer"

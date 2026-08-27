"""Read the local outbox: what this deployment would have emailed.

With no SMTP server configured, every message is written to
`<storage_root>/outbox` as a complete `.eml` file. That is a real, valid email —
headers, both bodies, working links — and it is the whole reason the outbox
exists rather than a no-op sender that returns success and teaches everyone to
trust a lie.

The files are plain text, so `cat` works. This exists because `cat` on a
`multipart/alternative` message shows quoted-printable soup with the link
wrapped across two lines, which is exactly the part somebody opening the file
came to read.

    python -m app.scripts.outbox              # newest first, one line each
    python -m app.scripts.outbox --show 1     # one message in full
    python -m app.scripts.outbox --links      # just the links, for clicking

Nothing here writes, sends, or deletes anything.
"""

from __future__ import annotations

import argparse
import re
import sys
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from app.core.config import get_settings

_LINK = re.compile(r"https?://\S+")


def outbox_dir() -> Path:
    return Path(get_settings().storage_root) / "outbox"


def messages() -> list[Path]:
    """Every `.eml` in the outbox, newest first.

    Sorted by modification time, with the name as a tiebreak. The filenames
    carry a UTC timestamp but only to the second, and the rest is random hex -
    so two messages written in the same second (a signup queues one, a
    password reset queues another) sorted by name alone came out in an
    arbitrary order, and `--show 1` showed whichever happened to sort higher
    rather than the one that had just been written.
    """
    directory = outbox_dir()
    if not directory.is_dir():
        return []
    return sorted(
        directory.glob("*.eml"), key=lambda path: (path.stat().st_mtime, path.name), reverse=True
    )


def read(path: Path) -> EmailMessage:
    with path.open("rb") as handle:
        return BytesParser(policy=policy.default).parse(handle)


def body(message: EmailMessage, subtype: str) -> str:
    """One part of a message, decoded. Empty when the message has no such part."""
    part = message.get_body(preferencelist=(subtype,))
    return part.get_content() if part is not None else ""


def links(message: EmailMessage) -> list[str]:
    """Every distinct link, in the order they appear in the plain-text part."""
    seen: list[str] = []
    for match in _LINK.findall(body(message, "plain")):
        cleaned = match.rstrip(".,)")
        if cleaned not in seen:
            seen.append(cleaned)
    return seen


def _list(paths: list[Path]) -> None:
    for index, path in enumerate(paths, start=1):
        message = read(path)
        print(f"{index:>3}  {message['Date']}  ->  {message['To']}")
        print(f"     {message['Subject']}")
        print(f"     {path.name}")


def _show(path: Path) -> None:
    message = read(path)
    print(f"File:    {path}")
    print(f"From:    {message['From']}")
    print(f"To:      {message['To']}")
    print(f"Date:    {message['Date']}")
    print(f"Subject: {message['Subject']}")
    print()
    print("--- plain text " + "-" * 55)
    print(body(message, "plain").strip())
    html = body(message, "html")
    if html:
        print()
        print("--- html (raw) " + "-" * 55)
        print(html.strip())
    found = links(message)
    if found:
        print()
        print("--- links " + "-" * 60)
        for link in found:
            print(link)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.scripts.outbox",
        description="Inspect the local email outbox (used when no SMTP is configured).",
    )
    parser.add_argument(
        "--show",
        type=int,
        metavar="N",
        help="Print message N from the listing in full (1 is the newest).",
    )
    parser.add_argument(
        "--links",
        action="store_true",
        help="Print only the links from the newest message, one per line.",
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="How many to list (default 20)."
    )
    args = parser.parse_args(argv)

    paths = messages()
    if not paths:
        print(f"No messages in {outbox_dir()}.")
        print("Nothing has been sent yet, or SMTP is configured and mail is going out for real.")
        return 0

    if args.links:
        for link in links(read(paths[0])):
            print(link)
        return 0

    if args.show is not None:
        if not 1 <= args.show <= len(paths):
            print(f"There is no message {args.show}; the outbox holds {len(paths)}.")
            return 1
        _show(paths[args.show - 1])
        return 0

    print(f"{len(paths)} message(s) in {outbox_dir()}, newest first:")
    print()
    _list(paths[: args.limit])
    if len(paths) > args.limit:
        print(f"\n... and {len(paths) - args.limit} more. Use --limit to see them.")
    print("\nUse --show N to read one in full.")
    return 0


if __name__ == "__main__":  # pragma: no cover - a command-line entry point
    sys.exit(main())

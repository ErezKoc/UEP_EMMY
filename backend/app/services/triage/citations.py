"""Provenance for clinical rules.

Every triage rule states which published source its clinical claim comes from,
with the URL and the date the page was read. A rule without a citation is an
invented medical opinion, so the type refuses to be built without one and the
test suite refuses placeholders.

A citation has two states:

1. **Retrieved** — the page was fetched and read, and the URL and access date
   are recorded. Every shipping rule is at least here.
2. **Verified** — a named person on the team independently opened the source,
   confirmed it supports the exact claim the rule makes, and signed it with
   `verified_by`. Nothing is here yet.

`TRIAGE_REQUIRE_VERIFIED_RULES=true` refuses to start the engine until every
rule reaches state 2, so unchecked clinical logic cannot reach real users.
"""

from dataclasses import dataclass
from datetime import date

# Words that indicate a citation was left as a reminder rather than filled in.
_PLACEHOLDER_MARKERS = ("todo", "fixme", "tbd", "xxx", "lorem", "...", "???", "example.org")


@dataclass(frozen=True)
class Citation:
    """Where a rule's clinical claim comes from.

    `supports` is a short paraphrase, in our own words, of what the source
    actually says. It exists so a reviewer can check a rule against its source
    without re-reading the whole page.
    """

    source: str
    url: str
    accessed: date
    supports: str
    species: frozenset[str] | None = None
    verified_by: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("source", "url", "supports"):
            value = getattr(self, field_name)
            if not value or not value.strip():
                raise ValueError(f"Citation is missing {field_name}.")
            if _looks_like_placeholder(value):
                raise ValueError(f"Citation {field_name} looks like a placeholder: {value!r}")
        if not self.url.startswith("https://"):
            raise ValueError(f"Citation url must be a real https link, got {self.url!r}")

    @property
    def is_verified(self) -> bool:
        """True once a named human has confirmed the source supports the claim."""
        return bool(self.verified_by)

    def describe(self) -> str:
        state = f"verified by {self.verified_by}" if self.verified_by else "not yet verified by the team"
        scope = "all animals" if self.species is None else ", ".join(sorted(self.species))
        return f"{self.source} ({self.url}, species: {scope}; read {self.accessed}; {state})"


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)

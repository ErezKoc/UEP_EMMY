"""One place that decides what an owner's species answer means.

`species` reaches the triage engine from three directions — typed into the
symptom form, copied off a saved pet, or guessed by the image model — and each
of them can deliver the same animal spelled differently. Before this module
existed the rule table compared species in two places with two different
normalisations, so a pet saved as `" cat "` matched the cat-only rules'
*species scope* but failed the `SpeciesIs` condition inside them, and a cat that
had not eaten for over a day came back with no rules fired at all.

Two functions, deliberately separated:

* `normalise_species` answers "which animal is this, for matching evidence to?"
  It returns `None` for anything that means "the owner did not tell us",
  including the placeholder words a free-text field collects in practice.
* `clean_species_label` answers "what should we store and show?" It tidies
  whitespace and nothing else, because the owner's own capitalisation of their
  pet's species is theirs to keep.
"""

from __future__ import annotations

#: Words a free-text species field collects that mean "not told", not a species.
#: An owner typing any of these has answered the question with a non-answer, and
#: treating it as an unrecognised animal would silence every rule we have.
UNKNOWN_SPECIES_PLACEHOLDERS = frozenset(
    {
        "unknown",
        "unsure",
        "not sure",
        "not_sure",
        "notsure",
        "dont know",
        "don't know",
        "other",
        "n/a",
        "na",
        "none",
        "null",
        "-",
        "--",
        "?",
    }
)


def clean_species_label(raw: str | None) -> str | None:
    """Tidy a species for storage and display, preserving the owner's casing."""
    if raw is None:
        return None
    collapsed = " ".join(raw.split())
    return collapsed or None


def normalise_species(raw: str | None) -> str | None:
    """The species to match evidence against, or `None` when it is unknown.

    Trims and collapses whitespace, compares case-insensitively, and maps the
    placeholder answers in `UNKNOWN_SPECIES_PLACEHOLDERS` to `None`. Returning
    `None` is what lets dog-and-cat evidence still apply: guidance a source
    states for both species does not stop being true because we failed to ask
    which one.
    """
    cleaned = clean_species_label(raw)
    if cleaned is None:
        return None
    token = cleaned.casefold()
    if token in UNKNOWN_SPECIES_PLACEHOLDERS:
        return None
    return token


def species_matches(raw: str | None, scope: frozenset[str] | None) -> bool:
    """Does this species fall inside a rule's or a source's species scope?

    `scope is None` means the evidence explicitly covers every species, so it
    applies whatever the owner said — including when they said nothing.
    """
    if scope is None:
        return True
    species = normalise_species(raw)
    if species is None:
        return False
    return species in scope

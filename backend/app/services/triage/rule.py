"""The rule type.

Two kinds of rule:

* **Emergency rules** carry `level_override=RED`. They short-circuit the whole
  assessment — if one fires, nothing else can talk the result down.
* **Weighted rules** contribute to a score. The score maps to amber or green.

Both kinds require at least one citation; a rule cannot be constructed without
one, so an uncited clinical claim is a runtime error rather than an oversight.
"""

from dataclasses import dataclass, field

from app.core.species import normalise_species
from app.schemas.triage import SymptomIntake, TriageLevel
from app.services.triage.citations import Citation
from app.services.triage.conditions import Condition
from app.services.triage.sources import ALL_SPECIES, DOG_AND_CAT


@dataclass(frozen=True)
class Rule:
    id: str
    condition: Condition
    message: str
    citations: tuple[Citation, ...]
    weight: int = 0
    level_override: TriageLevel | None = None
    #: Which animals this rule's evidence covers. `ALL_SPECIES` (None) means the
    #: cited page states its claim for every species, so the rule applies to any
    #: animal an owner names — including one we have no other evidence for.
    #: Spelling that as `None` rather than listing species keeps us from
    #: guessing which exotic pets exist; the source's own scope decides.
    applies_to_species: frozenset[str] | None = DOG_AND_CAT
    headline: str | None = None
    advice: str | None = None
    urgent_care_signs: tuple[str, ...] = ()
    care_instructions: tuple[str, ...] = ()
    # Free-text note for the reviewing veterinarian; not shown to users.
    reviewer_note: str = field(default="")

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError(f"Rule {self.id!r} has no citation. Every clinical claim needs a source.")
        if self.level_override is None and self.weight <= 0:
            raise ValueError(f"Rule {self.id!r} must either override the level or carry a weight.")
        if self.level_override is not None and self.weight != 0:
            raise ValueError(
                f"Rule {self.id!r} overrides the level, so its weight is meaningless; leave it at 0."
            )
        if self.applies_to_species is not None and not self.applies_to_species:
            raise ValueError(f"Rule {self.id!r} must declare at least one supported species.")
        if self.applies_to_species is None:
            # A rule for every animal may only rest on evidence that itself
            # claims every animal. Anything narrower would be us extending a
            # dog-and-cat page to a species it never mentions.
            narrow = [c.source for c in self.citations if c.species is not None]
            if narrow:
                raise ValueError(
                    f"Rule {self.id!r} applies to all species, but {', '.join(narrow)} "
                    "covers only some. Narrow the rule or cite an all-species source."
                )
            return
        for citation in self.citations:
            if citation.species is not None and not self.applies_to_species <= citation.species:
                unsupported = ", ".join(sorted(self.applies_to_species - citation.species))
                raise ValueError(
                    f"Rule {self.id!r} applies to {unsupported}, but citation "
                    f"{citation.source!r} does not. Narrow the rule or use a matching source."
                )

    @property
    def is_species_specific(self) -> bool:
        """True when the rule's evidence covers only some of the species we serve."""
        return self.applies_to_species is not None and self.applies_to_species != DOG_AND_CAT

    @property
    def applies_to_every_species(self) -> bool:
        return self.applies_to_species is None

    def matches(self, intake: SymptomIntake) -> bool:
        # One shared normalisation for the whole system — see app/core/species.py.
        # `SpeciesIs` uses the same function, so a rule's species scope and the
        # conditions inside it can no longer disagree about what " Cat " means.
        species = normalise_species(intake.species)

        if self.applies_to_every_species:
            # The source states its claim for every animal, so nothing about the
            # species — named, unnamed or unrecognised — can withhold it.
            return self.condition.matches(intake)

        if species is None:
            # Species unknown — the owner chose "not sure", left it blank, or
            # typed a placeholder, and no pet was linked.
            #
            # Requiring a known species here used to silently disable the ENTIRE
            # rule table, so an owner reporting suspected poisoning with blood in
            # the vomit was told "we can't assess this one". Guidance that its
            # own source states for both dogs and cats does not stop applying
            # because we failed to ask which one; withholding it adds no safety.
            #
            # Rules narrowed to one species stay out, because we genuinely cannot
            # tell whether they apply. (Rules that narrow species inside their
            # condition, via SpeciesIs, exclude themselves for the same reason.)
            if self.is_species_specific:
                return False
            return self.condition.matches(intake)

        return species in self.applies_to_species and self.condition.matches(intake)

    @property
    def is_emergency(self) -> bool:
        return self.level_override is TriageLevel.RED

    @property
    def is_verified(self) -> bool:
        """True when every citation has been checked by a named person."""
        return all(citation.is_verified for citation in self.citations)

    @property
    def is_extrapolation(self) -> bool:
        """True when the rule goes further than its source literally states.

        Flagged in the review document so a veterinarian can see exactly where
        we reasoned beyond the published wording.
        """
        return self.reviewer_note.startswith("EXTRAPOLATION")

    def describe(self) -> str:
        """One auditable English sentence, for veterinarian review."""
        effect = (
            f"treat as {self.level_override.value.upper()}"
            if self.level_override
            else f"add {self.weight} to the concern score"
        )
        sources = "; ".join(citation.describe() for citation in self.citations)
        flag = " [EXTRAPOLATION — needs review]" if self.is_extrapolation else ""
        species = (
            "any animal" if self.applies_to_every_species else "/".join(sorted(self.applies_to_species))
        )
        return f"For {species}: if {self.condition.describe()}, {effect}.{flag} Source: {sources}"

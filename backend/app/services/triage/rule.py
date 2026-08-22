"""The rule type.

Two kinds of rule:

* **Emergency rules** carry `level_override=RED`. They short-circuit the whole
  assessment — if one fires, nothing else can talk the result down.
* **Weighted rules** contribute to a score. The score maps to amber or green.

Both kinds require at least one citation; a rule cannot be constructed without
one, so an uncited clinical claim is a runtime error rather than an oversight.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from app.core.species import normalise_species
from app.schemas.triage import (
    DiagnosticEvidence,
    ExtrapolationKind,
    RedFlag,
    SymptomIntake,
    TriageLevel,
    UrgencyEvidence,
)
from app.services.triage.citations import Citation
from app.services.triage.conditions import Condition
from app.services.triage.sources import ALL_SPECIES, DOG_AND_CAT


#: How each sign reads back to the owner, in the words the form used to offer
#: it. Only signs a rule quotes need an entry; `RedFlag.value` is the fallback.
SIGN_PHRASES: dict[RedFlag, str] = {
    RedFlag.SKIN_ITCHING: "itching, licking or chewing",
    RedFlag.SKIN_REDNESS: "redness",
    RedFlag.SKIN_HAIR_LOSS: "hair loss",
    RedFlag.SKIN_RASH_OR_BUMPS: "a rash or bumps",
    RedFlag.SKIN_SCABS_OR_FLAKING: "scabs, crusts or flaking",
    RedFlag.SKIN_SWELLING: "swelling",
    RedFlag.SKIN_LUMP: "a lump",
    RedFlag.SKIN_NAIL_OR_PAD_CHANGE: "a change to a nail or paw pad",
    RedFlag.SKIN_OPEN_WOUND: "open or raw skin",
    RedFlag.SKIN_DISCHARGE_OR_PUS: "discharge or pus",
    RedFlag.SKIN_ODOR: "a bad smell",
    RedFlag.SKIN_CONTAGION: "a skin problem in another pet or a person at home",
    RedFlag.EYE_REDNESS: "redness",
    RedFlag.EYE_WATERING: "watering",
    RedFlag.EYE_IRRITATION: "rubbing or irritation",
    RedFlag.EYE_PAIN_OR_CLOSED: "squinting or holding the eye closed",
    RedFlag.EYE_CLOUDY_OR_BLUE: "a cloudy or blue area on the eye",
    RedFlag.UNEQUAL_PUPILS_OR_VISION_CHANGE: "unequal pupils or a change in vision",
    RedFlag.EYE_BULGING_OR_SEVERE_SWELLING: "bulging or marked swelling",
    RedFlag.EYE_DISCHARGE_YELLOW_GREEN_OR_BLOODY: "yellow-green or bloody discharge",
}


def _phrase_list(flags: Sequence[RedFlag]) -> str:
    """"a, b and c" — or a neutral stand-in when nothing was ticked."""
    phrases = [SIGN_PHRASES.get(flag, flag.value.replace("_", " ")) for flag in flags]
    if not phrases:
        return "what you described"
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


#: How each kind of step past a source reads to a reviewer.
_TRANSFORMATION_WORDS: dict[ExtrapolationKind, str] = {
    ExtrapolationKind.MAPPING: (
        "we classify the owner's answers into the category the source writes about"
    ),
    ExtrapolationKind.THRESHOLD: (
        "we decide that a presentation of this severity crosses the bar for an appointment; "
        "the source sets no such bar"
    ),
    ExtrapolationKind.RECOMMENDATION: (
        "we recommend more than the source recommends"
    ),
    ExtrapolationKind.TIMING: (
        "we name a timeframe the source does not give"
    ),
}


@dataclass(frozen=True)
class SupportedProposition:
    """One source, and the exact thing we say it supports."""

    source: str
    url: str
    accessed: date
    #: Our paraphrase of what the page states — the proposition, not the rule.
    proposition: str
    verified_by: str | None = None


@dataclass(frozen=True)
class RuleProvenance:
    """A rule's whole chain, in the order a reviewer checks it.

    source -> the proposition it supports -> the step we take past it -> who has
    signed any of it off. Each link was already present somewhere in this file;
    gathering them into one record is what makes a rule auditable without
    reading the rule table, and it is what `report.py` prints.
    """

    rule_id: str
    asserts: str
    propositions: tuple[SupportedProposition, ...]
    our_steps: tuple[str, ...]
    reviewer_note: str
    review_status: str

    def describe(self) -> str:
        lines = [f"[{self.rule_id}] ASSERTS: {self.asserts}"]
        for proposition in self.propositions:
            lines.append(f"    SOURCE SAYS: {proposition.proposition}")
            lines.append(
                f"        {proposition.source} ({proposition.url}; read {proposition.accessed})"
            )
        for step in self.our_steps:
            lines.append(f"    OUR STEP:    {step}")
        if not self.our_steps:
            lines.append("    OUR STEP:    none — the rule asserts what the sources assert.")
        lines.append(f"    REVIEW:      {self.review_status}")
        if self.reviewer_note:
            lines.append(f"    QUESTION:    {self.reviewer_note}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Rule:
    id: str
    condition: Condition
    message: str
    citations: tuple[Citation, ...]
    weight: int = 0
    level_override: TriageLevel | None = None
    #: Signs this rule will read back to the owner. When `message` contains
    #: `{reported}`, it is filled with the ones they actually ticked — so an
    #: explanation quotes the answers given rather than listing every sign the
    #: rule happens to cover. An owner who reported an itchy red patch was being
    #: told about hair loss, crusting, nodules and lumps as well.
    reported_signs: tuple[RedFlag, ...] = ()
    #: Whether a cited page says how soon. Defaults to "it does not", because
    #: that is the safe direction to be wrong in: it understates our evidence
    #: rather than inventing a deadline.
    urgency_evidence: UrgencyEvidence = UrgencyEvidence.NOT_STATED
    #: Whether a cited page describes how the cause is identified. Defaults to
    #: "it does not", so a rule has to claim this rather than inherit it.
    diagnostic_evidence: DiagnosticEvidence = DiagnosticEvidence.NOT_DESCRIBED
    #: Which steps past the source this rule takes, if any. A set, because a
    #: rule can take more than one and they land in different places in the
    #: confidence report: a mapping step is reported as source applicability, a
    #: threshold step as weaker evidence for the action, a timing step as weaker
    #: evidence for the urgency.
    extrapolations: frozenset[ExtrapolationKind] = frozenset()
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
    #: What the appointment itself involves. Explanatory, not instructions.
    what_to_expect: tuple[str, ...] = ()
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
        # The declared kind and the reviewer's note must agree, or the review
        # document says one thing and the confidence report another.
        if self.is_extrapolation and not self.reviewer_note.startswith("EXTRAPOLATION"):
            kinds = "/".join(sorted(kind.value for kind in self.extrapolations))
            raise ValueError(
                f"Rule {self.id!r} declares a {kinds} extrapolation but its reviewer note does "
                "not start with EXTRAPOLATION, so the review document will not explain it."
            )
        if self.reviewer_note.startswith("EXTRAPOLATION") and not self.is_extrapolation:
            raise ValueError(
                f"Rule {self.id!r} tells the reviewer it extrapolates but declares no kind. Set "
                "`extrapolations` so the confidence report can weigh it."
            )
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

    def message_for(self, intake: SymptomIntake) -> str:
        """The message with `{reported}` filled in from what the owner ticked."""
        if "{reported}" not in self.message:
            return self.message
        reported = [flag for flag in self.reported_signs if flag in intake.red_flags]
        return self.message.format(reported=_phrase_list(reported))

    @property
    def states_urgency(self) -> bool:
        """Does the evidence behind this rule say how soon, at all?

        Emergencies do by construction: `test_no_rule_asserts_an_urgency_its_
        sources_do_not_establish` proves each one cites a page using emergency
        language.
        """
        return self.is_emergency or self.urgency_evidence is UrgencyEvidence.STATED

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
        we reasoned beyond the published wording. `extrapolation` says which
        kind of step it is; the reviewer note spells it out in words.
        """
        return bool(self.extrapolations)

    @property
    def provenance(self) -> RuleProvenance:
        """The rule's evidence chain as data, not prose."""
        return RuleProvenance(
            rule_id=self.id,
            asserts=self._asserts(),
            propositions=tuple(
                SupportedProposition(
                    source=citation.source,
                    url=citation.url,
                    accessed=citation.accessed,
                    proposition=citation.supports,
                    verified_by=citation.verified_by,
                )
                for citation in self.citations
            ),
            our_steps=tuple(
                _TRANSFORMATION_WORDS[kind]
                for kind in sorted(self.extrapolations, key=lambda k: k.value)
            ),
            reviewer_note=self.reviewer_note,
            review_status=(
                "signed off by "
                + ", ".join(
                    sorted({c.verified_by for c in self.citations if c.verified_by})
                )
                if self.is_verified
                else "awaiting veterinary review"
            ),
        )

    def _asserts(self) -> str:
        effect = (
            f"treat as {self.level_override.value.upper()}"
            if self.level_override
            else f"add {self.weight} to the concern score"
        )
        species = (
            "any animal"
            if self.applies_to_every_species
            else "/".join(sorted(self.applies_to_species))
        )
        return f"for {species}, if {self.condition.describe()}, {effect}"

    def describe(self) -> str:
        """One auditable English sentence, for veterinarian review."""
        effect = (
            f"treat as {self.level_override.value.upper()}"
            if self.level_override
            else f"add {self.weight} to the concern score"
        )
        sources = "; ".join(citation.describe() for citation in self.citations)
        flag = (
            " [EXTRAPOLATION (" + "/".join(sorted(k.value for k in self.extrapolations))
            + ") — needs review]"
            if self.is_extrapolation
            else ""
        )
        species = (
            "any animal" if self.applies_to_every_species else "/".join(sorted(self.applies_to_species))
        )
        return f"For {species}: if {self.condition.describe()}, {effect}.{flag} Source: {sources}"

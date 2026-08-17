"""The triage engine.

Two tiers, evaluated in order:

1. **Emergency rules.** If any fires, the result is red and scoring stops
   mattering — nothing can talk an emergency sign down.
2. **Weighted rules.** Their weights sum into a concern score; at or above
   `AMBER_THRESHOLD` the result is amber, otherwise green.

Every fired rule is returned with its message and citation, so the user sees
exactly why they got the answer they got, and the reasoning can be audited.
"""

from collections.abc import Iterable

from app.core.config import get_settings
from app.schemas.triage import (
    Concern,
    FiredRule,
    SourceLink,
    SymptomIntake,
    TriageAssessment,
    TriageLevel,
)
from app.services.triage.rule import Rule
from app.services.triage.rules import ALL_RULES, AMBER_THRESHOLD

DISCLAIMER = (
    "This is triage guidance based on published veterinary sources, not a diagnosis. "
    "If you are worried about your pet, contact a veterinarian."
)

_HEADLINES: dict[TriageLevel, str] = {
    TriageLevel.RED: "Contact a vet today",
    TriageLevel.AMBER: "Worth a vet visit in the next few days",
    TriageLevel.GREEN: "You can monitor this at home for now",
    TriageLevel.UNASSESSED: "We can't assess this one",
}

_ADVICE: dict[TriageLevel, str] = {
    TriageLevel.RED: (
        "Call your veterinary practice now, or an out-of-hours emergency service if they are closed. "
        "Describe the signs you reported here."
    ),
    TriageLevel.AMBER: (
        "Contact your veterinary practice to arrange an appointment. Online advice can supplement "
        "an examination, but it should not replace or delay in-person care."
    ),
    TriageLevel.GREEN: (
        "Keep an eye on it and take another photo in about three days. If it spreads, gets worse, or "
        "your pet stops eating or becomes lethargic, check again."
    ),
    TriageLevel.UNASSESSED: (
        "None of our published sources cover what you described, so we are not going to guess. "
        "That is not the same as saying your pet is fine, and it is not a reason to wait. Contact "
        "your veterinary practice if you are worried, if your pet seems unwell, or if anything gets "
        "worse."
    ),
}


class UnverifiedRulesError(RuntimeError):
    """Raised at startup when strict mode is on but citations are unchecked."""


class TriageEngine:
    def __init__(self, rules: tuple[Rule, ...] = ALL_RULES, *, require_verified: bool | None = None):
        self.rules = rules
        if require_verified is None:
            require_verified = get_settings().triage_require_verified_rules
        if require_verified:
            unverified = [rule.id for rule in rules if not rule.is_verified]
            if unverified:
                raise UnverifiedRulesError(
                    "TRIAGE_REQUIRE_VERIFIED_RULES is on, but these rules still have unverified "
                    f"citations: {', '.join(unverified)}. Verify the sources or turn strict mode off "
                    "in development."
                )

    @property
    def fully_verified(self) -> bool:
        return all(rule.is_verified for rule in self.rules)

    def assess(self, intake: SymptomIntake) -> TriageAssessment:
        # Breed-only users never asked a health question; do not invent a verdict.
        # The test is "did they tell us anything at all", not just "did they tick
        # a red flag": someone who leaves the concern on breed-only but fills in
        # a duration and a worsening trend has described a problem, and answering
        # that with "No health concern reported" would be the same false
        # reassurance in a different wrapper.
        if intake.concern is Concern.BREED_ONLY and not _owner_reported_something(intake):
            return TriageAssessment(
                level=TriageLevel.GREEN,
                headline="No health concern reported",
                score=0,
                threshold=AMBER_THRESHOLD,
                fired_rules=[],
                advice=(
                    "You asked for a breed estimate only. If you are worried about something, "
                    "run the check again and describe the symptoms."
                ),
                disclaimer=DISCLAIMER,
                rules_fully_verified=self.fully_verified,
            )

        fired = [rule for rule in self.rules if rule.matches(intake)]
        emergencies = [rule for rule in fired if rule.is_emergency]

        # The owner described something and nothing in our sourced rules covers
        # it. There is no evidence here for any level, including the reassuring
        # one, so we refuse the scale rather than picking its calm end.
        #
        # This used to require `intake.red_flags` to be non-empty, which meant an
        # owner who chose "breathing", "worsening", and ticked no box fell
        # through to green and was told to monitor at home for three days.
        if not fired and _owner_reported_something(intake):
            return TriageAssessment(
                level=TriageLevel.UNASSESSED,
                headline=_HEADLINES[TriageLevel.UNASSESSED],
                score=0,
                threshold=AMBER_THRESHOLD,
                fired_rules=[],
                advice=_ADVICE[TriageLevel.UNASSESSED],
                disclaimer=DISCLAIMER,
                rules_fully_verified=self.fully_verified,
            )

        if emergencies:
            level = TriageLevel.RED
            # An emergency answer should show only the emergency reasons; the
            # minor contributors are noise when someone needs to act now.
            shown = emergencies
        elif fired:
            level = TriageLevel.AMBER if _score(fired) >= AMBER_THRESHOLD else TriageLevel.GREEN
            shown = sorted(fired, key=lambda rule: rule.weight, reverse=True)
        else:
            # Nothing fired and nothing was reported: the owner asked no health
            # question at all, so there is no verdict to give.
            level = TriageLevel.GREEN
            shown = []

        headline, advice = _headline_and_advice(shown, level)

        return TriageAssessment(
            level=level,
            headline=headline,
            # The score must equal the weights of the rules actually listed
            # below, or the owner cannot reconcile the number with the reasons.
            # In the emergency branch that is zero: emergencies carry no weight.
            score=_score(shown),
            threshold=AMBER_THRESHOLD,
            fired_rules=[
                FiredRule(
                    rule_id=rule.id,
                    message=rule.message,
                    weight=rule.weight,
                    sources=[citation.source for citation in rule.citations],
                    source_links=[
                        SourceLink(name=citation.source, url=citation.url)
                        for citation in rule.citations
                    ],
                )
                for rule in shown
            ],
            advice=advice,
            urgent_care_signs=_unique_items(
                sign for rule in shown for sign in rule.urgent_care_signs
            ),
            care_instructions=_unique_items(
                instruction for rule in shown for instruction in rule.care_instructions
            ),
            disclaimer=DISCLAIMER,
            rules_fully_verified=self.fully_verified,
        )


def provenance_report(rules: tuple[Rule, ...] = ALL_RULES) -> str:
    """The whole clinical logic as plain English, for veterinarian review."""
    from app.services.triage.candidates import CANDIDATE_RULES
    from app.services.triage.sources import ALL_SOURCES

    verified = [rule for rule in rules if rule.is_verified]
    extrapolations = [rule for rule in rules if rule.is_extrapolation]
    lines = [
        "UEP EMMY — triage rules for veterinary review",
        "",
        f"{len(rules)} rules ({len(verified)} verified by our team, "
        f"{len(rules) - len(verified)} awaiting verification).",
        f"{len(extrapolations)} rule(s) reason beyond the literal wording of their source and are"
        " marked EXTRAPOLATION below.",
        "",
        "SOURCES USED",
    ]
    lines += [
        f"  - {source.name} [{_species_label(source.species)}; read {source.accessed}]"
        f"\n    {source.url}"
        for source in ALL_SOURCES
    ]

    lines += ["", "EMERGENCY RULES (any one of these means 'contact a vet today')"]
    for rule in rules:
        if rule.is_emergency:
            lines.append(f"  - [{rule.id}] {rule.describe()}")
            if rule.reviewer_note:
                lines.append(f"      QUESTION: {rule.reviewer_note}")

    lines += ["", f"GRADED RULES (a score of {AMBER_THRESHOLD} or more means 'see a vet soon')"]
    for rule in rules:
        if not rule.is_emergency:
            lines.append(f"  - [{rule.id}] {rule.describe()}")
            if rule.reviewer_note:
                lines.append(f"      QUESTION: {rule.reviewer_note}")

    lines += [
        "",
        "NOT IN USE — we could not find a published source for these.",
        "They affect nothing today. Please tell us whether any is worth keeping.",
    ]
    for candidate in CANDIDATE_RULES:
        lines.append(f"  - [{candidate['id']}] {candidate['claim']}")
        lines.append(f"      QUESTION: {candidate['question_for_reviewer']}")
    return "\n".join(lines)


def _owner_reported_something(intake: SymptomIntake) -> bool:
    """Did the owner tell us anything about a health problem?

    Ticking no red flag is not evidence that nothing is wrong — it is often just
    an owner who did not recognise their pet's sign in our list. Any of these
    answers means they came here with a concern, and a concern we cannot cover
    must be declared, not answered with home-monitoring advice.
    """
    return bool(
        intake.red_flags
        or intake.concern is not Concern.BREED_ONLY
        or intake.body_area is not None
        or intake.duration is not None
        or intake.trend is not None
        or intake.time_since_eating is not None
        or intake.weight_bearing is False
    )


def _score(rules: Iterable[Rule]) -> int:
    return sum(rule.weight for rule in rules)


def _headline_and_advice(shown: list[Rule], level: TriageLevel) -> tuple[str, str]:
    """Pick the top line, preferring a generic one when systems disagree.

    A rule's own headline is only safe to show when it is the whole story. When
    a pet has trouble breathing AND a head tilt, the fired rules used to be read
    in table order and the answer came back headlined "Same-day urgent ear
    examination recommended" — pointing the owner at the wrong body system while
    the animal could not breathe. So a specific headline is used only when every
    reason shown agrees on it; otherwise the generic emergency line, which is
    correct for all of them.
    """
    headlines = {rule.headline for rule in shown if rule.headline}
    silent = any(rule.headline is None for rule in shown)
    headline = headlines.pop() if len(headlines) == 1 and not silent else _HEADLINES[level]

    advices = {rule.advice for rule in shown if rule.advice}
    silent_advice = any(rule.advice is None for rule in shown)
    advice = advices.pop() if len(advices) == 1 and not silent_advice else _ADVICE[level]

    return headline, advice


def _unique_items(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _species_label(species: frozenset[str] | None) -> str:
    return "all animals" if species is None else "/".join(sorted(species))


_engine: TriageEngine | None = None


def get_triage_engine() -> TriageEngine:
    """FastAPI dependency; built once so strict mode fails fast at first use."""
    global _engine
    if _engine is None:
        _engine = TriageEngine()
    return _engine

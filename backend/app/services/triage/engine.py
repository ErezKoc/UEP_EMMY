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
from app.core.species import normalise_species
from app.schemas.triage import (
    Concern,
    ConfidenceReport,
    DiagnosticEvidence,
    ExtrapolationKind,
    FiredRule,
    SourceLink,
    SymptomIntake,
    TriageAssessment,
    TriageLevel,
    UrgentSign,
)
from app.services.triage import confidence as confidence_module
from app.services.triage.rule import Rule
from app.services.triage.rules import (
    ALL_RULES,
    AMBER_THRESHOLD,
    GENERAL_EMERGENCY_NOTE,
    GENERAL_EMERGENCY_SIGNS,
)

DISCLAIMER = (
    "This is triage guidance based on published veterinary sources, not a diagnosis. "
    "If you are worried about your pet, contact a veterinarian."
)

_HEADLINES: dict[TriageLevel, str] = {
    # "today" and the advice line's "call now, or an out-of-hours service if
    # they are closed" were telling the owner two different things.
    TriageLevel.RED: "Contact a vet now",
    # No "in the next few days": that timeframe was ours, applied to every
    # amber result including ones whose sources give no timing at all.
    #
    # "Worth a vet visit" was a verdict on the problem where the owner needs an
    # instruction. It also hedged — "worth" invites a judgement call from the
    # person least equipped to make it. The line names the action instead, and
    # still names no timeframe, because none of the levels carry one.
    TriageLevel.AMBER: "Arrange a vet visit",
    TriageLevel.GREEN: "You can monitor this at home for now",
    # "this one" sounded like a quirk of an individual case. The problem is
    # that we cannot do it SAFELY, and the word is the difference between an
    # apology and a warning.
    TriageLevel.UNASSESSED: "We can't assess this safely",
}

def _screening_note(intake: SymptomIntake, note: str) -> str | None:
    """The screening line, but only for an owner who actually screened.

    An empty `red_flags` list is not an answer. It is what you get from someone
    who ticked nothing because nothing applied, AND from someone who never saw
    the question — a direct API call, a stored intake from before the emergency
    step existed, a client that skips it. Telling the second group "you did not
    select any of the emergency warning signs" is true only in the sense that a
    question nobody asked has no answer, and it reads as though we checked.

    So the line waits for `emergency_screen_answered`. Unknown means silence,
    which costs a sentence and never claims a screening that did not happen.
    """
    if not intake.emergency_screen_answered:
        return None
    return note


#: The first line of a non-emergency result, above everything else.
#:
#: An owner who has just answered a page of questions about seizures, collapse
#: and pale gums wants one thing settled before they read a word of evidence
#: reporting: did any of that apply. That was previously inferable only from
#: the card's colour and from the absence of alarm in three sections of prose,
#: while the emergency list — eleven signs, each with citations — sat below the
#: result whatever the owner had answered.
#:
#: Worded as what they told us and what our own screening then did, never as
#: "this is not an emergency" or "assessed as a non-emergency". Both of those
#: read as a clinical conclusion that emergencies have been excluded, and a
#: finite checklist coming back negative is not that: Merck's triage guidance
#: covers a far wider range of presentations needing immediate evaluation than
#: our form asks about, and we did not examine the animal at all. What we can
#: say is that nothing they reported matched an emergency trigger of ours.
_NO_EMERGENCY_SIGNS_NOTE = (
    "You did not select any of the emergency warning signs this checker asked about. This cannot "
    "rule out every emergency. If your pet worsens or you are worried, contact a veterinarian."
)

#: Same two facts, plus the one this branch exists to say. Kept apart from the
#: line above so neither has to carry the other's meaning.
_NO_EMERGENCY_SIGNS_NOTE_UNASSESSED = (
    "You did not select any of the emergency warning signs this checker asked about, and nothing "
    "else you described matched guidance this checker holds. This cannot rule out every "
    "emergency. If your pet worsens or you are worried, contact a veterinarian."
)

_ADVICE: dict[TriageLevel, str] = {
    # "Call your veterinary practice now" was the whole instruction, while a
    # heatstroke result three sections lower said to travel to a clinic while
    # cooling. The ASPCA's own advice is to transport the animal and have
    # someone else phone: "Once you feel confident and safe transporting your
    # pet, immediately bring him to an emergency care facility" and "Ask a
    # friend or family member to call the clinic so the staff knows to expect
    # you and your pet."
    # "the clinic will be expecting you" promised something the phone call does
    # not deliver: an emergency service can be full, or send you somewhere else,
    # and an owner who arrives to either has been told wrong by us at the worst
    # possible moment. What the ASPCA's advice actually gets you is that the
    # clinic knows, which is worth doing for a different reason — they can tell
    # you where to go.
    TriageLevel.RED: (
        "Take your pet to a veterinary clinic now, or contact an out-of-hours emergency service "
        "if your usual clinic is closed. If possible, call ahead and describe the signs you "
        "reported."
    ),
    TriageLevel.AMBER: (
        "Contact your veterinary practice to arrange an appointment. Online advice can supplement "
        "an examination, but it should not replace or delay in-person care."
    ),
    TriageLevel.GREEN: (
        "Keep an eye on it and take another photo in about three days. If it spreads, gets worse, or "
        "your pet stops eating or becomes lethargic, check again."
    ),
    # Deliberately says nothing about urgency, in either direction. An earlier
    # version ended "and it is not a reason to wait", which is a triage
    # recommendation — the one thing this branch exists because we cannot make.
    # It also used to say no published source covers the problem, which is not
    # true: veterinary literature covers these presentations extensively. What
    # is missing is a rule in OUR evidence library that matches the answers
    # given, and that is a limitation of this product, not of the field.
    TriageLevel.UNASSESSED: (
        "Your answers do not match guidance this checker can assess confidently. That is a gap in "
        "what this checker holds, not a sign that the problem is minor, and it does not mean the "
        "problem is safe to ignore. If you are worried, your pet is getting worse, or something "
        "does not seem right, contact a veterinarian. The signs listed below are ones our sources "
        "do cover, and they need emergency care whatever else is going on."
    ),
}

#: The same refusal, when the reason is the animal rather than the answers.
#:
#: The line above blames the answers - "your answers do not match guidance" -
#: which is simply untrue for an owner whose rabbit stopped eating two days ago.
#: They answered perfectly well. Every species-scoped rule we hold is about dogs
#: and cats, and no wording about their answers can tell them that.
#:
#: Deliberately makes no claim about the species itself. Rabbit gut stasis is
#: described as urgent in places, and `candidates.py` records it as a question
#: for a reviewer precisely because nobody here has sourced it; repeating it in
#: the one message an unsupported-species owner reads would be inventing exactly
#: the guidance this branch exists because we do not have.
#: Carries the same three promises the general wording makes, because the
#: safety suite pins them and it is right to: an abstention must name itself as
#: our gap, must not read as "nothing serious", and must still send the owner to
#: a veterinarian. Only the reason changes.
_UNASSESSED_UNSUPPORTED_SPECIES = (
    "The published guidance behind this checker covers dogs and cats, so none of it applies to "
    "{species}. That is a limit of what this checker holds, not a sign that the problem is minor, "
    "and it does not mean the problem is safe to ignore. Contact a veterinarian, ideally one who "
    "sees this species. The signs listed below come from sources that speak for animals "
    "generally, and they need emergency care whatever else is going on."
)


def _species_scoped_coverage(rules: Iterable[Rule]) -> frozenset[str]:
    """Every species some rule in the table holds specific evidence for.

    Derived from the table rather than written down beside it, so it cannot go
    stale: adding rabbit rules tomorrow makes rabbits supported here with no
    second edit. Rules scoped to `ALL_SPECIES` are excluded on purpose - they
    apply to every animal already, so counting them would mark every species as
    covered and this message would never be shown.
    """
    covered: set[str] = set()
    for rule in rules:
        if rule.applies_to_species is not None:
            covered |= rule.applies_to_species
    return frozenset(covered)


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

    def decide(self, intake: SymptomIntake) -> tuple[TriageLevel, list[Rule]]:
        """The level, and the rules to show for it. No wording, no confidence.

        Split out of `assess` so it can be replayed cheaply: the confidence
        report answers "which unanswered question would change this?" by
        filling each blank in and calling this again.
        """
        # Breed-only users never asked a health question; do not invent a verdict.
        # The test is "did they tell us anything at all", not just "did they tick
        # a red flag": someone who leaves the concern on breed-only but fills in
        # a duration and a worsening trend has described a problem, and answering
        # that with "No health concern reported" would be the same false
        # reassurance in a different wrapper.
        if intake.concern is Concern.BREED_ONLY and not _owner_reported_something(intake):
            return TriageLevel.GREEN, []

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
            return TriageLevel.UNASSESSED, []

        if emergencies:
            # An emergency answer should show only the emergency reasons; the
            # minor contributors are noise when someone needs to act now.
            return TriageLevel.RED, emergencies
        if fired:
            level = TriageLevel.AMBER if _score(fired) >= AMBER_THRESHOLD else TriageLevel.GREEN
            return level, sorted(fired, key=lambda rule: rule.weight, reverse=True)
        # Nothing fired and nothing was reported: the owner asked no health
        # question at all, so there is no verdict to give.
        return TriageLevel.GREEN, []

    def _unassessed_advice(self, intake: SymptomIntake) -> str:
        """Name the species as the reason, when it is the reason.

        Only when the owner actually told us the species AND we hold no
        species-scoped evidence for it. An unknown species falls through to the
        general wording: we cannot say the animal is unsupported when we were
        never told what it is.
        """
        species = normalise_species(intake.species)
        if species is None or species in _species_scoped_coverage(self.rules):
            return _ADVICE[TriageLevel.UNASSESSED]
        # The owner's own spelling, tidied - "my Rabbit" reads back as they
        # wrote it rather than as a normalised token.
        label = intake.species.strip() if intake.species else species
        return _UNASSESSED_UNSUPPORTED_SPECIES.format(species=f"a {label.lower()}")

    def assess(self, intake: SymptomIntake) -> TriageAssessment:
        level, shown = self.decide(intake)

        if level is TriageLevel.GREEN and not shown and intake.concern is Concern.BREED_ONLY:
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
                # Nothing was asked, so there is no answer to be confident about.
                confidence=None,
            )

        if level is TriageLevel.UNASSESSED:
            return TriageAssessment(
                level=TriageLevel.UNASSESSED,
                headline=_HEADLINES[TriageLevel.UNASSESSED],
                screening_note=_screening_note(intake, _NO_EMERGENCY_SIGNS_NOTE_UNASSESSED),
                score=0,
                threshold=AMBER_THRESHOLD,
                fired_rules=[],
                advice=self._unassessed_advice(intake),
                # Sourced independently of the problem we could not match, and
                # true regardless of it.
                urgent_care_signs=_general_emergency_signs(intake),
                urgent_care_note=GENERAL_EMERGENCY_NOTE,
                disclaimer=DISCLAIMER,
                rules_fully_verified=self.fully_verified,
                confidence=self._confidence(intake, level, shown),
            )

        headline, advice = _headline_and_advice(shown, level)
        advice = _with_threshold_caveat(advice, shown)

        return TriageAssessment(
            level=level,
            headline=headline,
            # Only on the levels where it is true. A red result reached this
            # line because an emergency rule fired, and the reassuring half of
            # this sentence is the last thing that owner should read.
            screening_note=(
                None
                if level is TriageLevel.RED
                else _screening_note(intake, _NO_EMERGENCY_SIGNS_NOTE)
            ),
            # The score must equal the weights of the rules actually listed
            # below, or the owner cannot reconcile the number with the reasons.
            # In the emergency branch that is zero: emergencies carry no weight.
            score=_score(shown),
            threshold=AMBER_THRESHOLD,
            fired_rules=[
                FiredRule(
                    rule_id=rule.id,
                    # Filled in with the signs this owner actually ticked, so the
                    # explanation quotes their answers instead of listing every
                    # sign the rule covers.
                    message=rule.message_for(intake),
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
            confidence=self._confidence(intake, level, shown),
            urgent_care_signs=_urgent_care_signs(shown, intake),
            urgent_care_note=None if _has_own_urgent_signs(shown) else GENERAL_EMERGENCY_NOTE,
            care_instructions=_unique_items(
                instruction for rule in shown for instruction in rule.care_instructions
            ),
            what_to_expect=_unique_items(
                note for rule in shown for note in rule.what_to_expect
            ),
            disclaimer=DISCLAIMER,
            rules_fully_verified=self.fully_verified,
        )

    def _confidence(
        self, intake: SymptomIntake, level: TriageLevel, shown: list[Rule]
    ) -> ConfidenceReport:
        return confidence_module.build(
            intake,
            level,
            fired_rule_count=len(shown),
            extrapolations=frozenset().union(*(rule.extrapolations for rule in shown))
            if shown
            else frozenset(),
            states_urgency=any(rule.states_urgency for rule in shown),
            describes_diagnosis=any(
                rule.diagnostic_evidence is DiagnosticEvidence.DESCRIBED for rule in shown
            ),
            rules_fully_verified=self.fully_verified,
            level_of=lambda candidate: self.decide(candidate)[0],
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
        "EVIDENCE CHAIN, RULE BY RULE",
        "Read each block downwards: what the rule asserts, what each source",
        "actually says, the step we take past it, and who has signed it off.",
        "",
    ]
    for rule in rules:
        lines.append(rule.provenance.describe())
        lines.append("")

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


#: Said out loud whenever the recommendation rests on a bar we set ourselves.
#: It belongs next to the action, not three sections below it: the owner reads
#: "what to do now" and stops.
_THRESHOLD_CAVEAT = (
    " Whether a problem at this severity needs an appointment rather than watching is our own "
    "judgement — no source we hold sets that bar, and it is on the reviewing veterinarian's list."
)


def _with_threshold_caveat(advice: str, shown: list[Rule]) -> str:
    """Say whose decision the recommendation is, where it is ours."""
    takes_threshold_step = any(
        ExtrapolationKind.THRESHOLD in rule.extrapolations for rule in shown
    )
    if not takes_threshold_step or _THRESHOLD_CAVEAT.strip() in advice:
        return advice
    # A rule that already owns the judgement in its own advice does not need it
    # said twice.
    if "our cautious default" in advice or "our own judgement" in advice:
        return advice
    return advice + _THRESHOLD_CAVEAT


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


def _has_own_urgent_signs(shown: list[Rule]) -> bool:
    return any(rule.urgent_care_signs for rule in shown)


def _general_emergency_signs(intake: SymptomIntake | None = None) -> list[UrgentSign]:
    """The safety net, each line carrying the page that states it.

    Filtered to the animal in front of the owner where a line's source only
    speaks for one species — a urethral blockage is Cornell's claim about cats,
    GDV is Cornell's about dogs. When we were never told which animal it is,
    every line is shown: the lines say whose emergency they are in their own
    words, and dropping one on a guess is the wrong way to be wrong here.
    """
    species = normalise_species(intake.species) if intake is not None else None
    return [
        UrgentSign(
            text=sign.text,
            sources=[SourceLink(name=source.name, url=source.url) for source in sign.sources],
        )
        for sign in GENERAL_EMERGENCY_SIGNS
        if sign.species is None or species is None or species in sign.species
    ]


def _urgent_care_signs(shown: list[Rule], intake: SymptomIntake) -> list[UrgentSign]:
    """The "come back sooner if…" list, or the general emergency list.

    A rule only carries its own list when a source states those signs as
    reasons to be seen faster — the eye and ear pathways do. The skin pathway
    does not, because no page we hold sets an urgency threshold for skin, and
    the invented one it used to carry was exactly the kind of plausible,
    unsourced advice this system exists to keep out.

    Dropping the section entirely would leave an owner with a graded result and
    no stated safety boundary at all, so the fallback is the general emergency
    list, which is sourced independently of whatever they came in about.
    """
    if not _has_own_urgent_signs(shown):
        return _general_emergency_signs(intake)
    # A rule's own list is carried by that rule's citations, so each line is
    # attributed to the pages behind the reason it came with.
    seen: dict[str, UrgentSign] = {}
    for rule in shown:
        links = [SourceLink(name=c.source, url=c.url) for c in rule.citations]
        for sign in rule.urgent_care_signs:
            seen.setdefault(sign, UrgentSign(text=sign, sources=links))
    return list(seen.values())


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

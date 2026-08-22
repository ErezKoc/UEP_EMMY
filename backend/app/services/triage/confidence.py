"""How far the engine's own answer can be relied on.

Reported as separate dimensions, because they are separate questions and they
routinely disagree. An owner describing an itchy, red patch matches our skin
rules exactly — and the pages behind those rules say nothing whatsoever about
how soon the animal should be seen. Rolling that into one "moderate confidence"
badge hides the only part they might act on.

Underneath the dimensions are two facts:

* which of the answers the owner gave actually decided the result, and
* which of the questions they skipped could have changed it.

The second one is computed rather than estimated, and the exact scope matters
because the owner is told about it. Every question in `PROBES` that this owner
left blank is filled in with each of its possible answers, ONE QUESTION AT A
TIME, and the assessment is re-run. What that does not do: explore combinations
of two skipped answers, or vary the individual "other symptoms" checkboxes,
which the form offers in full and does not consider skippable. So the claim the
report makes is the narrow one — each blank, tried on its own — and the wording
shown to the owner says so.

There is no percentage anywhere in this file. A number would imply we had
measured how often the engine is right, and nobody has: the rules are read from
published sources and no veterinarian has reviewed them yet.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from app.core.species import normalise_species
from app.models.animal import AgeCategory
from app.schemas.triage import (
    BodyArea,
    Concern,
    ConfidenceDimension,
    ConfidenceKind,
    ConfidenceLevel,
    ConfidenceReport,
    Duration,
    ExtrapolationKind,
    ItchLevel,
    RedFlag,
    SymptomIntake,
    TimeSinceEating,
    TriageLevel,
    Trend,
)

#: The signs the skin questions offer. Used to notice that an owner has said
#: "skin or coat" and then never described the skin, which is the single most
#: common reason a dermatological case cannot be matched to a rule.
_SKIN_SIGNS = (
    RedFlag.SKIN_ITCHING,
    RedFlag.SKIN_REDNESS,
    RedFlag.SKIN_HAIR_LOSS,
    RedFlag.SKIN_RASH_OR_BUMPS,
    RedFlag.SKIN_SCABS_OR_FLAKING,
    RedFlag.SKIN_SWELLING,
    RedFlag.SKIN_LUMP,
    RedFlag.SKIN_NAIL_OR_PAD_CHANGE,
    RedFlag.SKIN_OPEN_WOUND,
    RedFlag.SKIN_DISCHARGE_OR_PUS,
    RedFlag.SKIN_ODOR,
)

_EYE_SIGNS = (
    RedFlag.EYE_PAIN_OR_CLOSED,
    RedFlag.EYE_CLOUDY_OR_BLUE,
    RedFlag.UNEQUAL_PUPILS_OR_VISION_CHANGE,
    RedFlag.EYE_BULGING_OR_SEVERE_SWELLING,
    RedFlag.EYE_DISCHARGE_YELLOW_GREEN_OR_BLOODY,
)

_EAR_SIGNS = (
    RedFlag.EAR_HEAD_SHAKING_OR_SCRATCHING,
    RedFlag.EAR_ODOR,
    RedFlag.EAR_DISCHARGE,
    RedFlag.EAR_REDNESS,
    RedFlag.EAR_PAIN,
)


def _is_skin_context(intake: SymptomIntake) -> bool:
    return intake.concern is Concern.SKIN_OR_COAT or bool(
        set(intake.red_flags) & set(_SKIN_SIGNS)
    )


def _is_eye_context(intake: SymptomIntake) -> bool:
    return intake.concern is Concern.EYES or intake.body_area is BodyArea.EYE


def _is_ear_context(intake: SymptomIntake) -> bool:
    return intake.concern is Concern.EARS or intake.body_area is BodyArea.EAR


@dataclass(frozen=True)
class _Probe:
    """One question, and what the answers to it would have been.

    `label` is the question as the owner saw it, so the result can quote it back
    rather than naming a field.
    """

    label: str
    applies: Callable[[SymptomIntake], bool]
    variants: Callable[[SymptomIntake], Iterator[SymptomIntake]]
    #: Set when answering the question is the only way to reach a rule at all,
    #: which is worth saying more strongly than "this might change things".
    decisive: bool = field(default=False)


def _set(intake: SymptomIntake, **updates: object) -> SymptomIntake:
    return intake.model_copy(update=updates)


def _with_flag(intake: SymptomIntake, flag: RedFlag) -> SymptomIntake:
    return _set(intake, red_flags=[*intake.red_flags, flag])


def _unanswered(name: str) -> Callable[[SymptomIntake], bool]:
    return lambda intake: getattr(intake, name) is None


def _sign_group_unanswered(signs: tuple[RedFlag, ...], context: Callable[[SymptomIntake], bool]):
    def applies(intake: SymptomIntake) -> bool:
        return context(intake) and not set(intake.red_flags) & set(signs)

    return applies


PROBES: tuple[_Probe, ...] = (
    _Probe(
        label="what you can see on the skin",
        applies=_sign_group_unanswered(_SKIN_SIGNS, _is_skin_context),
        variants=lambda intake: (_with_flag(intake, flag) for flag in _SKIN_SIGNS),
        decisive=True,
    ),
    _Probe(
        label="how much the skin is bothering them",
        applies=lambda intake: intake.itch_level is None and _is_skin_context(intake),
        variants=lambda intake: (_set(intake, itch_level=value) for value in ItchLevel),
    ),
    _Probe(
        label="what you are noticing with the eye",
        applies=_sign_group_unanswered(_EYE_SIGNS, _is_eye_context),
        variants=lambda intake: (_with_flag(intake, flag) for flag in _EYE_SIGNS),
    ),
    _Probe(
        label="what you are noticing with the ear",
        applies=_sign_group_unanswered(_EAR_SIGNS, _is_ear_context),
        variants=lambda intake: (_with_flag(intake, flag) for flag in _EAR_SIGNS),
    ),
    _Probe(
        label="which animal this is",
        applies=lambda intake: normalise_species(intake.species) is None,
        variants=lambda intake: (_set(intake, species=name) for name in ("dog", "cat")),
    ),
    _Probe(
        label="how long this has been going on",
        applies=_unanswered("duration"),
        variants=lambda intake: (_set(intake, duration=value) for value in Duration),
    ),
    _Probe(
        label="whether it is getting better or worse",
        applies=_unanswered("trend"),
        variants=lambda intake: (_set(intake, trend=value) for value in Trend),
    ),
    _Probe(
        label="where on the body it is",
        applies=_unanswered("body_area"),
        variants=lambda intake: (_set(intake, body_area=value) for value in BodyArea),
    ),
    _Probe(
        label="how long since they last ate",
        applies=lambda intake: (
            intake.time_since_eating is None and RedFlag.NOT_EATING in intake.red_flags
        ),
        variants=lambda intake: (
            _set(intake, time_since_eating=value) for value in TimeSinceEating
        ),
    ),
    _Probe(
        label="whether they can put weight on the leg",
        applies=lambda intake: (
            intake.weight_bearing is None
            and (
                intake.concern is Concern.MOBILITY
                or intake.body_area is BodyArea.LEGS_OR_PAWS
            )
        ),
        variants=lambda intake: (_set(intake, weight_bearing=value) for value in (True, False)),
    ),
    _Probe(
        label="whether they have a long-term illness",
        applies=_unanswered("has_chronic_illness"),
        variants=lambda intake: (
            _set(intake, has_chronic_illness=value) for value in (True, False)
        ),
    ),
    _Probe(
        label="how old they are",
        applies=_unanswered("age_category"),
        variants=lambda intake: (
            _set(intake, age_category=value)
            for value in (AgeCategory.BABY, AgeCategory.ADULT, AgeCategory.SENIOR)
        ),
    ),
)


def open_questions(
    intake: SymptomIntake, level_of: Callable[[SymptomIntake], TriageLevel]
) -> list[_Probe]:
    """The unanswered questions whose answers would change this result."""
    current = level_of(intake)
    found = []
    for probe in PROBES:
        if not probe.applies(intake):
            continue
        if any(level_of(variant) is not current for variant in probe.variants(intake)):
            found.append(probe)
    return found


def build(
    intake: SymptomIntake,
    level: TriageLevel,
    *,
    fired_rule_count: int,
    extrapolations: frozenset[ExtrapolationKind],
    states_urgency: bool,
    describes_diagnosis: bool,
    rules_fully_verified: bool,
    level_of: Callable[[SymptomIntake], TriageLevel],
) -> ConfidenceReport:
    """State how far this particular answer can be relied on, and why."""
    questions = open_questions(intake, level_of)
    labels = [probe.label for probe in questions]
    matched = fired_rule_count > 0

    # ------------------------------------------------ did the answers match?
    #
    # Named "Rule match" and not "Match to your answers", and carrying its own
    # kind so it is never rated in the same words as the evidence below it.
    # "Match to your answers: Strong" sat above a recommendation whose evidence
    # was Partial and whose urgency evidence was nothing at all, and the first
    # word an owner reads should not be the most reassuring one on the panel
    # when it is only saying that a rule's conditions were met.
    if not matched:
        match = ConfidenceDimension(
            name="Rule match",
            kind=ConfidenceKind.MATCH,
            level=ConfidenceLevel.LOW,
            detail="Nothing in our sourced rule table matched what you described.",
        )
    elif not questions:
        match = ConfidenceDimension(
            name="Rule match",
            kind=ConfidenceKind.MATCH,
            level=ConfidenceLevel.HIGH,
            # Not "without ambiguity": where a rule reads the owner's words as its
            # source's clinical category, the ambiguity is real and is reported
            # under "what this rests on".
            #
            # The second sentence is the one that stops the first being read as
            # confidence in the advice. Matching is bookkeeping about our own
            # table; whether anything supports what we then told them to do is
            # the next three lines, and they can and do say something weaker.
            detail=(
                "Your answers met every condition this rule tests. That is about our rule table, "
                "not about how well the recommendation below is supported."
            ),
        )
    else:
        match = ConfidenceDimension(
            name="Rule match",
            kind=ConfidenceKind.MATCH,
            level=ConfidenceLevel.MODERATE if len(questions) <= 2 else ConfidenceLevel.LOW,
            detail=(
                f"Your answers matched our rules, but {len(questions)} question"
                f"{'s' if len(questions) > 1 else ''} you skipped would change the result."
            ),
        )

    # ------------------------- does an examination establish what this is?
    #
    # Split from the question below it, which is the one the owner acts on.
    # "An examination is how the cause of a skin problem is identified" is
    # stated outright by Merck. "Therefore this mild, localised patch should be
    # brought in rather than watched" is a threshold the same page never sets,
    # and reporting them as one number hides which of the two we are short of.
    if not matched:
        exam = ConfidenceDimension(
            name="Evidence that examination is part of identifying the cause",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.LOW,
            detail=(
                "No rule matched, so we are claiming neither that your pet needs examining nor "
                "that they do not."
            ),
        )
    elif not describes_diagnosis:
        # The pages behind an urgency rule are often about how fast to act and
        # nothing else. Saying they describe the diagnostic process, because a
        # different pathway's sources do, is the report inventing its own
        # evidence.
        exam = ConfidenceDimension(
            name="Evidence that examination is part of identifying the cause",
            kind=ConfidenceKind.EVIDENCE,
            # NOT_ASSESSED, not LOW: the detail below has always said the
            # question was out of scope for this rule, while the badge beside it
            # said "None" — the word this panel uses for "we looked and the
            # sources do not support it". On a red urinary result those are very
            # different statements and the owner only sees the badge.
            level=ConfidenceLevel.NOT_ASSESSED,
            # Says what WE have not recorded, not what the pages do not contain.
            # The old wording asserted the sources were silent on diagnosis; one
            # of them has a diagnostics section, and the rule simply does not
            # rest on it.
            detail=(
                "Not assessed for this rule. It rests on how urgently to act, so we have not "
                "recorded whether the pages behind it also describe how the cause is worked out."
            ),
        )
    elif ExtrapolationKind.RECOMMENDATION in extrapolations:
        exam = ConfidenceDimension(
            name="Evidence that examination is part of identifying the cause",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.MODERATE,
            detail=(
                "Published sources support examining a problem of this kind, but the "
                "recommendation goes further than they literally state."
            ),
        )
    else:
        exam = ConfidenceDimension(
            # "identifies the cause" overstated it: Merck says a definitive
            # diagnosis needs the history, the examination AND appropriate
            # tests. An examination on its own is part of that, not all of it.
            name="Evidence that examination is part of identifying the cause",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.HIGH,
            detail=(
                "The pages cited above state in their own words that working out the cause takes "
                "the history, a physical examination and, where needed, diagnostic tests."
            ),
        )

    # ------------------------ and should THIS presentation be brought in?
    if not matched:
        action = ConfidenceDimension(
            name="Evidence that this presentation should be examined",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.LOW,
            detail="No rule matched, so nothing here supports a recommendation either way.",
        )
    elif ExtrapolationKind.THRESHOLD in extrapolations:
        action = ConfidenceDimension(
            name="Evidence that this presentation should be examined",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.MODERATE,
            detail=(
                "Our sources explain how a problem like this is diagnosed, but none of them says "
                "that this combination and severity of signs should be brought in rather than "
                "watched. Where that bar sits is our judgement, and it is on the reviewing "
                "veterinarian's list."
            ),
        )
    else:
        action = ConfidenceDimension(
            name="Evidence that this presentation should be examined",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.HIGH,
            detail="A cited page recommends veterinary attention for what you described.",
        )

    # --------------------------------------------- does anything say how soon?
    if level is TriageLevel.RED:
        urgency = ConfidenceDimension(
            name="Evidence for how urgent this is",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.HIGH,
            # Not "call it an emergency": Missouri's list is introduced as
            # situations warranting more immediate veterinary attention, which
            # is strong urgency evidence and not that word.
            # Deliberately not quoting one publisher's phrasing at all of them:
            # Merck says "emergencies requiring immediate care", Missouri "more
            # immediate veterinary attention", Cornell "a true medical
            # emergency". The sources beside each reason carry their own words.
            detail=(
                "At least one cited page treats what you reported as needing veterinary attention "
                "straight away. Their own wording is in the sources beside each reason above."
            ),
        )
    elif states_urgency and ExtrapolationKind.TIMING in extrapolations:
        urgency = ConfidenceDimension(
            name="Evidence for how urgent this is",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.MODERATE,
            detail=(
                "A cited page does say this needs attention, but the specific window shown above "
                "is ours rather than theirs, and is flagged for veterinary review."
            ),
        )
    elif states_urgency:
        urgency = ConfidenceDimension(
            name="Evidence for how urgent this is",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.HIGH,
            detail="At least one page behind this answer states a timeframe of its own.",
        )
    else:
        urgency = ConfidenceDimension(
            name="Evidence for how urgent this is",
            kind=ConfidenceKind.EVIDENCE,
            level=ConfidenceLevel.LOW,
            # "not a sign that waiting is safe" leaned the other way while
            # claiming to lean neither way: it reads as a hint that waiting is
            # unsafe, which is a timing judgement, and the absence of timing
            # evidence is the entire content of this dimension.
            detail=(
                "None of the pages behind this answer says how soon your pet should be seen, so "
                "no timeframe is given. That is a gap in what our sources cover, and not a "
                "judgement either way about whether this can wait."
            ),
        )

    validation = ConfidenceDimension(
        name="Veterinary review",
        kind=ConfidenceKind.REVIEW,
        level=ConfidenceLevel.HIGH if rules_fully_verified else ConfidenceLevel.LOW,
        detail=(
            "A named veterinarian has checked the rules behind this answer."
            if rules_fully_verified
            else "These rules were read from published sources by the team. No veterinarian has "
            "signed them off yet."
        ),
    )

    based_on = []
    if fired_rule_count:
        based_on.append(
            f"{fired_rule_count} rule{'s' if fired_rule_count > 1 else ''} from our sourced table "
            "matched what you described."
        )
    else:
        based_on.append("No rule in our sourced table matched what you described.")

    if matched and not questions:
        based_on.append(
            "We re-ran the assessment once for every answer you could have given to a question "
            "you left blank, one question at a time. None of them changes this result."
        )
    if ExtrapolationKind.MAPPING in extrapolations:
        based_on.append(
            "Deciding that what you described belongs to the category our sources write about is "
            "our step, not theirs. It is flagged for veterinary review."
        )

    species = normalise_species(intake.species)
    if species is None:
        based_on.append(
            "You did not tell us which animal this is, so guidance that applies only to dogs or "
            "only to cats was left out."
        )
    elif species not in ("dog", "cat"):
        based_on.append(
            f"Our sources cover dogs and cats. Almost nothing in our evidence library speaks to "
            f"a {species}."
        )

    return ConfidenceReport(
        dimensions=[match, exam, action, urgency, validation],
        based_on=based_on,
        would_change_the_answer=labels,
    )

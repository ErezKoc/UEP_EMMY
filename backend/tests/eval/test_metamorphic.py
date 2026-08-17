"""Metamorphic relations — how the answer must move when the input moves.

These need no expected level at all. They assert relationships between two
answers, which makes them usable on the whole evaluation set including the
cases the evidence cannot label.
"""

from __future__ import annotations

import pytest

from app.models.animal import AgeCategory
from app.schemas.triage import Concern, Duration, RedFlag, SymptomIntake, TimeSinceEating, Trend
from app.services.triage import TriageEngine
from tests.eval.cases import CASES
from tests.eval.oracle import CAUTION_ORDER

engine = TriageEngine(require_verified=False)

#: Ordered least to most concerning, as the intake form presents them.
_LONGER = (Duration.TODAY, Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)
_HUNGRIER = (TimeSinceEating.UNDER_12H, TimeSinceEating.H12_TO_24H, TimeSinceEating.OVER_24H)


def _level(intake: SymptomIntake):
    return engine.assess(intake).level


def _relation(cases, field, ordering, label):
    regressions = []
    for case in cases:
        for lower, higher in zip(ordering, ordering[1:]):
            before = _level(case.intake.model_copy(update={field: lower}))
            after = _level(case.intake.model_copy(update={field: higher}))
            if CAUTION_ORDER[after] < CAUTION_ORDER[before]:
                regressions.append(
                    f"{case.id}: {field} {lower.value} -> {higher.value} dropped "
                    f"{before.value} -> {after.value}"
                )
    assert not regressions, f"{label}:\n  " + "\n  ".join(regressions[:15])


def test_a_longer_duration_never_lowers_urgency():
    _relation(CASES, "duration", _LONGER, "Reporting a longer duration made the answer calmer")


def test_a_longer_time_without_food_never_lowers_urgency():
    _relation(
        CASES, "time_since_eating", _HUNGRIER, "Reporting a longer fast made the answer calmer"
    )


def test_a_worsening_trend_is_never_calmer_than_an_improving_one():
    regressions = []
    for case in CASES:
        improving = _level(case.intake.model_copy(update={"trend": Trend.IMPROVING}))
        worsening = _level(case.intake.model_copy(update={"trend": Trend.WORSENING}))
        if CAUTION_ORDER[worsening] < CAUTION_ORDER[improving]:
            regressions.append(
                f"{case.id}: improving={improving.value} but worsening={worsening.value}"
            )
    assert not regressions, "A worsening trend calmed the answer:\n  " + "\n  ".join(regressions[:15])


@pytest.mark.parametrize("fragile_age", [AgeCategory.BABY, AgeCategory.SENIOR])
def test_a_fragile_age_is_never_calmer_than_an_adult(fragile_age):
    regressions = []
    for case in CASES:
        adult = _level(case.intake.model_copy(update={"age_category": AgeCategory.ADULT}))
        fragile = _level(case.intake.model_copy(update={"age_category": fragile_age}))
        if CAUTION_ORDER[fragile] < CAUTION_ORDER[adult]:
            regressions.append(
                f"{case.id}: adult={adult.value} but {fragile_age.value}={fragile.value}"
            )
    assert not regressions, (
        f"A {fragile_age.value} animal was treated more calmly than an adult:\n  "
        + "\n  ".join(regressions[:15])
    )


def test_declaring_a_chronic_illness_never_lowers_urgency():
    regressions = []
    for case in CASES:
        well = _level(case.intake.model_copy(update={"has_chronic_illness": False}))
        chronic = _level(case.intake.model_copy(update={"has_chronic_illness": True}))
        if CAUTION_ORDER[chronic] < CAUTION_ORDER[well]:
            regressions.append(f"{case.id}: healthy={well.value} but chronic={chronic.value}")
    assert not regressions, (
        "Declaring a chronic illness calmed the answer:\n  " + "\n  ".join(regressions[:15])
    )


def test_refusing_to_bear_weight_is_never_calmer_than_bearing_weight():
    regressions = []
    for case in CASES:
        bearing = _level(case.intake.model_copy(update={"weight_bearing": True}))
        not_bearing = _level(case.intake.model_copy(update={"weight_bearing": False}))
        if CAUTION_ORDER[not_bearing] < CAUTION_ORDER[bearing]:
            regressions.append(
                f"{case.id}: weight bearing={bearing.value} but refusing={not_bearing.value}"
            )
    assert not regressions, (
        "Refusing to use a limb calmed the answer:\n  " + "\n  ".join(regressions[:15])
    )


def test_naming_the_species_never_lowers_urgency():
    """Answering 'dog' or 'cat' must not be worse than leaving it blank.

    Both are species the evidence base covers, so telling us which one can only
    add applicable rules. Unsupported species are excluded here — that they
    silence the table is a separate, reported finding, not a metamorphic bug.
    """
    regressions = []
    for case in CASES:
        blank = _level(case.intake.model_copy(update={"species": None}))
        for species in ("dog", "cat"):
            named = _level(case.intake.model_copy(update={"species": species}))
            if CAUTION_ORDER[named] < CAUTION_ORDER[blank]:
                regressions.append(
                    f"{case.id}: species blank={blank.value} but {species}={named.value}"
                )
    assert not regressions, (
        "Naming a supported species calmed the answer:\n  " + "\n  ".join(regressions[:15])
    )


def test_selecting_a_matching_concern_never_lowers_urgency():
    """Picking the concern that matches the reported signs must not calm things.

    The eye and ear rules are gated on the selected concern, so this relation
    checks the gate only ever adds urgency, never removes it.
    """
    pairs = (
        (Concern.EYES, RedFlag.EYE_CLOUDY_OR_BLUE),
        (Concern.EARS, RedFlag.EAR_HEAD_TILT),
        (Concern.DIGESTION, RedFlag.VOMITING),
        (Concern.MOBILITY, RedFlag.LIMB_CANNOT_MOVE),
    )
    regressions = []
    for concern, flag in pairs:
        base = SymptomIntake(
            duration=Duration.DAYS_2_7, red_flags=[flag], species="dog",
            age_category=AgeCategory.ADULT,
        )
        generic = _level(base.model_copy(update={"concern": Concern.OTHER}))
        specific = _level(base.model_copy(update={"concern": concern}))
        if CAUTION_ORDER[specific] < CAUTION_ORDER[generic]:
            regressions.append(
                f"{flag.value}: concern=other -> {generic.value}, "
                f"concern={concern.value} -> {specific.value}"
            )
    assert not regressions, "Choosing the matching concern calmed the answer:\n  " + "\n  ".join(
        regressions
    )


def test_dog_and_cat_get_the_same_answer_for_species_general_evidence():
    """Where every applicable source covers both species, so must the answer."""
    from tests.eval.oracle import GENERAL_EMERGENCY_FLAGS

    asymmetric = []
    for flag in sorted(GENERAL_EMERGENCY_FLAGS, key=lambda f: f.value):
        base = SymptomIntake(concern=Concern.OTHER, red_flags=[flag], age_category=AgeCategory.ADULT)
        as_dog = _level(base.model_copy(update={"species": "dog"}))
        as_cat = _level(base.model_copy(update={"species": "cat"}))
        if as_dog is not as_cat:
            asymmetric.append(f"{flag.value}: dog={as_dog.value}, cat={as_cat.value}")
    assert not asymmetric, (
        "Signs their sources describe for both species were answered differently:\n  "
        + "\n  ".join(asymmetric)
    )

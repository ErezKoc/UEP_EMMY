"""Accuracy: does the engine agree with an expert on realistic cases?

Each vignette is a short case with an expected urgency assigned *before* the
engine was run. The metric that matters is **under-triage**: a case that needed
urgent care and was told to stay home. That number must be zero. Over-triage —
sending someone who did not strictly need to go — is the cost we deliberately
accept, and it is reported rather than hidden.

LABEL STATUS
------------
These expected levels were assigned from the same published sources the rules
cite. They are **not yet confirmed by a veterinarian**. When a reviewer goes
through them, record their name in `labelled_by` — and if they disagree with a
label, change the label, never the engine.

Growing this file is the cheapest way to strengthen the accuracy claim.
"""

from dataclasses import dataclass

import pytest

from app.models.animal import AgeCategory
from app.schemas.triage import (
    BodyArea,
    Concern,
    Duration,
    RedFlag,
    SymptomIntake,
    TimeSinceEating,
    TriageLevel,
    Trend,
)
from app.services.triage import TriageEngine

engine = TriageEngine(require_verified=False)

_SEVERITY_ORDER = {
    TriageLevel.GREEN: 0,
    # An abstention is not a point on the clinical scale. It is ranked above
    # green here only so these comparisons have a total order: refusing to
    # answer withholds the reassurance green gives, so it can never be an
    # under-triage relative to a green label.
    TriageLevel.UNASSESSED: 1,
    TriageLevel.AMBER: 2,
    TriageLevel.RED: 3,
}

_PENDING_REVIEW = "team, from the cited sources (pending veterinary review)"

#: Appended to the labels that used to read GREEN purely because no rule fired.
_UNCOVERED = (
    " The engine no longer answers an uncovered case with green: absence of a matching rule is not"
    " evidence that home monitoring is safe, so this now returns UNASSESSED. The label is updated"
    " to match that contract, not to make a failing test pass."
)


@dataclass(frozen=True)
class Vignette:
    id: str
    description: str
    intake: SymptomIntake
    expected: TriageLevel
    rationale: str
    labelled_by: str = _PENDING_REVIEW
    # Set when the engine deliberately disagrees with this label and a
    # veterinarian has to settle it. The label is NOT changed to match the
    # engine — that would erase the disagreement instead of recording it.
    awaiting_veterinary_adjudication: str = ""


VIGNETTES: tuple[Vignette, ...] = (
    # ---------------------------------------------------------------- red
    Vignette(
        id="dog_laboured_breathing",
        description="Adult Labrador breathing hard at rest.",
        intake=SymptomIntake(
            concern=Concern.BREATHING,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.TROUBLE_BREATHING],
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Merck lists trouble breathing as needing immediate care.",
    ),
    Vignette(
        id="pale_gums_after_fall",
        description="Cat with pale gums and lethargy after falling from a balcony.",
        intake=SymptomIntake(
            concern=Concern.OTHER,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.PALE_GUMS, RedFlag.EXTREME_LETHARGY],
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="ASPCA lists pale gums among emergency signs.",
    ),
    Vignette(
        id="male_cat_straining",
        description="Male cat visiting the litter tray repeatedly, producing nothing.",
        intake=SymptomIntake(
            concern=Concern.URINATION,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.UNABLE_TO_URINATE],
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="ACVS states urinary obstruction requires emergency treatment.",
    ),
    Vignette(
        id="dog_bloated_retching",
        description="Large dog with a swollen belly, retching without producing anything.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            body_area=BodyArea.BELLY,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.BLOATED_ABDOMEN_WITH_RETCHING],
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Cornell states GDV needs immediate intervention and is fatal without it.",
    ),
    Vignette(
        id="ate_chocolate",
        description="Dog ate a bar of chocolate an hour ago and currently seems fine.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.SUSPECTED_POISONING],
            species="dog",
            age_category=AgeCategory.YOUNG,
        ),
        expected=TriageLevel.RED,
        rationale="Merck lists poisoning as an emergency; looking well does not rule it out.",
    ),
    Vignette(
        id="bloody_vomit",
        description="Adult dog vomiting material that looks like coffee grounds.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.VOMITING, RedFlag.BLOOD_IN_VOMIT_OR_STOOL],
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Missouri lists blood or coffee-grounds vomit as warranting immediate attention.",
    ),
    Vignette(
        id="cat_off_food_two_days",
        description="Indoor cat has eaten nothing for two days.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.NOT_EATING],
            time_since_eating=TimeSinceEating.OVER_24H,
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Cornell: appetite loss can severely affect a mature cat in as little as 24 hours.",
    ),
    Vignette(
        id="kitten_off_food_overnight",
        description="Four-week-old kitten has refused food since last night.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.NOT_EATING],
            time_since_eating=TimeSinceEating.H12_TO_24H,
            species="cat",
            age_category=AgeCategory.BABY,
        ),
        expected=TriageLevel.RED,
        rationale="Cornell: for a kitten under six weeks, 12 hours without food can be lethal.",
    ),
    Vignette(
        id="senior_dog_vomiting_twice",
        description="Twelve-year-old dog with kidney disease vomited twice this morning.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.VOMITING],
            has_chronic_illness=True,
            species="dog",
            age_category=AgeCategory.SENIOR,
        ),
        expected=TriageLevel.RED,
        rationale="Missouri: chronically ill or elderly animals warrant attention after only a few episodes.",
    ),
    Vignette(
        id="puppy_diarrhoea",
        description="Ten-week-old puppy with diarrhoea since this morning, still playful.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.DIARRHOEA],
            species="dog",
            age_category=AgeCategory.BABY,
        ),
        expected=TriageLevel.RED,
        rationale="Missouri: very young animals warrant immediate attention even after a few episodes.",
    ),
    Vignette(
        id="cut_paw_bleeding",
        description="Dog cut a paw pad and it is still bleeding heavily.",
        intake=SymptomIntake(
            concern=Concern.OTHER,
            body_area=BodyArea.LEGS_OR_PAWS,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.UNCONTROLLED_BLEEDING],
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Merck and ASPCA both list severe bleeding as an emergency.",
    ),
    Vignette(
        id="scratched_eye",
        description="Cat came in with a watering, injured-looking eye after a fight.",
        intake=SymptomIntake(
            concern=Concern.EYES,
            body_area=BodyArea.EYE,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.EYE_INJURY],
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Merck lists eye injuries as needing immediate care.",
    ),
    Vignette(
        id="hit_by_car_looks_fine",
        description="Dog was clipped by a car, got up and walked away, seems normal.",
        intake=SymptomIntake(
            concern=Concern.OTHER,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.MAJOR_TRAUMA],
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="ASPCA: severe trauma from an accident or fall warrants emergency care.",
    ),
    Vignette(
        id="left_in_hot_car",
        description="Dog was shut in a hot car, now panting heavily and unsteady.",
        intake=SymptomIntake(
            concern=Concern.BEHAVIOUR,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.OVERHEATING],
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Cornell: heatstroke is life-threatening; Merck calls it an emergency.",
    ),
    Vignette(
        id="black_tarry_stool",
        description="Adult cat passing black, tarry stool.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.DIARRHOEA, RedFlag.BLACK_TARRY_STOOL],
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Cornell lists black or tarry stool (melena) as needing immediate attention.",
    ),
    Vignette(
        id="cat_ear_problem_with_balance_changes",
        description="Cat with an ear problem now has a head tilt and is stumbling.",
        intake=SymptomIntake(
            concern=Concern.EARS,
            body_area=BodyArea.EAR,
            duration=Duration.DAYS_2_7,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.EAR_HEAD_TILT, RedFlag.EAR_BALANCE_PROBLEMS],
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Merck lists head tilt and vestibular ataxia as signs of inner ear disease.",
        awaiting_veterinary_adjudication=(
            "The label is left at RED on purpose. Re-reading Merck's otitis media/interna page for"
            " the safety audit found that it describes these signs and says treatment works best"
            " when started early, but never calls them an emergency and gives no timing — so the"
            " engine now grades them AMBER rather than asserting a same-day urgency no source"
            " states. Whether vestibular signs warrant same-day care in practice is a clinical"
            " judgement this team cannot make. If the answer is yes, name a source and the rule"
            " goes back to red."
        ),
    ),
    # -------------------------------------------------------------- amber
    Vignette(
        id="squinting_no_injury",
        description="Cat squinting one eye since yesterday, no known injury.",
        intake=SymptomIntake(
            concern=Concern.EYES,
            body_area=BodyArea.EYE,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.AMBER,
        rationale="General pet and small-animal eye guidance supports examination within 24 hours.",
    ),
    Vignette(
        id="dog_red_watery_eye",
        description="Dog with a newly red, watery and irritated left eye.",
        intake=SymptomIntake(
            concern=Concern.EYES,
            body_area=BodyArea.EYE,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.AMBER,
        rationale="New eye redness and watering should be examined within about 24 hours.",
    ),
    Vignette(
        id="dog_cloudy_painful_eye",
        description="Dog squinting with a cloudy, painful-looking eye.",
        intake=SymptomIntake(
            concern=Concern.EYES,
            body_area=BodyArea.EYE,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.EYE_PAIN_OR_CLOSED, RedFlag.EYE_CLOUDY_OR_BLUE],
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale="Pain, clouding and worsening require same-day urgent eye assessment.",
    ),
    Vignette(
        id="dog_worsening_ear_problem_for_days",
        description="Dog's ear problem has lasted several days and is getting worse.",
        intake=SymptomIntake(
            concern=Concern.EARS,
            body_area=BodyArea.EAR,
            duration=Duration.DAYS_2_7,
            trend=Trend.WORSENING,
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.AMBER,
        rationale="Persistence and worsening trigger a cautious examination within 24-48 hours.",
    ),
    Vignette(
        id="cat_ear_odor_and_discharge",
        description="Cat developed foul-smelling ear discharge today.",
        intake=SymptomIntake(
            concern=Concern.EARS,
            body_area=BodyArea.EAR,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.EAR_ODOR, RedFlag.EAR_DISCHARGE],
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.AMBER,
        rationale="Merck lists odor and discharge among signs that require cause-directed assessment.",
    ),
    Vignette(
        id="lame_for_three_days",
        description="Dog limping and not loading one back leg for three days, but able to move it.",
        intake=SymptomIntake(
            concern=Concern.MOBILITY,
            body_area=BodyArea.LEGS_OR_PAWS,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            weight_bearing=False,
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.AMBER,
        rationale="VCA: lameness persisting more than 24 hours warrants veterinary care.",
    ),
    Vignette(
        id="limping_since_this_afternoon",
        description="Dog started limping an hour ago after running, still bright and eating.",
        intake=SymptomIntake(
            concern=Concern.MOBILITY,
            body_area=BodyArea.LEGS_OR_PAWS,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            weight_bearing=True,
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.UNASSESSED,
        rationale=(
            "VCA's threshold is 24 hours, so fresh mild lameness is below anything it asks for."
            " Reading that as permission to monitor at home is the complement of a threshold, not"
            " something the page says — an inference the team may not make on its own. The engine"
            " therefore abstains rather than reassuring. Adding an evidence-backed low-risk"
            " pathway here is on the veterinary-adjudication list."
        ),
    ),
    Vignette(
        id="drinking_much_more",
        description="Senior cat emptying the water bowl daily for a few weeks, otherwise well.",
        intake=SymptomIntake(
            concern=Concern.BEHAVIOUR,
            duration=Duration.WEEKS_1_4,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.DRINKING_MUCH_MORE],
            species="cat",
            age_category=AgeCategory.SENIOR,
        ),
        expected=TriageLevel.AMBER,
        rationale="VCA describes increased thirst as warranting investigation, not emergency care.",
    ),
    Vignette(
        id="lethargic_adult_dog",
        description="Adult dog unusually flat and reluctant to move today, no other signs.",
        intake=SymptomIntake(
            concern=Concern.BEHAVIOUR,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.EXTREME_LETHARGY],
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.AMBER,
        rationale="Missouri lists marked lethargy as warranting attention, framed alongside vomiting.",
    ),
    # -------------------------------------------------------------- green
    Vignette(
        id="healing_scab",
        description="Small scab on an adult dog's back, improving, not being licked.",
        intake=SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            body_area=BodyArea.BACK,
            duration=Duration.DAYS_2_7,
            trend=Trend.IMPROVING,
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.UNASSESSED,
        rationale=(
            "No sourced rule fires; nothing in our sources escalates this — and nothing in them"
            " supports reassurance either." + _UNCOVERED
        ),
    ),
    Vignette(
        id="adult_cat_skipped_breakfast",
        description="Adult cat skipped breakfast but ate last night and seems normal.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.NOT_EATING],
            time_since_eating=TimeSinceEating.UNDER_12H,
            species="cat",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.UNASSESSED,
        rationale=(
            "Below Cornell's 24-hour threshold for a mature cat — but the page states no level for"
            " a shorter fast, so 'below the threshold' is not the same as 'safe to watch'. Reading"
            " it that way was an inference. The engine abstains, and what a cat that has skipped"
            " one meal should be told is on the veterinary-adjudication list."
        ),
    ),
    Vignette(
        id="adult_dog_diarrhoea_and_off_food",
        description="Adult dog with diarrhoea since yesterday and refusing food.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.DIARRHOEA, RedFlag.NOT_EATING],
            time_since_eating=TimeSinceEating.H12_TO_24H,
            has_chronic_illness=False,
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.RED,
        rationale=(
            "Cornell lists a dog stopping eating as a red flag when it has diarrhoea. This case"
            " previously returned green — the second round of research closed the gap."
        ),
    ),
    Vignette(
        id="adult_dog_off_food_only",
        description="Adult dog skipped meals since yesterday, otherwise bright.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.NOT_EATING],
            time_since_eating=TimeSinceEating.H12_TO_24H,
            has_chronic_illness=False,
            species="dog",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.AMBER,
        rationale="VCA: appetite change in a dog warrants investigation; no hour threshold given.",
    ),
    Vignette(
        id="rabbit_off_food_uncovered",
        description="Rabbit has not touched its food since yesterday.",
        intake=SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.NOT_EATING],
            time_since_eating=TimeSinceEating.H12_TO_24H,
            species="rabbit",
            age_category=AgeCategory.ADULT,
        ),
        expected=TriageLevel.UNASSESSED,
        rationale=(
            "Known coverage gap: our anorexia sources cover cats and dogs only. The engine must say it"
            " cannot assess this rather than imply reassurance." + _UNCOVERED
        ),
    ),
    Vignette(
        id="breed_curiosity",
        description="Owner just wants to know what breed their rescue dog might be.",
        intake=SymptomIntake(concern=Concern.BREED_ONLY, species="dog"),
        expected=TriageLevel.GREEN,
        rationale="No health question was asked.",
    ),
)


@pytest.mark.parametrize("vignette", VIGNETTES, ids=lambda v: v.id)
def test_engine_matches_expected_level(vignette: Vignette):
    result = engine.assess(vignette.intake)
    if vignette.awaiting_veterinary_adjudication:
        pytest.xfail(vignette.awaiting_veterinary_adjudication)
    assert result.level is vignette.expected, (
        f"{vignette.description}\nexpected {vignette.expected.value}, got {result.level.value} "
        f"(score {result.score}); fired: {[r.rule_id for r in result.fired_rules]}\n"
        f"label rationale: {vignette.rationale}"
    )


def test_no_under_triage():
    """The metric that matters: nobody who needed urgent care was told to stay home.

    Cases whose disagreement with the engine is a clinical judgement awaiting a
    veterinarian are listed separately by `test_cases_awaiting_adjudication_are_visible`
    rather than counted here, so a deferred question cannot masquerade as a
    software defect — or be quietly forgotten.
    """
    under = [
        vignette.id
        for vignette in VIGNETTES
        if not vignette.awaiting_veterinary_adjudication
        and _SEVERITY_ORDER[engine.assess(vignette.intake).level]
        < _SEVERITY_ORDER[vignette.expected]
    ]
    assert not under, f"Under-triaged cases (dangerous): {under}"


def test_cases_awaiting_adjudication_are_visible(capsys):
    """Deferred clinical questions must stay on the record, not disappear."""
    deferred = [v for v in VIGNETTES if v.awaiting_veterinary_adjudication]
    with capsys.disabled():
        for vignette in deferred:
            got = engine.assess(vignette.intake).level.value
            print(
                f"\nAWAITING VETERINARY ADJUDICATION — {vignette.id}: "
                f"label {vignette.expected.value}, engine {got}"
            )
    for vignette in deferred:
        assert vignette.rationale, f"{vignette.id} defers a decision without saying why."


def test_every_result_cites_its_reasons():
    """A verdict the owner cannot interrogate is not acceptable in this product.

    `UNASSESSED` is exempt, and must be: it is the one answer whose whole
    content is that we have no applicable rule to cite. `GREEN` is exempt for
    the breed-only case, where no health question was asked.
    """
    for vignette in VIGNETTES:
        result = engine.assess(vignette.intake)
        assert result.disclaimer
        if result.level in (TriageLevel.RED, TriageLevel.AMBER):
            assert result.fired_rules, f"{vignette.id} gave a verdict with no stated reason."
            for fired in result.fired_rules:
                assert fired.message and fired.sources
        if result.level is TriageLevel.UNASSESSED:
            assert not result.fired_rules, (
                f"{vignette.id} abstained while listing reasons — one of the two is wrong."
            )


def test_uncovered_cases_are_declared_not_reassured():
    """Reporting symptoms no rule covers must never read as 'your pet is fine'.

    Our sources have gaps (anorexia guidance covers cats and dogs, not rabbits).
    Silence dressed up as a green light would be the most dangerous output the
    system could produce.
    """
    uncovered = SymptomIntake(
        concern=Concern.DIGESTION,
        duration=Duration.TODAY,
        red_flags=[RedFlag.NOT_EATING],
        time_since_eating=TimeSinceEating.H12_TO_24H,
        species="rabbit",
        age_category=AgeCategory.ADULT,
    )
    result = engine.assess(uncovered)
    assert result.fired_rules == []
    assert "can't assess" in result.headline.lower()
    assert "not the same as saying your pet is fine" in result.advice


def test_dog_eye_result_is_24_hour_species_appropriate_guidance():
    result = engine.assess(
        SymptomIntake(
            concern=Concern.EYES,
            body_area=BodyArea.EYE,
            duration=Duration.TODAY,
            trend=Trend.UNCHANGED,
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.AMBER
    assert "within 24 hours" in result.headline.lower()
    assert "today" in result.advice.lower()
    assert result.urgent_care_signs
    assert any("steroid" in item.lower() for item in result.care_instructions)
    assert all("feline" not in source.lower() for rule in result.fired_rules for source in rule.sources)
    assert all(link.url.startswith("https://") for rule in result.fired_rules for link in rule.source_links)


def test_eye_warning_signs_escalate_to_same_day_urgent_care():
    result = engine.assess(
        SymptomIntake(
            concern=Concern.EYES,
            body_area=BodyArea.EYE,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.UNEQUAL_PUPILS_OR_VISION_CHANGE],
            species="cat",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.RED
    assert "same-day" in result.headline.lower()
    assert "emergency service" in result.advice.lower()


def test_worsening_multiday_ear_problem_is_not_reassured():
    result = engine.assess(
        SymptomIntake(
            concern=Concern.EARS,
            body_area=BodyArea.EAR,
            duration=Duration.DAYS_2_7,
            trend=Trend.WORSENING,
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.AMBER
    assert "24-48 hours" in result.headline.lower()
    assert "contact your veterinary clinic today" in result.advice.lower()
    assert "cautious recommendation" in result.advice.lower()
    assert any("otoscope" in rule.message.lower() for rule in result.fired_rules)
    assert any("microscope" in rule.message.lower() for rule in result.fired_rules)
    assert any("cotton" in item.lower() for item in result.care_instructions)
    assert any("eardrum" in item.lower() for item in result.care_instructions)
    assert result.urgent_care_signs


def test_ear_neurological_signs_are_graded_and_reach_the_rules_ungated():
    """Head tilt and stumbling must be caught however the owner filed them.

    Rewritten from `test_ear_neurological_signs_escalate_to_same_day_urgent_care`.
    The old test asserted a same-day RED verdict, which the safety audit traced
    back to no source at all: Merck's otitis media/interna page describes these
    signs and recommends early treatment, but never calls them an emergency and
    states no timing. Asserting the urgency here was what kept the undeclared
    extrapolation alive, so the assertion now matches the evidence — graded, not
    red — and the RED question is recorded for veterinary adjudication on the
    `cat_ear_problem_with_balance_changes` vignette.

    The property this test now protects is the one the audit found broken: the
    signs are evaluated on their own, so choosing the "wrong" concern no longer
    discards them.
    """
    signs = [RedFlag.EAR_HEAD_TILT, RedFlag.EAR_BALANCE_PROBLEMS]

    in_context = engine.assess(
        SymptomIntake(
            concern=Concern.EARS,
            body_area=BodyArea.EAR,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=signs,
            species="cat",
            age_category=AgeCategory.ADULT,
        )
    )
    # The same signs, filed by an owner who did not think of them as an ear
    # problem. This used to return green with no rules at all.
    out_of_context = engine.assess(
        SymptomIntake(
            concern=Concern.BEHAVIOUR,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=signs,
            species="cat",
            age_category=AgeCategory.ADULT,
        )
    )

    for result in (in_context, out_of_context):
        assert result.level is TriageLevel.AMBER
        assert "ear_neurological_signs" in {rule.rule_id for rule in result.fired_rules}
        assert result.urgent_care_signs
        assert "same-day" not in result.headline.lower(), (
            "No cited source establishes same-day urgency for vestibular signs."
        )


def test_breed_only_is_not_treated_as_an_uncovered_case():
    """Someone who asked no health question should not get a warning."""
    result = engine.assess(SymptomIntake(concern=Concern.BREED_ONLY, species="dog"))
    assert "no health concern" in result.headline.lower()


def test_emergency_signs_cannot_be_outweighed():
    """A red flag stays red no matter how reassuring everything else looks."""
    reassuring = SymptomIntake(
        concern=Concern.SKIN_OR_COAT,
        duration=Duration.TODAY,
        trend=Trend.IMPROVING,
        red_flags=[RedFlag.TROUBLE_BREATHING],
        species="dog",
        age_category=AgeCategory.ADULT,
    )
    assert engine.assess(reassuring).level is TriageLevel.RED


def test_unknown_species_still_gets_general_emergency_rules():
    """Not knowing dog-vs-cat must never silence species-general guidance.

    Reported case: suspected poisoning, blood in the vomit or stool, vomiting,
    not eating for over a day, extreme lethargy and worsening — with the owner
    answering "not sure" to species. Every rule was gated on a known species, so
    the whole table went quiet and this came back as "we can't assess this one".
    An owner describing a poisoning was told nothing.
    """
    unknown_species = SymptomIntake(
        concern=Concern.DIGESTION,
        body_area=BodyArea.BELLY,
        trend=Trend.WORSENING,
        red_flags=[
            RedFlag.SUSPECTED_POISONING,
            RedFlag.BLOOD_IN_VOMIT_OR_STOOL,
            RedFlag.VOMITING,
            RedFlag.NOT_EATING,
            RedFlag.EXTREME_LETHARGY,
        ],
        time_since_eating=TimeSinceEating.OVER_24H,
        has_chronic_illness=True,
        species=None,
    )
    result = engine.assess(unknown_species)

    assert result.level is TriageLevel.RED
    fired = {rule.rule_id for rule in result.fired_rules}
    assert "suspected_poisoning" in fired
    assert "blood_in_vomit_or_stool" in fired
    # A poisoning answer is only actionable if it says where to call.
    assert any("426-4435" in instruction for instruction in result.care_instructions)


def test_species_specific_rules_stay_out_when_species_is_unknown():
    """The cat-only anorexia rule must not be applied to an unidentified animal."""
    not_eating = dict(
        concern=Concern.DIGESTION,
        duration=Duration.DAYS_2_7,
        red_flags=[RedFlag.NOT_EATING],
        time_since_eating=TimeSinceEating.OVER_24H,
    )
    as_cat = {rule.rule_id for rule in engine.assess(SymptomIntake(species="cat", **not_eating)).fired_rules}
    unknown = {rule.rule_id for rule in engine.assess(SymptomIntake(species=None, **not_eating)).fired_rules}

    assert "cat_not_eating_24h" in as_cat
    assert "cat_not_eating_24h" not in unknown


def test_triage_summary(capsys):
    """Prints agreement and over-triage counts — run with -s to see them."""
    over = 0
    agreed = 0
    deferred = 0
    for vignette in VIGNETTES:
        if vignette.awaiting_veterinary_adjudication:
            deferred += 1
            continue
        got = engine.assess(vignette.intake).level
        if got is vignette.expected:
            agreed += 1
        elif _SEVERITY_ORDER[got] > _SEVERITY_ORDER[vignette.expected]:
            over += 1
    print(
        f"\nvignettes: {len(VIGNETTES)} | agreement: {agreed} | over-triage: {over} "
        f"| awaiting veterinary adjudication: {deferred}"
    )
    assert agreed + over + deferred == len(VIGNETTES), "Anything left over is under-triage."

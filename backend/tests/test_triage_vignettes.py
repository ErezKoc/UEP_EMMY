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
    ConfidenceKind,
    ConfidenceLevel,
    Duration,
    ItchLevel,
    RedFlag,
    SkinSpread,
    SymptomIntake,
    TimeSinceEating,
    TriageLevel,
    Trend,
)
from app.services.triage import TriageEngine

engine = TriageEngine(require_verified=False)


def dimension(result, name: str):
    """One named certainty dimension out of a result's confidence report."""
    assert result.confidence is not None, "No confidence report on this result."
    for entry in result.confidence.dimensions:
        if entry.name == name:
            return entry
    raise AssertionError(
        f"No dimension named {name!r}; got {[d.name for d in result.confidence.dimensions]}"
    )

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
        expected=TriageLevel.AMBER,
        rationale=(
            "Below Cornell's 24-hour threshold for a mature cat, and the page states no level for"
            " a shorter fast — so 'below the threshold' is still not the same as 'safe to watch',"
            " and this case is not green. What changed on 2026-08-22 is that it is no longer"
            " unassessed either: the same page says a cat that is not eating deserves a full"
            " veterinary workup, without conditioning that on a duration, so `cat_not_eating`"
            " answers amber. The remaining question for a veterinarian is not whether this cat"
            " needs a vet but how fast, since Cornell's own word is 'immediately'."
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
    # The abstention must name itself as our gap, and must not be readable as
    # "nothing serious" — the sentence that carries that is the one under test.
    assert "not a sign that the problem is minor" in result.advice
    assert "safe to ignore" in result.advice
    assert "contact a veterinarian" in result.advice.lower()
    # Updated when the species branch was added. This case is a RABBIT, and the
    # advice used to open "your answers do not match guidance this checker can
    # assess confidently" — which blames the answers. The owner answered fine;
    # every species-scoped rule we hold is about dogs and cats, and no wording
    # about their answers can tell them that. The assertion now pins the reason
    # rather than the old phrasing of it.
    assert "covers dogs and cats" in result.advice
    assert "rabbit" in result.advice.lower()


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


def test_a_described_skin_problem_is_assessed_rather_than_abstained_on():
    """The reported case: dog, skin or coat, legs or paws, 2-7 days, unchanged.

    That combination used to return "we can't assess this one", because the
    only things it told the engine were a location, a duration and a trajectory
    — never what was actually on the skin. Merck's dermatology framework defines
    a skin case by its lesions, so the form now asks, and the rules read it.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            body_area=BodyArea.LEGS_OR_PAWS,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.SKIN_ITCHING, RedFlag.SKIN_REDNESS],
            itch_level=ItchLevel.FREQUENT,
            skin_spread=SkinSpread.SEVERAL_AREAS,
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.AMBER
    assert "skin_lesion_needs_examination" in {rule.rule_id for rule in result.fired_rules}
    assert result.urgent_care_signs
    assert result.what_to_expect

    # The explanation must quote what this owner reported. It used to list every
    # presentation the rule covers, so someone reporting an itchy red patch was
    # also told about hair loss, crusting, nodules and lumps.
    explanation = next(
        rule.message for rule in result.fired_rules
        if rule.rule_id == "skin_lesion_needs_examination"
    )
    assert "itching, licking or chewing and redness" in explanation
    for unreported in ("hair loss", "crusting", "nodule", "lump"):
        assert unreported not in explanation.lower(), (
            f"The explanation mentions {unreported!r}, which this owner did not report."
        )


def test_no_skin_answer_states_a_timeframe():
    """Merck's dermatology pages give no timing, so neither may we.

    Every other pathway in the table that recommends a visit has a source that
    at least says "seek veterinary care". The skin pages say what a diagnosis
    requires and nothing about when, so a skin-only result must recommend an
    examination without attaching hours or days to it.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            red_flags=[RedFlag.SKIN_HAIR_LOSS],
            species="cat",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.AMBER
    text = f"{result.headline} {result.advice}".lower()
    for timing in ("24 hours", "24-48", "same-day", "today", "next few days", "immediately"):
        assert timing not in text, f"A skin result claimed a timeframe: {timing!r}"


def test_skin_infection_advice_states_the_source_rather_than_a_derived_warning():
    """The bullet has to be the page's claim, not a prudent-sounding inference.

    This rule used to tell owners "do not use leftover skin medicine". Nothing
    we hold says that. What Merck does say is that treatment should be based on
    culture and susceptibility testing, so that is what the owner is told, and
    the explicit warning is on the reviewer's list to sign off in their name.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            red_flags=[RedFlag.SKIN_DISCHARGE_OR_PUS, RedFlag.SKIN_ODOR],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert "skin_infection_or_wound_signs" in {rule.rule_id for rule in result.fired_rules}
    everything = " ".join([*result.care_instructions, *result.what_to_expect]).lower()
    assert "culture and susceptibility testing" in everything
    assert "do not use leftover" not in everything


def test_a_skin_problem_someone_else_caught_is_answered_with_the_isolation_advice():
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            red_flags=[RedFlag.SKIN_SCABS_OR_FLAKING, RedFlag.SKIN_CONTAGION],
            species="cat",
            age_category=AgeCategory.YOUNG,
        )
    )

    assert "skin_problem_affecting_another_animal_or_person" in {
        rule.rule_id for rule in result.fired_rules
    }
    instructions = " ".join(result.care_instructions).lower()
    assert "away from other pets" in instructions
    # A hand-washing line was removed: sensible, but no page we hold recommends
    # it, and this rule exists to keep unsourced advice out.
    assert "wash your hands" not in instructions


def test_an_undescribed_skin_problem_abstains_and_names_the_question_that_would_help():
    """The abstention has to be useful, not just honest.

    Same case as above with the skin never described. The engine still refuses
    to place it on the scale — but it can say exactly which unanswered question
    would let it, because it re-runs the assessment with each possible answer
    filled in.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            body_area=BodyArea.LEGS_OR_PAWS,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.UNASSESSED
    assert result.fired_rules == []
    # The sourced emergency list is independent of the gap and still applies.
    assert result.urgent_care_signs
    assert result.confidence is not None
    assert dimension(result, "Rule match").level is ConfidenceLevel.LOW
    assert "what you can see on the skin" in result.confidence.would_change_the_answer


def test_confidence_is_high_for_an_emergency_and_admits_nothing_would_lower_it():
    result = engine.assess(
        SymptomIntake(
            concern=Concern.BREATHING,
            red_flags=[RedFlag.TROUBLE_BREATHING],
            species="dog",
        )
    )

    assert result.level is TriageLevel.RED
    assert dimension(result, "Evidence for how urgent this is").level is ConfidenceLevel.HIGH
    assert result.confidence.would_change_the_answer == []


def test_confidence_reports_the_unknown_species_as_a_limit_on_the_answer():
    result = engine.assess(
        SymptomIntake(
            concern=Concern.DIGESTION,
            red_flags=[RedFlag.NOT_EATING],
            duration=Duration.DAYS_2_7,
            species=None,
        )
    )

    assert result.confidence is not None
    based_on = " ".join(result.confidence.based_on).lower()
    assert "did not tell us which animal" in based_on
    assert "which animal this is" in result.confidence.would_change_the_answer


def test_a_skin_answer_reports_its_urgency_evidence_as_absent():
    """The dimension an owner might act on must not be hidden in an average.

    A skin case can match our rules perfectly and still rest on no urgency
    evidence at all, because none of the dermatology pages says how soon. Those
    are different questions and they are reported separately.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            body_area=BodyArea.BACK,
            duration=Duration.WEEKS_1_4,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.SKIN_HAIR_LOSS],
            itch_level=ItchLevel.OCCASIONAL,
            skin_spread=SkinSpread.ONE_AREA,
            has_chronic_illness=False,
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert dimension(result, "Rule match").level is ConfidenceLevel.HIGH

    # Two different questions, and the answers differ. Merck states outright how
    # the cause of a skin disease is identified — that is strong. It never says
    # that a mild, localised patch crosses the bar for an appointment rather
    # than being watched, and that is the half the owner acts on.
    assert dimension(result, "Evidence that examination is part of identifying the cause").level is (
        ConfidenceLevel.HIGH
    )
    action = dimension(result, "Evidence that this presentation should be examined")
    assert action.level is ConfidenceLevel.MODERATE
    assert "rather than watched" in action.detail
    assert any("our step, not theirs" in line for line in result.confidence.based_on)
    urgency = dimension(result, "Evidence for how urgent this is")
    assert urgency.level is ConfidenceLevel.LOW
    assert "how soon" in urgency.detail
    assert dimension(result, "Veterinary review").level is ConfidenceLevel.LOW


def test_the_rule_match_line_is_not_rated_in_the_same_words_as_the_evidence():
    """The panel's most reassuring word must not be its least meaningful one.

    "Match to your answers: Strong" sat at the top of the certainty panel on
    exactly this case — above a recommendation whose supporting evidence was
    Partial and whose urgency evidence was nothing at all. Both were rendered
    from one vocabulary, so the first word an owner read was the strongest one
    on the card, attached to the only line that says nothing about whether the
    advice is any good. The kinds keep them apart, in the payload and in the
    words the card picks from it.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            body_area=BodyArea.LEGS_OR_PAWS,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.SKIN_ITCHING, RedFlag.SKIN_REDNESS, RedFlag.SKIN_HAIR_LOSS],
            itch_level=ItchLevel.OCCASIONAL,
            skin_spread=SkinSpread.ONE_AREA,
            has_chronic_illness=False,
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    match = dimension(result, "Rule match")
    assert match.kind is ConfidenceKind.MATCH
    assert match.level is ConfidenceLevel.HIGH
    # And it says so itself, for anyone reading the payload rather than the card.
    assert "not about how well the recommendation" in match.detail

    action = dimension(result, "Evidence that this presentation should be examined")
    assert action.kind is ConfidenceKind.EVIDENCE
    assert action.level is ConfidenceLevel.MODERATE
    assert dimension(result, "Veterinary review").kind is ConfidenceKind.REVIEW


def test_a_mild_skin_case_says_no_emergency_sign_was_reported_before_anything_else():
    """The one thing they want settled first, said first.

    An owner has just been asked about seizures, collapse and pale gums. That
    the answer to all of them was "no" was previously inferable only from the
    card's colour and from the absence of alarm in three sections of evidence
    reporting, while the eleven-item emergency list sat below the result either
    way.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            body_area=BodyArea.LEGS_OR_PAWS,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            red_flags=[RedFlag.SKIN_ITCHING, RedFlag.SKIN_REDNESS],
            itch_level=ItchLevel.OCCASIONAL,
            species="dog",
            # The owner answered the emergency step. Without this the line is
            # withheld, because an empty flag list is not an answer.
            emergency_screen_answered=True,
        )
    )

    assert result.level is TriageLevel.AMBER
    assert result.screening_note is not None
    assert "did not select any of the emergency warning signs" in result.screening_note.lower()
    # And it says so without claiming the checklist settled the question.
    assert "cannot rule out every emergency" in result.screening_note.lower()
    # A restatement of their answers and of what our screening did with them —
    # never the clinical claim that emergencies have been excluded, which a
    # finite checklist coming back negative does not establish.
    assert "is not an emergency" not in result.screening_note
    assert "non-emergency" not in result.screening_note


def test_an_emergency_result_carries_no_reassuring_screening_line():
    result = engine.assess(
        SymptomIntake(
            concern=Concern.BREATHING,
            red_flags=[RedFlag.TROUBLE_BREATHING],
            species="dog",
        )
    )

    assert result.level is TriageLevel.RED
    assert result.screening_note is None


def test_an_unassessed_result_does_not_call_itself_a_non_emergency():
    """It screened the emergency signs and nothing else. Both halves matter.

    Saying "assessed as a non-emergency" here would hand back, in the screening
    line, the reassurance the whole branch exists to withhold.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            body_area=BodyArea.LEGS_OR_PAWS,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            species="dog",
            emergency_screen_answered=True,
        )
    )

    assert result.level is TriageLevel.UNASSESSED
    assert result.screening_note is not None
    assert "did not select any of the emergency warning signs" in result.screening_note.lower()
    assert "non-emergency" not in result.screening_note


def test_skin_rules_carry_no_urgent_care_list_of_their_own():
    """Diagnostic significance is not urgency evidence.

    The skin rules used to carry a "when to get urgent help" list — oozing,
    strong odour, spreading quickly, becoming lethargic. Every line was
    plausible and none was sourced: the pages establish that those signs matter
    when working out a cause, not that they mean the animal should be seen
    faster. The list is gone, and results fall back to the general emergency
    signs, which are sourced independently of the skin problem.
    """
    from app.services.triage.rules import ALL_RULES, GENERAL_EMERGENCY_SIGNS

    for rule in ALL_RULES:
        if rule.id.startswith("skin_"):
            assert rule.urgent_care_signs == (), (
                f"{rule.id} carries its own urgent-care list. No page we hold sets an urgency "
                "threshold for a skin sign."
            )

    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            red_flags=[RedFlag.SKIN_HAIR_LOSS],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )
    # Every line except the ones whose source speaks only for the other animal:
    # Cornell's urethral-obstruction claim is about cats, and this is a dog.
    assert [sign.text for sign in result.urgent_care_signs] == [
        sign.text
        for sign in GENERAL_EMERGENCY_SIGNS
        if sign.species is None or "dog" in sign.species
    ]


def test_the_general_emergency_list_says_where_it_came_from():
    """A result's source list must not appear to cover advice it never sourced.

    The skin pages establish nothing about emergencies, so when a skin answer
    borrows the general emergency signs it has to say so and carry their own
    sources — otherwise one merged list at the foot of the page reads as though
    Merck's dermatology article had endorsed all nine.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            red_flags=[RedFlag.SKIN_HAIR_LOSS],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.urgent_care_signs
    assert result.urgent_care_note is not None
    assert "do not come from the sources behind the result above" in result.urgent_care_note

    # Every line names the page that states it, and they are NOT all the same
    # page: severe pain is Merck's, the gums and the seizure are the ASPCA's.
    # Attributing all of them to both pages jointly implied a reviewer would
    # find each line on either one.
    for sign in result.urgent_care_signs:
        assert sign.sources, f"{sign.text!r} carries no source."
        assert all(source.url.startswith("https://") for source in sign.sources)

    def sources_for(fragment: str) -> set[str]:
        sign = next(s for s in result.urgent_care_signs if fragment in s.text.lower())
        return {source.name for source in sign.sources}

    assert sources_for("severe pain") == {
        "Merck Veterinary Manual - What to Do in a Dog or Cat Emergency"
    }
    assert "ASPCA - Emergency Care for Your Pet" in sources_for("pale or white gums")

    # A pathway with its own sourced list keeps it, and claims no borrowing.
    eye = engine.assess(
        SymptomIntake(
            concern=Concern.EYES,
            body_area=BodyArea.EYE,
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )
    assert eye.urgent_care_signs
    assert eye.urgent_care_note is None
    # Its own list, carried by the citations of the rule that produced it.
    assert all(sign.sources for sign in eye.urgent_care_signs)


def test_explanatory_notes_are_not_filed_as_care_instructions():
    """"Care until the appointment" has to contain care, not explanation."""
    result = engine.assess(
        SymptomIntake(
            concern=Concern.SKIN_OR_COAT,
            red_flags=[RedFlag.SKIN_ITCHING],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.what_to_expect, "The skin pathway explains what a diagnosis involves."
    assert result.care_instructions == [], (
        "Nothing here tells the owner how to care for the animal, so nothing should be filed "
        "under care instructions."
    )
    # And a rule that does give home care still carries it.
    ear = engine.assess(
        SymptomIntake(
            concern=Concern.EARS,
            body_area=BodyArea.EAR,
            red_flags=[RedFlag.EAR_ODOR],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )
    assert any("dry" in item.lower() for item in ear.care_instructions)


def test_a_timing_extrapolation_is_reported_as_partial_urgency_evidence():
    """The eye pathway names 24 hours; no page we hold does. Say so."""
    result = engine.assess(
        SymptomIntake(
            concern=Concern.EYES,
            body_area=BodyArea.EYE,
            duration=Duration.DAYS_2_7,
            trend=Trend.UNCHANGED,
            has_chronic_illness=False,
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert "24 hours" in result.headline.lower()
    urgency = dimension(result, "Evidence for how urgent this is")
    assert urgency.level is ConfidenceLevel.MODERATE
    assert "ours rather than theirs" in urgency.detail


def test_a_sting_does_not_make_a_mild_skin_problem_an_emergency():
    """The reported false positive: an exposure treated as an emergency sign.

    Dog, one itchy red paw for several days, not worsening, none of the
    emergency signs ticked — and, in the accident question, "stung by an
    insect". That came back as "Contact a vet now", with an emergency service
    suggested, on the strength of the ASPCA naming a sting among the causes a
    pet MAY need emergency care because of. The same form's emergency screen had
    just returned nothing, and the two answers contradicted each other.
    """
    mild = SymptomIntake(
        concern=Concern.SKIN_OR_COAT,
        body_area=BodyArea.LEGS_OR_PAWS,
        duration=Duration.DAYS_2_7,
        trend=Trend.UNCHANGED,
        red_flags=[RedFlag.SKIN_ITCHING, RedFlag.SKIN_REDNESS, RedFlag.INSECT_STING_REACTION],
        itch_level=ItchLevel.OCCASIONAL,
        skin_spread=SkinSpread.ONE_AREA,
        species="dog",
        age_category=AgeCategory.ADULT,
    )
    result = engine.assess(mild)

    assert result.level is TriageLevel.AMBER, (
        f"A sting with mild local signs was returned as {result.level.value}."
    )
    assert "sting_with_emergency_signs" not in {rule.rule_id for rule in result.fired_rules}

    # The reaction is what escalates, and it still does.
    reacting = mild.model_copy(
        update={"red_flags": [*mild.red_flags, RedFlag.TROUBLE_BREATHING]}
    )
    escalated = engine.assess(reacting)
    assert escalated.level is TriageLevel.RED
    assert "sting_with_emergency_signs" in {rule.rule_id for rule in escalated.fired_rules}


def test_a_sting_alone_is_declared_rather_than_escalated_or_dismissed():
    """No source covers the middle ground, so the engine says so."""
    result = engine.assess(
        SymptomIntake(
            concern=Concern.OTHER,
            red_flags=[RedFlag.INSECT_STING_REACTION],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.UNASSESSED
    assert result.urgent_care_signs, "The sourced emergency signs are still shown."


def test_the_red_headline_and_advice_agree_about_how_fast():
    """"Contact a vet today" sat above "call now, or an out-of-hours service"."""
    result = engine.assess(
        SymptomIntake(concern=Concern.BREATHING, red_flags=[RedFlag.TROUBLE_BREATHING], species="dog")
    )
    assert result.level is TriageLevel.RED
    assert "today" not in result.headline.lower()
    assert "now" in result.headline.lower()


def test_vomiting_duration_alone_no_longer_claims_missouris_clause():
    """Sick once a day for three days is not "attempts to vomit continue for 24 hours".

    A red rule used to fire on vomiting plus any duration band past "today",
    quoting a Missouri clause the form had never established. The clause is now
    asked about directly, and duration alone supports nothing for vomiting.
    """
    duration_only = SymptomIntake(
        concern=Concern.DIGESTION,
        duration=Duration.DAYS_2_7,
        trend=Trend.WORSENING,
        has_chronic_illness=False,
        red_flags=[RedFlag.VOMITING],
        species="cat",
        age_category=AgeCategory.ADULT,
    )
    result = engine.assess(duration_only)
    assert result.level is not TriageLevel.RED
    assert not any("24 hours" in rule.message for rule in result.fired_rules)

    # Asked and answered, it is red again — on the clause itself.
    reported = duration_only.model_copy(
        update={"red_flags": [RedFlag.VOMITING, RedFlag.VOMITING_MANY_TIMES]}
    )
    escalated = engine.assess(reported)
    assert escalated.level is TriageLevel.RED
    assert "profuse_vomiting_in_a_day" in {rule.rule_id for rule in escalated.fired_rules}


def test_marked_lethargy_with_vomiting_carries_the_result_on_its_own():
    """The reported case: one rule, not two, and still 'contact a vet now'."""
    result = engine.assess(
        SymptomIntake(
            concern=Concern.DIGESTION,
            duration=Duration.DAYS_2_7,
            trend=Trend.WORSENING,
            has_chronic_illness=False,
            red_flags=[RedFlag.VOMITING, RedFlag.EXTREME_LETHARGY],
            species="cat",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.RED
    assert [rule.rule_id for rule in result.fired_rules] == ["gi_signs_with_extreme_lethargy"]

    # Missouri's page is about how fast to act. It says nothing about how the
    # cause is identified, and the report must not borrow another pathway's
    # sources to answer that.
    diagnosis = dimension(result, "Evidence that examination is part of identifying the cause")
    # NOT_ASSESSED rather than LOW: this rule was never asked the question, and
    # "None" is what the panel says when a question was asked of the sources
    # and they did not answer it.
    assert diagnosis.level is ConfidenceLevel.NOT_ASSESSED
    assert "Not assessed" in diagnosis.detail
    assert result.confidence is not None
    assert any("1 rule from our sourced table" in line for line in result.confidence.based_on)
    # The owner's words are not Missouri's, and the answer says so.
    assert any("our step, not theirs" in line for line in result.confidence.based_on)


def test_an_emergency_tells_the_owner_to_travel_not_only_to_phone():
    """The prominent action said "call"; the heatstroke section said "travel".

    The ASPCA's own instruction is to bring the animal in and have someone else
    phone ahead, so the two halves of the answer now say the same thing.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.BREATHING,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[
                RedFlag.TROUBLE_BREATHING,
                RedFlag.OVERHEATING,
                RedFlag.EXTREME_LETHARGY,
            ],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.RED
    advice = result.advice.lower()
    assert "take your pet to a veterinary clinic now" in advice
    assert "call ahead" in advice
    assert any("travel to a veterinary clinic" in item.lower() for item in result.care_instructions)


def _breathing_reason(flag: RedFlag, rule_id: str) -> str:
    result = engine.assess(
        SymptomIntake(
            concern=Concern.BREATHING,
            red_flags=[flag],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )
    assert result.level is TriageLevel.RED
    return next(rule.message for rule in result.fired_rules if rule.rule_id == rule_id).lower()


def test_each_breathing_answer_gets_its_own_reason_and_its_own_publisher():
    """One option, "breathing hard or fast", used to collect two different signs.

    It fired one unconditional emergency rule citing Merck's "trouble breathing"
    and the ASPCA's "rapid breathing" together, as though each page supported
    the whole of what the question collected. They do not: a dog that has just
    run breathes hard and fast, and only one of the two readings survives
    without a qualifier. The question is now two questions and the evidence
    follows each of them separately.
    """
    laboured = _breathing_reason(RedFlag.TROUBLE_BREATHING, "trouble_breathing")
    assert "difficult or laboured" in laboured
    assert "trouble breathing" in laboured
    assert "rapid breathing" not in laboured

    rapid = _breathing_reason(RedFlag.RAPID_BREATHING_AT_REST, "rapid_breathing_at_rest")
    # The qualifier is the whole point of the split and must reach the owner.
    assert "while resting" in rapid
    assert "rapid breathing" in rapid
    assert "trouble breathing" not in rapid


def test_no_breathing_rule_still_fires_on_an_unqualified_hard_or_fast():
    """The retired wording must not come back through any rule's message."""
    from app.services.triage.rules import ALL_RULES

    for rule in ALL_RULES:
        assert "hard or fast" not in rule.message.lower(), (
            f"{rule.id} still describes breathing as 'hard or fast' without qualification. That "
            "question was split because it could not tell distress from panting after exercise."
        )


def test_an_emergency_reported_in_a_follow_up_question_is_still_an_emergency():
    """The first screen is a UI section, not a stored "no emergencies" verdict.

    This test used to forbid ANY intake field with "emergency" in its name, on
    the grounds that the form moved breathing, pale gums, choking and collapse
    out of the emergency screen and into the concern follow-up — so that screen
    could legitimately end with nothing ticked while the next one collected an
    emergency sign, and a stored "no emergency signs" answer would have been a
    lie the engine could act on.

    Both halves of that have changed. The emergency step is now universal and
    no follow-up repeats one of its signs, and `emergency_screen_answered` was
    added for a purpose that is not clinical at all: it decides whether the
    result may say "you did not select any of the emergency warning signs",
    which is a claim about what the owner did and cannot be read off an empty
    list. The wall the old assertion built is still worth having, so it is
    rebuilt here as the thing it was actually protecting — the field may exist,
    and it may not move the verdict.
    """
    emergency_fields = {name for name in SymptomIntake.model_fields if "emergency" in name}
    assert emergency_fields == {"emergency_screen_answered"}, (
        "SymptomIntake has grown another field about emergencies. The flags are the only "
        f"clinical record; found {sorted(emergency_fields)}."
    )

    # It is display-only, and this is what proves it: the same answers, screened
    # or not, reach the same level every time.
    for answers in (
        SymptomIntake(concern=Concern.BREATHING, red_flags=[RedFlag.TROUBLE_BREATHING], species="dog"),
        SymptomIntake(concern=Concern.SKIN_OR_COAT, red_flags=[RedFlag.SKIN_ITCHING], species="dog"),
        SymptomIntake(concern=Concern.MOBILITY, red_flags=[], species="cat"),
    ):
        levels = {
            engine.assess(answers.model_copy(update={"emergency_screen_answered": screened})).level
            for screened in (None, True, False)
        }
        assert len(levels) == 1, (
            f"answering the emergency screen changed the verdict for {answers.concern}: {levels}"
        )

    result = engine.assess(
        SymptomIntake(
            concern=Concern.BREATHING,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            # As the form would send it: nothing from the emergency screen,
            # because the emergency screen never offered these.
            red_flags=[RedFlag.RAPID_BREATHING_AT_REST, RedFlag.EXTREME_LETHARGY],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.RED
    # And the reassuring screening line is withheld, as on any red result.
    assert result.screening_note is None


def test_the_blocked_cat_rule_cites_a_page_that_covers_cats_not_only_males():
    """The form never asks the cat's sex, so the rule must not need it.

    This rule cited only the ACVS's "Urinary Obstruction in Male Cats". The
    disposition was right and the applicability was not: nothing established
    that the cat in front of the owner was male. Cornell's page covers cats,
    names males as higher risk rather than the only ones affected, and states
    the emergency in its own words.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.URINATION,
            duration=Duration.TODAY,
            trend=Trend.WORSENING,
            red_flags=[RedFlag.UNABLE_TO_URINATE],
            species="cat",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.RED
    fired = next(rule for rule in result.fired_rules if rule.rule_id == "unable_to_urinate")
    names = " ".join(fired.sources)
    assert "Feline Lower Urinary Tract Disease" in names
    # The message used to carry "an emergency in any cat", which was how this
    # test checked the answer did not read as male-only. It now says nothing
    # about sex at all, which is the same guarantee more directly: the rule
    # fires on the sign, and nothing in what the owner is shown asks them to
    # decide whether their cat is the kind the ACVS page is about.
    message = fired.message.lower()
    assert "male" not in message
    assert "suspected obstruction requires immediate veterinary attention" in message


def test_the_eye_pathway_never_describes_a_sign_the_owner_did_not_report():
    """The reviewer's finding: "Eyes" alone produced advice about redness and watering.

    Both eye rules shared one message that opened "Redness and watering are not
    specific to one condition". Those are VCA's words for what its page covers,
    not the owner's answers — and the form did not offer redness or watering as
    answers at all, so nobody reaching that message could have reported them.
    """
    bare_concern = engine.assess(SymptomIntake(concern=Concern.EYES, species="dog"))
    message = " ".join(rule.message for rule in bare_concern.fired_rules).lower()
    assert message, "expected the eye concern to still reach a rule"
    for invented in ("redness", "watering", "irritation"):
        assert invented not in message, (
            f"the owner reported no signs, and is being told about {invented!r}"
        )

    # A sign that WAS reported is quoted back, which is the other half of the
    # same guarantee: honest about what we were told, in both directions.
    cloudy = engine.assess(
        SymptomIntake(
            concern=Concern.EYES,
            red_flags=[RedFlag.EYE_CLOUDY_OR_BLUE],
            species="dog",
        )
    )
    cloudy_message = " ".join(rule.message for rule in cloudy.fired_rules).lower()
    assert "cloudy or blue area on the eye" in cloudy_message
    assert "redness" not in cloudy_message
    assert "watering" not in cloudy_message


def test_ordinary_eye_signs_can_now_be_reported_and_reach_the_eye_pathway():
    """Redness, watering and irritation are answers, not just rule wording."""
    result = engine.assess(
        SymptomIntake(
            # Filed under "something else" on purpose: the evidence attaches to
            # the sign, not to the category the owner chose for it.
            concern=Concern.OTHER,
            red_flags=[RedFlag.EYE_REDNESS, RedFlag.EYE_WATERING],
            species="dog",
        )
    )

    assert result.level is TriageLevel.AMBER
    assert any(rule.rule_id == "eye_signs_without_injury" for rule in result.fired_rules)


def test_a_dog_straining_to_urinate_is_an_emergency():
    """The gap a reviewer found: this exact case used to reach no rule at all.

    "Dog -> Toilet trouble -> straining to urinate, producing little or nothing"
    returned our abstention, because every urinary page the library held was
    feline. It was never a judgement that dogs were different; ACVS publishes
    the same article for dogs and Merck's obstruction page covers both species,
    and neither had been opened.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.URINATION,
            duration=Duration.TODAY,
            red_flags=[RedFlag.UNABLE_TO_URINATE],
            species="dog",
            age_category=AgeCategory.ADULT,
        )
    )

    assert result.level is TriageLevel.RED
    fired = next(rule for rule in result.fired_rules if rule.rule_id == "dog_unable_to_urinate")
    names = " ".join(fired.sources)
    assert "Urinary Obstruction in Dogs" in names
    assert "suspected obstruction requires immediate veterinary attention" in fired.message.lower()


def test_the_dog_and_cat_urinary_rules_rest_on_their_own_species_evidence():
    """Neither species rule may be answered out of the other one's pages."""
    dog = engine.assess(
        SymptomIntake(
            concern=Concern.URINATION,
            red_flags=[RedFlag.UNABLE_TO_URINATE],
            species="dog",
        )
    )
    cat = engine.assess(
        SymptomIntake(
            concern=Concern.URINATION,
            red_flags=[RedFlag.UNABLE_TO_URINATE],
            species="cat",
        )
    )

    dog_sources = " ".join(source for rule in dog.fired_rules for source in rule.sources)
    cat_sources = " ".join(source for rule in cat.fired_rules for source in rule.sources)

    # The feline pages are about cats; a dog owner must not be shown them as
    # the reason, which is the mistake the species scope exists to prevent.
    assert "Feline Lower Urinary Tract Disease" not in dog_sources
    assert "Urinary Obstruction in Male Cats" not in dog_sources
    assert "Urinary Obstruction in Dogs" not in cat_sources


def test_straining_to_urinate_is_urgent_even_when_the_species_is_unknown():
    """Red for a dog and red for a cat must not become silence in between.

    Merck states the claim for small animals rather than for one species, so
    the rule carrying that page is not narrowed and answers an intake that
    never said which animal it is.
    """
    result = engine.assess(
        SymptomIntake(
            concern=Concern.URINATION,
            red_flags=[RedFlag.UNABLE_TO_URINATE],
            species=None,
        )
    )

    assert result.level is TriageLevel.RED
    assert any(
        rule.rule_id == "unable_to_urinate_either_species" for rule in result.fired_rules
    )


def test_an_unassessed_diagnostic_dimension_claims_nothing_about_the_pages():
    """"Not assessed" is about our record, not about what a page contains."""
    result = engine.assess(
        SymptomIntake(
            concern=Concern.URINATION,
            red_flags=[RedFlag.UNABLE_TO_URINATE],
            species="cat",
            age_category=AgeCategory.ADULT,
        )
    )

    diagnosis = dimension(result, "Evidence that examination is part of identifying the cause")
    assert diagnosis.level is ConfidenceLevel.NOT_ASSESSED
    assert "Not assessed for this rule" in diagnosis.detail
    # The ACVS page does have a diagnostics section; we must not say otherwise.
    assert "do not describe" not in diagnosis.detail


def test_breed_only_carries_no_confidence_report():
    """Nothing was asked, so there is no answer to be confident about."""
    result = engine.assess(SymptomIntake(concern=Concern.BREED_ONLY, species="dog"))
    assert result.confidence is None


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

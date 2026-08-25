"""Safety invariants — properties that must hold whatever the case.

These are the audit's hard checks. A failure here is a defect in the engine,
not a disagreement about a clinical label, so each test is scoped to exactly
one defect and names it in the assertion message.

Run just this file:
    python -m pytest tests/eval/test_safety_invariants.py -v
"""

from __future__ import annotations

import itertools
import random
import re
from pathlib import Path

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
from app.services.triage.engine import DISCLAIMER
from app.services.triage.candidates import CANDIDATE_RULES
from app.services.triage.rules import (
    ALL_RULES,
    EMERGENCY_SCREENING,
    EMERGENCY_SCREENING_FLAGS,
    GENERAL_EMERGENCY_SIGNS,
    ScreeningBehaviour,
)
from tests.eval import evidence as ev
from tests.eval.cases import CASES
from tests.eval.oracle import CAUTION_ORDER, GENERAL_EMERGENCY_FLAGS, normalise_species

engine = TriageEngine(require_verified=False)

REASSURANCE_MARKERS = (
    "monitor this at home",
    "keep an eye on it",
    "no health concern reported",
)


def _level(intake: SymptomIntake) -> TriageLevel:
    return engine.assess(intake).level


# =========================================================================
# The form and the result must screen for the same emergencies
#
# Three lists used to be maintained by hand and independently: the questions
# the form asks, the rules that read the answers, and the "come back if this
# happens" list shown afterwards. They had drifted. The form asked about a
# urinary blockage, a bloated abdomen with retching, blood in vomit or stool,
# an eye injury and a limb that cannot move; the list shown to an owner
# afterwards named none of the five, so someone told their dog's itchy paw was
# a non-emergency had no way to learn that a bloated abdomen an hour later was.
#
# `EMERGENCY_SCREENING_FLAGS` is now the declaration and these tests are what
# keeps the other two honest.
# =========================================================================


def test_every_emergency_question_has_a_line_to_come_back_for():
    covered = {flag for sign in GENERAL_EMERGENCY_SIGNS for flag in sign.covers}
    missing = sorted(flag.value for flag in EMERGENCY_SCREENING_FLAGS - covered)

    assert not missing, (
        "The form asks about these emergencies and the safety-net list shown afterwards names "
        f"none of them: {missing}. Add a line to GENERAL_EMERGENCY_SIGNS carrying the citation "
        "its own emergency rule already carries, and mark it `covers=`."
    )


def test_no_safety_net_line_claims_to_cover_something_we_never_ask_about():
    """The other direction: a line covering a question nobody is asked.

    Not a safety defect, but it means `covers` has stopped describing reality,
    and the test above is only worth what `covers` is worth.
    """
    covered = {flag for sign in GENERAL_EMERGENCY_SIGNS for flag in sign.covers}
    # BLACK_TARRY_STOOL rides along on the blood-in-stool line, which is how
    # Missouri words it; it is asked elsewhere in the form, not as one of the
    # emergency triggers.
    stray = sorted(
        flag.value for flag in covered - EMERGENCY_SCREENING_FLAGS - {RedFlag.BLACK_TARRY_STOOL}
    )
    assert not stray, f"GENERAL_EMERGENCY_SIGNS covers questions the form never asks: {stray}"


def _levels_reported_alone(flag: RedFlag) -> dict[str, TriageLevel]:
    """The verdict for that flag and nothing else, per animal."""
    return {
        species: engine.assess(
            SymptomIntake(concern=Concern.OTHER, red_flags=[flag], species=species)
        ).level
        for species in ("dog", "cat")
    }


def _covered_species(trigger) -> set[str]:
    return {"dog", "cat"} if trigger.claim_species is None else set(trigger.claim_species)


UNCONDITIONAL = [t for t in EMERGENCY_SCREENING if t.behaviour is ScreeningBehaviour.EMERGENCY]
CONDITIONAL = [t for t in EMERGENCY_SCREENING if t.behaviour is ScreeningBehaviour.CONDITIONAL]


@pytest.mark.parametrize("trigger", UNCONDITIONAL, ids=lambda t: t.flag.value)
def test_an_unconditional_emergency_question_is_red_for_every_animal_it_claims(trigger):
    """Declared as an emergency on its own, so it must be one — per species.

    Per species, not "for at least one of them", which is what an earlier
    version of this test asked. That version passed while a dog reported as
    straining to urinate and producing nothing reached no rule at all, because
    the cat did. Anything narrower than dog-and-cat now has to say so in
    `claim_species`, and say whether the narrowing is the claim's or our
    library's.
    """
    levels = _levels_reported_alone(trigger.flag)
    for species in _covered_species(trigger):
        assert levels[species] is TriageLevel.RED, (
            f"{trigger.flag.value} is declared an emergency for {species}, but reporting it alone "
            f"reaches {levels[species].value}."
        )


@pytest.mark.parametrize(
    "trigger",
    [t for t in UNCONDITIONAL if t.claim_species is not None],
    ids=lambda t: t.flag.value,
)
def test_a_narrowed_emergency_claim_is_honest_about_the_animals_it_drops(trigger):
    """The other animal gets our abstention — never the reassuring end of the scale.

    A narrowed claim means some owner reports a real emergency sign and we have
    nothing to say about it. That has to stay visible: never green, and where
    the narrowing is our citations' rather than the disease's, it must be
    parked as an open question that names itself.
    """
    levels = _levels_reported_alone(trigger.flag)
    for species in {"dog", "cat"} - _covered_species(trigger):
        assert levels[species] is not TriageLevel.GREEN, (
            f"{trigger.flag.value} is not claimed for {species}, and a {species} reported this way "
            "is being told it can be watched at home."
        )

    if trigger.citation_bound_to is not None:
        assert trigger.citation_bound_to in {c["id"] for c in CANDIDATE_RULES}, (
            f"{trigger.flag.value} is narrowed by our citations rather than by the claim, and "
            f"names candidate {trigger.citation_bound_to!r}, which does not exist. The gap has to "
            "be somewhere a reviewer will read it."
        )


@pytest.mark.parametrize("trigger", CONDITIONAL, ids=lambda t: t.flag.value)
def test_a_conditional_emergency_question_escalates_only_with_its_predicate(trigger):
    """Both halves of the predicate, asserted from the model that declares it.

    This was a test-level exception list — "these flags are allowed not to be
    red" — which said nothing about what they ARE red under, and lived where a
    maintainer reading the rule table would never see it.
    """
    assert trigger.escalates_with, (
        f"{trigger.flag.value} is declared conditional but names no escalation signs, so nothing "
        "says what it is conditional on."
    )

    alone = _levels_reported_alone(trigger.flag)
    assert TriageLevel.RED not in alone.values(), (
        f"{trigger.flag.value} alone now reaches red. If a source says it is an emergency on its "
        "own, declare it EMERGENCY and cite the source; do not leave the model saying otherwise."
    )

    for escalation in trigger.escalates_with:
        level = engine.assess(
            SymptomIntake(
                concern=Concern.OTHER,
                red_flags=[trigger.flag, escalation],
                species="dog",
            )
        ).level
        assert level is TriageLevel.RED, (
            f"{trigger.flag.value} with {escalation.value} is declared an emergency and reaches "
            f"{level.value}."
        )


@pytest.mark.parametrize("trigger", CONDITIONAL, ids=lambda t: t.flag.value)
def test_a_conditional_trigger_tells_the_owner_what_the_escalation_looks_like(trigger):
    """The disclosure has to encode the predicate, not just the flag.

    An owner told "come back if the reaction starts" needs the reaction spelled
    out somewhere they are actually shown, so every escalation sign must itself
    be a line in the safety-net list.
    """
    covered = {flag for sign in GENERAL_EMERGENCY_SIGNS for flag in sign.covers}
    missing = sorted(flag.value for flag in set(trigger.escalates_with) - covered)
    assert not missing, (
        f"{trigger.flag.value} escalates with {missing}, and the safety-net list never tells the "
        "owner to come back for them."
    )


def test_a_species_specific_safety_net_line_is_not_shown_to_the_other_animal():
    """Cornell's cat page does not speak for dogs, and this list is shown to all."""

    def lines(species: str | None) -> str:
        result = engine.assess(
            SymptomIntake(
                concern=Concern.SKIN_OR_COAT,
                red_flags=[RedFlag.SKIN_ITCHING],
                species=species,
            )
        )
        return " ".join(sign.text for sign in result.urgent_care_signs)

    assert "urethral obstruction" not in lines("dog")
    assert "gastric dilatation" not in lines("cat")
    assert "urethral obstruction" in lines("cat")
    assert "gastric dilatation" in lines("dog")
    # Told nothing about the animal, an owner is shown both — each line says
    # whose emergency it is, and guessing is the wrong way to be wrong here.
    both = lines(None)
    assert "urethral obstruction" in both and "gastric dilatation" in both


QUALIFIED = [t for t in EMERGENCY_SCREENING if t.owner_facing_qualifier]


@pytest.mark.parametrize("trigger", QUALIFIED, ids=lambda t: t.flag.value)
def test_a_qualified_trigger_keeps_its_qualifier_everywhere_the_owner_reads_it(trigger):
    """Matching identifiers are not matching meanings.

    `rapid_breathing_at_rest` appears in the form, in the rule table and in the
    safety-net list, and the identifier check passes whether the disclosure says
    "unusually fast while resting" or just "rapid breathing". It said the
    second: the over-broad predicate the split removed from the question came
    back one section below it, on the line that tells an owner when to act.

    So where a trigger is deliberately narrower than the bare sign, the words
    that make it narrower are declared, and every place the owner reads about
    it has to carry them.
    """
    qualifier = trigger.owner_facing_qualifier.lower()

    lines = [sign for sign in GENERAL_EMERGENCY_SIGNS if trigger.flag in sign.covers]
    assert lines, f"{trigger.flag.value} has no safety-net line to check."
    for sign in lines:
        assert qualifier in sign.text.lower(), (
            f"The safety-net line for {trigger.flag.value} drops {qualifier!r}, so it tells the "
            f"owner to act on a broader sign than the one we ask about: {sign.text!r}"
        )

    reasons = [
        rule.message
        for rule in ALL_RULES
        if rule.id == trigger.flag.value or trigger.flag.value in rule.id
    ]
    assert reasons, f"No rule is named for {trigger.flag.value}; the reason check is blind."
    for message in reasons:
        assert qualifier in message.lower(), (
            f"The reason shown for {trigger.flag.value} drops {qualifier!r}: {message!r}"
        )

    labels = _labels_source()
    if labels is None:
        return
    label = re.search(rf"{trigger.flag.value}: \"([^\"]+)\"", labels)
    assert label, f"No label for {trigger.flag.value} in SIGN_LABELS; the owner sees no question."
    assert qualifier in label.group(1).lower(), (
        f"The form asks {label.group(1)!r}, which drops {qualifier!r} — the question and the "
        "rule behind it no longer mean the same thing."
    )


def _form_source() -> str | None:
    """Where the emergency screening lists live."""
    form = Path(__file__).resolve().parents[3] / "frontend/src/components/SymptomIntakeForm.tsx"
    return form.read_text(encoding="utf-8") if form.exists() else None


def _labels_source() -> str | None:
    """Where the owner-facing wording for each sign lives.

    Split out from the form when the result card started playing the owner's
    answers back to them under "Your answers" and needed the same strings. This
    check followed the labels rather than staying pointed at the form, where it
    would have passed by finding nothing — which is the failure mode the
    docstring above is about.
    """
    labels = Path(__file__).resolve().parents[3] / "frontend/src/lib/symptomLabels.ts"
    return labels.read_text(encoding="utf-8") if labels.exists() else None


def test_the_form_and_the_engine_screen_for_the_same_emergencies():
    """The last hand-maintained copy of the list: the form's own two questions.

    Their labels and ordering are a UI decision and stay in the component. WHICH
    triggers exist is not, and this is what stops a fourteenth button appearing
    on the form that no rule reads and no safety-net line mentions.
    """
    source = _form_source()
    if source is None:  # backend-only checkouts
        pytest.skip("frontend/ is not present in this checkout")

    asked: set[str] = set()

    # The urgent signs are declared as named GROUPS now - twelve identical
    # chips in one column was the form's most-complained-about screen. The
    # grouping is a UI decision; this reads whichever flags end up inside it,
    # so regrouping is free and adding a thirteenth is not.
    groups = re.search(
        r"const URGENT_SIGN_GROUPS: Array<\{ label: string; signs: RedFlag\[\] \}> = \[(.*?)\n\];",
        source,
        re.DOTALL,
    )
    assert groups, (
        "Could not find URGENT_SIGN_GROUPS in SymptomIntakeForm.tsx; the check is now blind."
    )
    # Only the signs, not the group labels: labels are prose and would other-
    # wise arrive here as fake flag names.
    for block in re.findall(r"signs: \[(.*?)\]", groups.group(1), re.DOTALL):
        asked |= set(re.findall(r'"([a-z_]+)"', block))

    accidents = re.search(r"const ACCIDENTS: RedFlag\[\] = \[(.*?)\];", source, re.DOTALL)
    assert accidents, "Could not find ACCIDENTS in SymptomIntakeForm.tsx; the check is now blind."
    asked |= set(re.findall(r'"([a-z_]+)"', accidents.group(1)))

    declared = {flag.value for flag in EMERGENCY_SCREENING_FLAGS}
    assert asked == declared, (
        "The form's emergency questions and EMERGENCY_SCREENING_FLAGS disagree. "
        f"Asked on the form but not declared: {sorted(asked - declared)}. "
        f"Declared but not asked on the form: {sorted(declared - asked)}."
    )



# =========================================================================
# Monotonicity and order independence
# =========================================================================


def test_adding_an_emergency_sign_never_reduces_urgency():
    """Every case in the set, with each emergency sign added in turn."""
    regressions = []
    for case in CASES:
        base = _level(case.intake)
        for flag in sorted(GENERAL_EMERGENCY_FLAGS, key=lambda f: f.value):
            if flag in case.intake.red_flags:
                continue
            escalated = case.intake.model_copy(
                update={"red_flags": [*case.intake.red_flags, flag]}
            )
            after = _level(escalated)
            if CAUTION_ORDER[after] < CAUTION_ORDER[base]:
                regressions.append(f"{case.id} + {flag.value}: {base.value} -> {after.value}")
    assert not regressions, (
        "Adding an emergency sign lowered the urgency:\n  " + "\n  ".join(regressions[:20])
    )


def test_reordering_red_flags_does_not_change_the_result():
    rng = random.Random(1234)
    for case in CASES:
        if len(case.intake.red_flags) < 2:
            continue
        baseline = engine.assess(case.intake)
        shuffled = list(case.intake.red_flags)
        rng.shuffle(shuffled)
        other = engine.assess(case.intake.model_copy(update={"red_flags": shuffled}))
        assert other.level is baseline.level, f"{case.id}: level depends on red-flag order."
        assert [r.rule_id for r in other.fired_rules] == [
            r.rule_id for r in baseline.fired_rules
        ], f"{case.id}: fired rules depend on red-flag order."


def test_duplicating_red_flags_does_not_change_the_result():
    for case in CASES:
        if not case.intake.red_flags:
            continue
        baseline = engine.assess(case.intake)
        doubled = engine.assess(
            case.intake.model_copy(update={"red_flags": [*case.intake.red_flags] * 3})
        )
        assert doubled.level is baseline.level, f"{case.id}: level changed when flags repeated."
        assert doubled.score == baseline.score, f"{case.id}: score changed when flags repeated."


def test_filling_in_an_optional_field_never_lowers_urgency():
    """Answering a question the owner could have skipped must not help them.

    Species is excluded here and tested on its own below, because naming an
    unsupported species is a documented (and separately reported) exception.

    ONE MORE EXCEPTION, added deliberately and narrowly: an answer may turn an
    ABSTENTION into a verdict, including a green one.

    `UNASSESSED` is not a point on this scale - `TriageLevel` says so in as many
    words: "not a fourth point on the urgency scale; it is a refusal to place
    the case on the scale at all". `CAUTION_ORDER` has to sort it somewhere, and
    ranking it above green is right for reporting, but it makes every
    abstention-resolved-by-an-answer look like a de-escalation here.

    The case that forced this: Missouri's home-care advice is scoped to an
    "otherwise healthy ADULT pet", so the rule now requires the age to be known
    rather than treating an animal nobody has told us about as an adult. An
    intake with no age abstains; supplying "adult" lets the rule apply. Refusing
    that transition would mean the only way to pass this test is to go back to
    assuming every unknown animal is a healthy adult, which is the bug this
    exception exists because of.

    Everything else is unchanged and still enforced: red, amber and green may
    never move downwards among themselves, whatever the owner answers.
    """
    regressions = []
    optional = {
        "duration": list(Duration),
        "trend": list(Trend),
        "time_since_eating": list(TimeSinceEating),
        "age_category": list(AgeCategory),
        "has_chronic_illness": [True, False],
        "body_area": list(BodyArea),
    }
    for case in CASES:
        base = _level(case.intake)
        for field, values in optional.items():
            if getattr(case.intake, field) is not None:
                continue
            for value in values:
                after = _level(case.intake.model_copy(update={field: value}))
                # An abstention resolving into a verdict is not a de-escalation;
                # see the docstring. Every other pair is still checked.
                if base is TriageLevel.UNASSESSED:
                    continue
                if CAUTION_ORDER[after] < CAUTION_ORDER[base]:
                    regressions.append(
                        f"{case.id}: setting {field}={value} dropped {base.value} -> {after.value}"
                    )
    assert not regressions, (
        "Supplying an optional answer lowered urgency:\n  " + "\n  ".join(regressions[:20])
    )


# =========================================================================
# Species handling
# =========================================================================


def test_species_whitespace_does_not_disable_rules():
    """' cat ' must behave exactly like 'cat'.

    Regression guard. `Rule.matches` used to strip and casefold while the
    `SpeciesIs` condition inside a rule only lowercased, so a species arriving
    with surrounding whitespace passed the rule's species scope and failed the
    condition — silently disabling every `SpeciesIs`-gated rule, all of which
    are emergencies. Both now go through `app.core.species.normalise_species`.
    """
    intake = SymptomIntake(
        concern=Concern.DIGESTION,
        duration=Duration.DAYS_2_7,
        red_flags=[RedFlag.NOT_EATING],
        time_since_eating=TimeSinceEating.OVER_24H,
        age_category=AgeCategory.ADULT,
    )
    mismatches = []
    for raw in (" cat ", "cat ", " cat", "\tcat", "Cat ", " dog ", "dog\n"):
        padded = engine.assess(intake.model_copy(update={"species": raw}))
        clean = engine.assess(intake.model_copy(update={"species": raw.strip()}))
        if padded.level is not clean.level:
            mismatches.append(
                f"species={raw!r}: {padded.level.value} vs {clean.level.value} for the trimmed value"
            )
    assert not mismatches, (
        "Untrimmed species silently changed the verdict:\n  " + "\n  ".join(mismatches)
    )


def test_species_specific_evidence_is_never_applied_to_another_species():
    """Cat-only and dog-only rules must not fire for the other species."""
    from app.services.triage.rules import ALL_RULES

    species_specific = [rule for rule in ALL_RULES if rule.is_species_specific]
    assert species_specific, "Expected at least one species-narrowed rule to check."

    violations = []
    for case in CASES:
        species = normalise_species(case.intake.species)
        if species is None:
            continue
        fired = {rule.rule_id for rule in engine.assess(case.intake).fired_rules}
        for rule in species_specific:
            if rule.id in fired and species not in rule.applies_to_species:
                violations.append(f"{case.id}: {rule.id} fired for species {species!r}")
    assert not violations, "Species-scoped evidence leaked:\n  " + "\n  ".join(violations)


def test_emergency_guidance_survives_a_missing_species():
    """Leaving species blank must not silence dog-and-cat emergency evidence."""
    silenced = []
    for flag in sorted(GENERAL_EMERGENCY_FLAGS, key=lambda f: f.value):
        result = engine.assess(
            SymptomIntake(concern=Concern.OTHER, red_flags=[flag], species=None)
        )
        as_dog = engine.assess(
            SymptomIntake(concern=Concern.OTHER, red_flags=[flag], species="dog")
        )
        as_cat = engine.assess(
            SymptomIntake(concern=Concern.OTHER, red_flags=[flag], species="cat")
        )
        if as_dog.level is TriageLevel.RED and as_cat.level is TriageLevel.RED:
            if result.level is not TriageLevel.RED:
                silenced.append(
                    f"{flag.value}: red for both dog and cat, but {result.level.value} "
                    "when the species is unknown"
                )
    assert not silenced, (
        "Guidance that applies to dogs AND cats was withheld for an unidentified animal:\n  "
        + "\n  ".join(silenced)
    )


def test_unsupported_species_emergency_is_not_returned_as_green():
    """A reported emergency in a species we cannot assess must not read green.

    The prose for an unassessable case was always careful, but `level` is the
    machine-readable field a client colours on, and GREEN is the reassuring end
    of the scale — an owner reporting a seizing rabbit was landing there. These
    now return `UNASSESSED`, which is a refusal to place the case on the scale
    rather than a quiet position at its calm end.
    """
    green_emergencies = []
    for species, flag in itertools.product(
        ("rabbit", "ferret", "guinea pig", "parrot", "bearded dragon"),
        sorted(GENERAL_EMERGENCY_FLAGS, key=lambda f: f.value),
    ):
        result = engine.assess(
            SymptomIntake(concern=Concern.OTHER, red_flags=[flag], species=species)
        )
        if result.level is TriageLevel.GREEN:
            green_emergencies.append(f"{species} + {flag.value}")
    assert not green_emergencies, (
        f"{len(green_emergencies)} unassessable emergencies were returned at GREEN level, "
        "e.g.:\n  " + "\n  ".join(green_emergencies[:10])
    )


# =========================================================================
# The UNASSESSED contract
# =========================================================================


def test_an_unassessed_result_never_reads_as_reassurance():
    """Abstaining must not sound like a clean bill of health."""
    seen = 0
    for case in CASES:
        result = engine.assess(case.intake)
        if result.level is not TriageLevel.UNASSESSED:
            continue
        seen += 1
        text = f"{result.headline} {result.advice}".lower()
        assert not any(marker in text for marker in REASSURANCE_MARKERS), (
            f"{case.id}: an unassessed result used reassurance language: {result.headline!r}"
        )
        assert "can't assess" in result.headline.lower(), (
            f"{case.id}: an unassessed result must say plainly that we cannot assess it."
        )
        # The instruction, not one particular phrasing of it. The copy moved
        # from "contact your veterinary practice" to "contact a veterinarian";
        # what this guards is that an abstention still sends the owner to one.
        assert "contact a veterinarian" in result.advice.lower(), (
            f"{case.id}: an unassessed result must point the owner at a veterinarian."
        )
        assert "safe to ignore" in result.advice.lower(), (
            f"{case.id}: an unassessed result must say the problem may still matter."
        )
        assert not result.fired_rules, (
            f"{case.id}: abstained while claiming {len(result.fired_rules)} reasons."
        )
    assert seen, "Expected the evaluation set to contain unassessable cases."


def test_unassessed_is_never_returned_when_a_rule_actually_matched():
    """`UNASSESSED` must not be able to hide a red or amber the rules produced."""
    from app.services.triage.rules import ALL_RULES

    hidden = []
    for case in CASES:
        result = engine.assess(case.intake)
        if result.level is not TriageLevel.UNASSESSED:
            continue
        matched = [rule.id for rule in ALL_RULES if rule.matches(case.intake)]
        if matched:
            hidden.append(f"{case.id}: abstained although {matched} matched")
    assert not hidden, "Abstention masked applicable evidence:\n  " + "\n  ".join(hidden)


def test_a_dog_or_cat_case_with_applicable_evidence_is_never_unassessed():
    """The abstention is for gaps in the evidence, not gaps in the plumbing.

    Scoped to labels a source states in so many words. Where the label needed
    the auditor to reason past a page — the feline-anorexia readings, which take
    Cornell's 24-hour threshold to imply something about a shorter fast — the
    engine abstaining is the *correct* behaviour under the no-inferred-clinical-
    logic rule, and the gap is recorded for veterinary adjudication instead. See
    `test_inference_dependent_abstentions_are_listed` below.
    """
    from tests.eval.oracle import NEEDS_REVIEW, expected_label

    wrongly_abstained = []
    for case in CASES:
        if normalise_species(case.intake.species) not in ("dog", "cat"):
            continue
        label = expected_label(case.intake)
        if label.level is NEEDS_REVIEW or label.level is TriageLevel.GREEN or label.inferred:
            continue
        if engine.assess(case.intake).level is TriageLevel.UNASSESSED:
            wrongly_abstained.append(
                f"{case.id}: evidence supports {label.level.value} — {label.rationale[:90]}"
            )
    assert not wrongly_abstained, (
        f"{len(wrongly_abstained)} dog/cat cases the sources cover were answered with an "
        "abstention:\n  " + "\n  ".join(wrongly_abstained[:12])
    )


def test_inference_dependent_abstentions_are_listed(capsys):
    """Print every case a veterinarian still has to settle. Never fails.

    These are the cases where the audit's own label rests on reading past a
    source's wording, so implementing them as rules would be inventing clinical
    logic. The engine abstains; this test keeps the list visible.
    """
    from tests.eval.oracle import NEEDS_REVIEW, expected_label

    pending = []
    for case in CASES:
        if normalise_species(case.intake.species) not in ("dog", "cat"):
            continue
        label = expected_label(case.intake)
        if label.level is NEEDS_REVIEW or not label.inferred:
            continue
        if engine.assess(case.intake).level is TriageLevel.UNASSESSED:
            pending.append((case.id, label.level.value, label.rationale))

    with capsys.disabled():
        print(f"\n{len(pending)} abstentions awaiting veterinary adjudication:")
        for reason in sorted({rationale for _, _, rationale in pending}):
            ids = [cid for cid, _, r in pending if r == reason]
            print(f"  {len(ids)} case(s): {reason}")
            print(f"    e.g. {', '.join(ids[:4])}")
    assert all(rationale for _, _, rationale in pending), "A deferral with no stated reason."


def test_green_is_only_reached_when_no_health_question_was_asked():
    """Absence of a matching rule is not evidence that home monitoring is safe.

    Until an evidence-backed low-risk pathway exists, the only green the engine
    may produce is the breed-only one, where the owner asked nothing clinical.
    """
    unearned = []
    for case in CASES:
        result = engine.assess(case.intake)
        if result.level is not TriageLevel.GREEN:
            continue
        if result.fired_rules:
            continue  # a rule produced this; its own evidence carries it
        if case.intake.concern is Concern.BREED_ONLY and not case.intake.red_flags:
            continue
        unearned.append(f"{case.id}: green with no rule and no breed-only exemption")
    assert not unearned, (
        "Green returned without evidence behind it:\n  " + "\n  ".join(unearned[:12])
    )


def test_all_species_evidence_is_applied_to_all_species():
    """A source that says 'all species' must not be narrowed to dogs and cats.

    Merck's corrosive-agents page states that all species are susceptible and
    requires flushing followed by fluorescein examination, and `sources.py`
    records that page with `species=None`.
    """
    withheld = []
    for species in ("rabbit", "ferret", "guinea pig", "parrot", "horse"):
        result = engine.assess(
            SymptomIntake(
                concern=Concern.EYES,
                body_area=BodyArea.EYE,
                red_flags=[RedFlag.EYE_CHEMICAL_EXPOSURE],
                species=species,
            )
        )
        if result.level is not TriageLevel.RED:
            withheld.append(f"{species}: {result.level.value}")
    assert not withheld, (
        "Corrosive ocular exposure is all-species evidence but was withheld from:\n  "
        + "\n  ".join(withheld)
    )


@pytest.mark.parametrize("raw", ev.AMBIGUOUS_UNKNOWN_SPECIES_VALUES)
def test_placeholder_species_values_do_not_silently_disable_the_rule_table(raw):
    """A pet saved with species 'unknown' must not silence every emergency.

    `species` is free text on the Animal model and is copied into the intake by
    `symptom_checks.py`. Each of these placeholders means "not told", so the
    dog-and-cat evidence must still apply exactly as it does for a blank.
    """
    result = engine.assess(
        SymptomIntake(concern=Concern.OTHER, red_flags=[RedFlag.SEIZURE], species=raw)
    )
    blank = engine.assess(
        SymptomIntake(concern=Concern.OTHER, red_flags=[RedFlag.SEIZURE], species=None)
    )
    assert result.level is TriageLevel.RED, (
        f"species={raw!r} with a reported seizure returned {result.level.value}. A placeholder "
        "species value must be read as 'unknown', not as an animal nothing covers."
    )
    assert [r.rule_id for r in result.fired_rules] == [r.rule_id for r in blank.fired_rules], (
        f"species={raw!r} fired different rules from a blank species."
    )


# =========================================================================
# No false reassurance
# =========================================================================


def test_a_recommendation_resting_on_our_own_bar_says_whose_bar_it_is():
    """Where the action is our judgement, the action itself must admit it.

    The engine can be scrupulous in its confidence panel and still overstate the
    thing an owner actually reads. "Veterinary examination recommended" sat
    above a panel saying, correctly, that no source establishes that a
    presentation this mild needs an appointment rather than watching — and the
    headline is what people act on. Any result whose rules take a THRESHOLD step
    has to own that where the recommendation is made.
    """
    from app.schemas.triage import ExtrapolationKind
    from app.services.triage.rules import ALL_RULES

    silent = []
    for case in CASES:
        result = engine.assess(case.intake)
        if result.level is not TriageLevel.AMBER:
            continue
        matched = [rule for rule in ALL_RULES if rule.matches(case.intake)]
        if not any(ExtrapolationKind.THRESHOLD in rule.extrapolations for rule in matched):
            continue
        advice = result.advice.lower()
        if "our own judgement" not in advice and "our cautious default" not in advice:
            silent.append(f"{case.id}: {result.advice[:80]!r}")
    assert not silent, (
        f"{len(silent)} results recommend an appointment on a bar we set ourselves without "
        "saying so:" + "".join("\n  " + line for line in silent[:10])
    )


def test_a_reported_sign_is_never_answered_with_monitor_at_home():
    offenders = []
    for case in CASES:
        if not case.intake.red_flags:
            continue
        result = engine.assess(case.intake)
        text = f"{result.headline} {result.advice}".lower()
        if any(marker in text for marker in REASSURANCE_MARKERS):
            offenders.append(f"{case.id}: {result.headline!r}")
    assert not offenders, (
        "Reported signs were answered with home-monitoring language:\n  "
        + "\n  ".join(offenders[:15])
    )


def test_a_reported_concern_without_a_red_flag_is_not_told_to_monitor_at_home():
    """Ticking no red flag is not evidence that nothing is wrong.

    An owner who selects a concern, a duration and a worsening trend has told
    us something. No source in the ledger supports answering that with home
    monitoring, and for several concerns the reassurance is actively unsafe.
    """
    offenders = []
    for concern, species in itertools.product(
        [c for c in Concern if c is not Concern.BREED_ONLY], ("dog", "cat", None, "rabbit")
    ):
        result = engine.assess(
            SymptomIntake(
                concern=concern,
                duration=Duration.DAYS_2_7,
                trend=Trend.WORSENING,
                species=species,
                age_category=AgeCategory.ADULT,
            )
        )
        text = f"{result.headline} {result.advice}".lower()
        if any(marker in text for marker in REASSURANCE_MARKERS):
            offenders.append(f"concern={concern.value}, species={species!r}")
    assert not offenders, (
        f"{len(offenders)} worsening, multi-day concerns with no rule coverage were told to "
        "monitor at home:\n  " + "\n  ".join(offenders[:15])
    )


def test_breed_only_mode_does_not_ignore_reported_emergency_signs():
    ignored = []
    for flag in sorted(GENERAL_EMERGENCY_FLAGS, key=lambda f: f.value):
        for species in ("dog", "cat", None):
            result = engine.assess(
                SymptomIntake(concern=Concern.BREED_ONLY, red_flags=[flag], species=species)
            )
            if "no health concern" in result.headline.lower():
                ignored.append(f"{flag.value} / species={species!r}")
    assert not ignored, (
        "Breed-only mode discarded a reported emergency sign:\n  " + "\n  ".join(ignored)
    )


# =========================================================================
# Explanation integrity
# =========================================================================


def test_every_fired_rule_carries_a_working_source_link():
    from app.services.triage.sources import ALL_SOURCES

    known = {source.url for source in ALL_SOURCES}
    for case in CASES:
        for fired in engine.assess(case.intake).fired_rules:
            assert fired.sources, f"{case.id}/{fired.rule_id}: no source named."
            assert fired.source_links, f"{case.id}/{fired.rule_id}: no source link."
            assert len(fired.source_links) == len(fired.sources), (
                f"{case.id}/{fired.rule_id}: link count does not match source count."
            )
            for link in fired.source_links:
                assert link.url.startswith("https://"), (
                    f"{case.id}/{fired.rule_id}: {link.url!r} is not a link."
                )
                assert link.url in known, (
                    f"{case.id}/{fired.rule_id}: {link.url!r} is not in the vetted source list."
                )


def test_the_explanation_lists_exactly_the_rules_that_decided_the_level():
    """Whatever the engine shows must be what actually drove the verdict."""
    from app.services.triage.rules import ALL_RULES

    for case in CASES:
        result = engine.assess(case.intake)
        matched = [rule for rule in ALL_RULES if rule.matches(case.intake)]
        emergencies = {rule.id for rule in matched if rule.is_emergency}
        shown = {fired.rule_id for fired in result.fired_rules}
        if result.level is TriageLevel.RED:
            assert shown == emergencies, (
                f"{case.id}: red verdict shows {sorted(shown)}, "
                f"emergency rules that fired were {sorted(emergencies)}."
            )
        elif shown:
            assert shown == {rule.id for rule in matched}, (
                f"{case.id}: shown rules {sorted(shown)} do not match fired rules "
                f"{sorted(rule.id for rule in matched)}."
            )


def test_a_displayed_score_is_reconcilable_with_the_displayed_rules():
    """The owner must be able to add the shown weights up to the shown score."""
    mismatches = []
    for case in CASES:
        result = engine.assess(case.intake)
        shown_total = sum(fired.weight for fired in result.fired_rules)
        if shown_total != result.score:
            mismatches.append(
                f"{case.id}: score {result.score} but the listed reasons total {shown_total}"
            )
    assert not mismatches, (
        f"{len(mismatches)} results reported a score the shown reasons cannot produce:\n  "
        + "\n  ".join(mismatches[:10])
    )


_SYSTEMIC_EMERGENCY_RULES = frozenset(
    {
        "trouble_breathing",
        "collapse_or_unresponsive",
        "seizure",
        "pale_gums",
        "uncontrolled_bleeding",
        "choking",
        "major_trauma",
        "severe_pain",
        "heatstroke",
        "suspected_poisoning",
    }
)


def test_the_headline_reflects_the_most_serious_reason_that_fired():
    """A pet that cannot breathe must not be given an eye or ear headline.

    Scoped to cases where a whole-body emergency rule actually FIRED. Where the
    owner reports collapse in a species we hold no evidence for, no rule fires
    for it and the headline can only speak for what did — that is a species
    coverage gap, reported separately, not a headline-ordering defect.
    """
    body_part_headline = re.compile(r"\b(eye|ear)\b", re.IGNORECASE)
    misleading = []
    for case in CASES:
        result = engine.assess(case.intake)
        if result.level is not TriageLevel.RED:
            continue
        fired = {rule.rule_id for rule in result.fired_rules}
        systemic = fired & _SYSTEMIC_EMERGENCY_RULES
        if systemic and body_part_headline.search(result.headline):
            misleading.append(
                f"{case.id}: {sorted(systemic)} fired but the headline is {result.headline!r}"
            )
    assert not misleading, (
        f"{len(misleading)} life-threatening cases were given a body-part headline:\n  "
        + "\n  ".join(misleading[:10])
    )


# =========================================================================
# What the advice may say
# =========================================================================

_DOSE = re.compile(r"\b\d+(\.\d+)?\s*(mg|milligram|ml|millilitre|milliliter|mcg|g|iu)\b", re.I)
_DRUGS = (
    "paracetamol", "acetaminophen", "ibuprofen", "aspirin", "meloxicam", "metacam",
    "prednisolone", "prednisone", "dexamethasone", "amoxicillin", "metronidazole",
    "omeprazole", "maropitant", "cerenia", "gabapentin", "tramadol", "benadryl",
    "diphenhydramine", "hydrogen peroxide", "activated charcoal",
)
_PRESCRIBING = ("give your pet", "administer", "dose of", "twice daily", "every 8 hours")
_DIAGNOSIS = ("your pet has ", "this is definitely", "the diagnosis is", "we can confirm")


def _all_text(result) -> str:
    return " ".join(
        [
            result.headline,
            result.advice,
            result.disclaimer,
            *(fired.message for fired in result.fired_rules),
            *(sign.text for sign in result.urgent_care_signs),
            *result.care_instructions,
        ]
    ).lower()


def test_no_output_contains_a_dose_a_drug_name_or_a_prescribing_instruction():
    offenders = []
    for case in CASES:
        text = _all_text(engine.assess(case.intake))
        if _DOSE.search(text):
            offenders.append(f"{case.id}: dose-like text")
        for drug in _DRUGS:
            # A warning not to use something is not a prescribing instruction.
            if drug in text and not re.search(rf"(do not|don't|never)[^.]*{re.escape(drug)}", text):
                offenders.append(f"{case.id}: names {drug!r} without a 'do not' framing")
        for phrase in _PRESCRIBING:
            if phrase in text:
                offenders.append(f"{case.id}: prescribing phrase {phrase!r}")
    assert not offenders, "Medication or dosage instructions found:\n  " + "\n  ".join(
        dict.fromkeys(offenders)
    )


def test_no_output_states_a_diagnosis():
    offenders = [
        f"{case.id}: {phrase!r}"
        for case in CASES
        for phrase in _DIAGNOSIS
        if phrase in _all_text(engine.assess(case.intake))
    ]
    assert not offenders, "Diagnostic claims found:\n  " + "\n  ".join(offenders)


def test_the_non_diagnosis_disclaimer_is_always_present():
    for case in CASES:
        result = engine.assess(case.intake)
        assert result.disclaimer == DISCLAIMER, f"{case.id}: disclaimer altered or missing."
        assert "not a diagnosis" in result.disclaimer.lower()


def test_first_aid_instructions_are_traceable_to_a_cited_source():
    """Any 'do this now' instruction must be supported by a cited page.

    Checked against each rule's own `supports` paraphrase, which is what a
    reviewer reads when deciding whether the wording is justified.
    """
    from app.services.triage.rules import ALL_RULES

    # Each action maps to the words a citation must contain for it to be
    # traceable. Matching on the action's first word was too brittle — a page
    # that says "cool the head and body" supports "start cooling" perfectly
    # well, and a page that says nothing about cooling must still be caught.
    actions = {
        "start cooling": ("cool", "cooling"),
        "flush": ("flush", "flushing", "irrigat"),
        "induce vomiting": ("induce", "emesis"),
        "apply pressure": ("pressure",),
        "bandage": ("bandage", "dressing"),
    }
    unsupported = []
    for rule in ALL_RULES:
        text = " ".join([rule.message, rule.advice or "", *rule.care_instructions]).lower()
        supports = " ".join(citation.supports for citation in rule.citations).lower()
        for action, evidence_words in actions.items():
            if action in text and not any(word in supports for word in evidence_words):
                unsupported.append(f"{rule.id}: tells the owner to {action!r}; no citation says so")
    assert not unsupported, (
        "First-aid instructions with no supporting citation:\n  " + "\n  ".join(unsupported)
    )


# =========================================================================
# Robustness
# =========================================================================


def test_the_engine_survives_every_case_in_the_set():
    for case in CASES:
        result = engine.assess(case.intake)
        assert result.level in tuple(TriageLevel)
        assert result.headline and result.advice and result.disclaimer


def test_the_engine_survives_hostile_and_empty_input():
    weird = [
        SymptomIntake(),
        SymptomIntake(species=""),
        SymptomIntake(species="   "),
        SymptomIntake(species="\x00\x01"),
        SymptomIntake(species="ドッグ"),
        SymptomIntake(species="dog" * 500),
        SymptomIntake(red_flags=[]),
        SymptomIntake(red_flags=list(RedFlag) * 4),
        SymptomIntake(concern=Concern.OTHER, has_chronic_illness=False, weight_bearing=True),
        SymptomIntake(age_category=AgeCategory.UNKNOWN, species="dog"),
    ]
    for intake in weird:
        result = engine.assess(intake)
        assert result.disclaimer, f"{intake!r} produced a result with no disclaimer."


def test_the_engine_is_deterministic():
    for case in CASES[::7]:
        first = engine.assess(case.intake)
        second = engine.assess(case.intake)
        assert first.model_dump() == second.model_dump(), f"{case.id} is not deterministic."

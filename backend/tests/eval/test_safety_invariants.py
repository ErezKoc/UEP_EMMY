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
        assert "contact your veterinary practice" in result.advice.lower(), (
            f"{case.id}: an unassessed result must point the owner at a veterinarian."
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
            *result.urgent_care_signs,
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

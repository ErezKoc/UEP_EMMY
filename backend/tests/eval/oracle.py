"""Derives an expected triage level for an intake from `evidence.py` alone.

This is the audit's oracle. It does not import the production rule table, and
it was written from the source readings recorded in `evidence.py` rather than
from `rules.py`.

Three deliberate design choices:

1. **Signs carry their own evidence.** If a source says a cloudy eye needs
   urgent care, this oracle escalates a reported cloudy eye whatever the owner
   picked as their "concern". Evidence attaches to the sign, not to the form.
2. **Negative findings are honoured.** Merck does not call otitis interna or an
   auricular hematoma an emergency, so those signs label AMBER, not RED, even
   though escalating them further would be the safer error.
3. **Absence of evidence is not GREEN.** Where no source speaks, the label is
   `NEEDS_REVIEW` and the case is excluded from accuracy. Safety invariants
   still apply to those cases.

Labels resting on any finding marked `inference` are flagged `inferred=True`,
so a disagreement that depends on the auditor's reasoning can be separated from
one that contradicts a source's literal words.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.animal import AgeCategory
from app.schemas.triage import (
    BodyArea,
    Concern,
    Duration,
    RedFlag,
    SymptomIntake,
    TimeSinceEating,
    TriageLevel,
)
from tests.eval import evidence as ev
from tests.eval.evidence import Finding, Urgency

NEEDS_REVIEW = "needs_expert_review"

#: Clinical urgency, for comparing a label with a result. `UNASSESSED` is
#: deliberately absent: it is not a point on this scale, it is a refusal to use
#: the scale, and giving it a number here would let an abstention silently
#: count as agreement with a red label.
SEVERITY = {TriageLevel.GREEN: 0, TriageLevel.AMBER: 1, TriageLevel.RED: 2}

#: How much caution each answer conveys to the owner, which is a different
#: question from clinical urgency. Used only by the monotonicity and metamorphic
#: relations, where the property being tested is "this input change must not
#: make the answer calmer". `UNASSESSED` outranks `GREEN` because it withholds
#: reassurance, and sits below `AMBER` because it recommends nothing specific.
CAUTION_ORDER = {
    TriageLevel.GREEN: 0,
    TriageLevel.UNASSESSED: 1,
    TriageLevel.AMBER: 2,
    TriageLevel.RED: 3,
}

_URGENCY_TO_LEVEL = {
    Urgency.EMERGENCY: TriageLevel.RED,
    Urgency.PROMPT_EXAM: TriageLevel.AMBER,
    Urgency.WATCHFUL: TriageLevel.GREEN,
}

_MULTI_DAY = (Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)

#: Signs whose own source calls them an emergency for dogs and cats. Used by the
#: safety-invariant tests to ask whether guidance was suppressed.
GENERAL_EMERGENCY_FLAGS = frozenset(
    {
        RedFlag.TROUBLE_BREATHING,
        RedFlag.RAPID_BREATHING_AT_REST,
        RedFlag.SEVERE_PAIN,
        RedFlag.UNCONTROLLED_BLEEDING,
        RedFlag.SUSPECTED_POISONING,
        RedFlag.EYE_INJURY,
        RedFlag.LIMB_CANNOT_MOVE,
        RedFlag.SEIZURE,
        RedFlag.COLLAPSE_OR_UNRESPONSIVE,
        RedFlag.PALE_GUMS,
        RedFlag.MAJOR_TRAUMA,
        RedFlag.CHOKING,
        # INSECT_STING_REACTION is deliberately absent. The ASPCA names a sting
        # among the causes a pet MAY need emergency care because of, and never
        # says a sting alone is life-threatening — so it is not a sign whose own
        # source calls it an emergency, which is what this set means.
        RedFlag.OVERHEATING,
        RedFlag.BLOOD_IN_VOMIT_OR_STOOL,
        RedFlag.BLACK_TARRY_STOOL,
        RedFlag.EYE_CHEMICAL_EXPOSURE,
        # Added 2026-08-22. Merck's urethral obstruction page calls it an
        # emergency for small animals, dogs and cats alike, so the sign now
        # meets this set's own definition. While the only pages we held were
        # feline, it did not, and an unidentified animal reported this way was
        # given no urgency at all.
        RedFlag.UNABLE_TO_URINATE,
    }
)

#: Eye signs whose own source calls them urgent, and which findings carry them.
#: Blepharospasm (an eye held closed), corneal edema (cloudiness), mydriasis and
#: loss of vision are all named by Merck as signs of acute glaucoma, which that
#: page calls an ophthalmological emergency — so those three do not depend on
#: the VCA urgent-care page alone.
_EYE_URGENT_FLAGS: dict[RedFlag, tuple] = {
    RedFlag.EYE_PAIN_OR_CLOSED: (ev.MERCK_GLAUCOMA, ev.VCA_EYE_URGENT),
    RedFlag.EYE_CLOUDY_OR_BLUE: (ev.MERCK_GLAUCOMA, ev.VCA_EYE_URGENT),
    RedFlag.UNEQUAL_PUPILS_OR_VISION_CHANGE: (ev.MERCK_GLAUCOMA,),
    RedFlag.EYE_BULGING_OR_SEVERE_SWELLING: (ev.VCA_EYE_URGENT,),
    RedFlag.EYE_DISCHARGE_YELLOW_GREEN_OR_BLOODY: (ev.VCA_EYE_URGENT,),
}

_OTITIS_EXTERNA_FLAGS = {
    RedFlag.EAR_HEAD_SHAKING_OR_SCRATCHING,
    RedFlag.EAR_ODOR,
    RedFlag.EAR_DISCHARGE,
    RedFlag.EAR_REDNESS,
    RedFlag.EAR_PAIN,
    RedFlag.EAR_BLOODY_OR_PUS_DISCHARGE,
    RedFlag.EAR_FOREIGN_BODY,
}

_OTITIS_INTERNA_FLAGS = {
    RedFlag.EAR_HEAD_TILT,
    RedFlag.EAR_BALANCE_PROBLEMS,
    RedFlag.EAR_RAPID_EYE_MOVEMENTS,
    RedFlag.EAR_SUDDEN_HEARING_LOSS,
    RedFlag.EAR_FACIAL_DROOP,
}

_PINNA_FLAGS = {RedFlag.EAR_FLAP_SWELLING, RedFlag.EAR_SELF_INJURY}

#: Presentations Merck's dermatology pages organise skin disease by. The itch
#: LEVEL is deliberately absent: Merck grades no severity, so the ledger records
#: that the product's severity bands rest on no source, and this oracle labels
#: from the lesion alone.
_SKIN_LESION_FLAGS = {
    RedFlag.SKIN_ITCHING,
    RedFlag.SKIN_REDNESS,
    RedFlag.SKIN_HAIR_LOSS,
    RedFlag.SKIN_RASH_OR_BUMPS,
    RedFlag.SKIN_SCABS_OR_FLAKING,
    RedFlag.SKIN_SWELLING,
    RedFlag.SKIN_LUMP,
    RedFlag.SKIN_NAIL_OR_PAD_CHANGE,
}

_SKIN_INFECTION_FLAGS = {
    RedFlag.SKIN_DISCHARGE_OR_PUS,
    RedFlag.SKIN_ODOR,
    RedFlag.SKIN_OPEN_WOUND,
}

_FRAGILE_AGES = (AgeCategory.BABY, AgeCategory.SENIOR)


@dataclass(frozen=True)
class Label:
    """The level the published evidence supports, and why."""

    level: TriageLevel | str
    findings: tuple[Finding, ...] = ()
    rationale: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_review(self) -> bool:
        return self.level == NEEDS_REVIEW

    @property
    def inferred(self) -> bool:
        """True when EVERY supporting finding needed a step past its source.

        One literally-quoted finding is enough to make the label confirmed; the
        presence of extra, weaker corroboration does not water it down.
        """
        return bool(self.findings) and all(finding.is_inferred for finding in self.findings)

    @property
    def source_urls(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(finding.url for finding in self.findings))


def normalise_species(raw: str | None) -> str | None:
    """Return 'dog', 'cat', None for unknown, or the raw token for anything else."""
    token = (raw or "").strip().casefold()
    if token in ev.UNKNOWN_SPECIES_VALUES:
        return None
    return token


def species_is_supported(raw: str | None) -> bool:
    species = normalise_species(raw)
    return species is None or species in ev.SUPPORTED_SPECIES


def _applies(finding: Finding, species: str | None) -> bool:
    """Can this finding be used for this animal?

    When the species is unknown, only evidence that covers both dogs and cats
    (or all animals) may be used — narrowing to one species would mean guessing
    which animal the owner has.
    """
    if finding.species is None:
        return True
    if species is None:
        return ev.SUPPORTED_SPECIES <= finding.species
    return species in finding.species


def expected_label(intake: SymptomIntake) -> Label:  # noqa: C901 - a decision table
    """The level the evidence supports for this intake, with its justification."""
    species = normalise_species(intake.species)
    flags = set(intake.red_flags)

    # No evidence base covers species other than dogs and cats. Saying anything
    # would be invention; saying "fine" would be dangerous. Neither is a label.
    if species is not None and species not in ev.SUPPORTED_SPECIES:
        # Corrosive ocular exposure is the one finding that explicitly covers
        # all species, so it still produces a label.
        if RedFlag.EYE_CHEMICAL_EXPOSURE in flags:
            return Label(
                TriageLevel.RED,
                (ev.MERCK_CORROSIVE_EYE,),
                "Merck's corrosive-agent page states all species are susceptible and requires "
                "prolonged flushing followed by fluorescein examination.",
            )
        return Label(
            NEEDS_REVIEW,
            (),
            f"No source in the evidence ledger covers {species!r}. A veterinarian must "
            "decide both the expected level and whether the product should answer at all.",
            ("unsupported_species",),
        )

    if intake.concern is Concern.BREED_ONLY and not flags:
        return Label(
            TriageLevel.GREEN,
            (),
            "No health question was asked, so there is no clinical claim to make.",
        )

    hits: list[tuple[TriageLevel, Finding, str]] = []

    def add(level: TriageLevel, finding: Finding, why: str) -> None:
        if _applies(finding, species):
            hits.append((level, finding, why))

    # ---------------------------------------------------------------- RED
    for flag, finding in (
        (RedFlag.TROUBLE_BREATHING, ev.MERCK_LIST[3]),
        (RedFlag.SEVERE_PAIN, ev.MERCK_LIST[1]),
        (RedFlag.UNCONTROLLED_BLEEDING, ev.MERCK_LIST[2]),
        (RedFlag.SUSPECTED_POISONING, ev.MERCK_LIST[0]),
        (RedFlag.EYE_INJURY, ev.MERCK_LIST[4]),
        (RedFlag.LIMB_CANNOT_MOVE, ev.MERCK_LIST[5]),
    ):
        if flag in flags:
            add(TriageLevel.RED, finding, f"Merck lists {flag.value.replace('_', ' ')} as an emergency.")

    for flag, finding in (
        (RedFlag.RAPID_BREATHING_AT_REST, ev.ASPCA_LIST[9]),
        (RedFlag.SEIZURE, ev.ASPCA_LIST[2]),
        (RedFlag.COLLAPSE_OR_UNRESPONSIVE, ev.ASPCA_LIST[1]),
        (RedFlag.PALE_GUMS, ev.ASPCA_LIST[0]),
        (RedFlag.MAJOR_TRAUMA, ev.ASPCA_LIST[4]),
        (RedFlag.CHOKING, ev.ASPCA_LIST[5]),
    ):
        if flag in flags:
            add(TriageLevel.RED, finding, f"ASPCA lists {flag.value.replace('_', ' ')} as an emergency sign.")

    if RedFlag.SUSPECTED_POISONING in flags:
        add(TriageLevel.RED, ev.PET_POISON_HELPLINE, "Pet Poison Helpline says to call immediately.")
        add(TriageLevel.RED, ev.ASPCA_POISON_CONTROL, "ASPCA runs a 24-hour animal poison line.")

    # A sting escalates on the reaction, not on the exposure.
    if RedFlag.INSECT_STING_REACTION in flags and flags & {
        RedFlag.TROUBLE_BREATHING,
        RedFlag.RAPID_BREATHING_AT_REST,
        RedFlag.COLLAPSE_OR_UNRESPONSIVE,
        RedFlag.PALE_GUMS,
        RedFlag.SEIZURE,
        RedFlag.BLOOD_IN_VOMIT_OR_STOOL,
    }:
        add(
            TriageLevel.RED,
            ev.ASPCA_LIST[6],
            "ASPCA names a sting among the causes a pet may need emergency care because of, and "
            "the reported reaction is on its list of emergency signs.",
        )

    if RedFlag.OVERHEATING in flags:
        add(TriageLevel.RED, ev.ASPCA_LIST[8], "ASPCA names heatstroke a life-threatening situation.")
        add(TriageLevel.RED, ev.MERCK_HEATSTROKE, "Merck treats heat stroke as an emergency.")
        add(TriageLevel.RED, ev.CORNELL_HEATSTROKE, "Cornell calls canine heatstroke life-threatening.")

    if RedFlag.EYE_CHEMICAL_EXPOSURE in flags:
        add(TriageLevel.RED, ev.MERCK_CORROSIVE_EYE, "Merck requires flushing then fluorescein examination.")

    for flag, findings in _EYE_URGENT_FLAGS.items():
        if flag in flags:
            for finding in findings:
                add(
                    TriageLevel.RED,
                    finding,
                    f"{flag.value.replace('_', ' ')} is on the urgent-eye list or is a sign of "
                    "acute glaucoma, which Merck calls an ophthalmological emergency.",
                )

    if RedFlag.BLOOD_IN_VOMIT_OR_STOOL in flags:
        add(TriageLevel.RED, ev.MISSOURI_BLOOD, "Missouri lists blood in vomit or stool as immediate.")
    if RedFlag.BLACK_TARRY_STOOL in flags:
        add(TriageLevel.RED, ev.MISSOURI_TARRY, "Missouri lists dark tarry stool as immediate.")

    gi_signs = flags & {RedFlag.VOMITING, RedFlag.DIARRHOEA}
    fragile = intake.has_chronic_illness is True or intake.age_category in _FRAGILE_AGES

    if RedFlag.VOMITING_MANY_TIMES in flags:
        add(
            TriageLevel.RED,
            ev.MISSOURI_VOMITING_OVER_24H,
            "Missouri lists profuse vomiting many times in a day among the situations warranting "
            "more immediate attention.",
        )
    # Duration alone is deliberately absent. "Vomiting for 2-7 days" was read
    # here as Missouri's "attempts to vomit continue for more than 24 hours"
    # until a reviewer separated the two: once a day for three days is not that
    # clause. The frequency answer above is what carries it now.
    if gi_signs and fragile:
        add(
            TriageLevel.RED,
            ev.MISSOURI_FRAGILE,
            "Missouri escalates vomiting or diarrhoea in the very young, very old, or chronically ill.",
        )
    if gi_signs and RedFlag.EXTREME_LETHARGY in flags:
        add(
            TriageLevel.RED,
            ev.MISSOURI_LETHARGY_WITH_GI,
            "Missouri lists extreme lethargy among immediate-attention situations in a GI case.",
        )

    if species == ev.DOG and RedFlag.DIARRHOEA in flags and (
        flags & {RedFlag.NOT_EATING, RedFlag.EXTREME_LETHARGY}
    ):
        add(
            TriageLevel.RED,
            ev.CORNELL_DIARRHOEA_RED_FLAGS,
            "Cornell names stopping eating and lethargy as reasons to seek care with diarrhoea.",
        )

    if RedFlag.BLOATED_ABDOMEN_WITH_RETCHING in flags:
        add(TriageLevel.RED, ev.CORNELL_GDV, "Cornell: GDV needs immediate intervention and is fatal without it.")

    if RedFlag.UNABLE_TO_URINATE in flags:
        add(
            TriageLevel.RED,
            ev.CORNELL_LUTD,
            "Cornell: urethral obstruction is a true medical emergency and any cat suspected of "
            "it must receive immediate veterinary attention.",
        )
        add(TriageLevel.RED, ev.ACVS_OBSTRUCTION, "ACVS: urinary obstruction requires emergency treatment.")

    if RedFlag.NOT_EATING in flags:
        if intake.time_since_eating is TimeSinceEating.OVER_24H:
            add(TriageLevel.RED, ev.CAT_ANOREXIA_24H, "Cornell: 24 hours severely affects a mature cat.")
        if intake.age_category is AgeCategory.BABY and intake.time_since_eating in (
            TimeSinceEating.H12_TO_24H,
            TimeSinceEating.OVER_24H,
        ):
            add(TriageLevel.RED, ev.KITTEN_ANOREXIA_12H, "Cornell: 12 hours can be lethal for a young kitten.")

    # -------------------------------------------------------------- AMBER
    eye_context = intake.concern is Concern.EYES or intake.body_area is BodyArea.EYE
    if eye_context:
        add(TriageLevel.AMBER, ev.VCA_EYE_NONSPECIFIC, "VCA: eye signs may indicate infection or injury.")
        add(TriageLevel.AMBER, ev.MERCK_UVEITIS, "Merck requires fluorescein staining to evaluate an eye.")

    if flags & _OTITIS_EXTERNA_FLAGS:
        add(TriageLevel.AMBER, ev.MERCK_OTITIS_EXTERNA, "Merck: otitis externa needs otoscopy and cytology.")
    if flags & _OTITIS_INTERNA_FLAGS:
        add(
            TriageLevel.AMBER,
            ev.MERCK_OTITIS_MEDIA_INTERNA,
            "Merck describes these as signs of otitis media/interna needing examination. The page "
            "does NOT call them an emergency.",
        )
    if flags & _PINNA_FLAGS:
        add(
            TriageLevel.AMBER,
            ev.MERCK_AURICULAR_HEMATOMA,
            "Merck describes ear-flap swelling and scratching trauma, with no urgency language.",
        )

    ear_context = intake.concern is Concern.EARS or intake.body_area is BodyArea.EAR
    if ear_context and (intake.duration in _MULTI_DAY or flags & _OTITIS_EXTERNA_FLAGS):
        add(
            TriageLevel.AMBER,
            ev.MERCK_OTITIS_EXTERNA,
            "A persistent ear problem needs the otoscopic and cytological work-up Merck describes.",
        )

    if flags & _SKIN_LESION_FLAGS:
        add(
            TriageLevel.AMBER,
            ev.MERCK_DERM_PROBLEMS,
            "Merck organises skin disease by presentation and states that accurate diagnosis "
            "requires a careful history and physical examination.",
        )
    if RedFlag.SKIN_ITCHING in flags:
        add(
            TriageLevel.AMBER,
            ev.MERCK_PRURITUS,
            "Merck: pruritus is a clinical sign rather than a diagnosis, and identifying its "
            "cause requires a methodical workup.",
        )
    if flags & _SKIN_INFECTION_FLAGS:
        add(
            TriageLevel.AMBER,
            ev.MERCK_PYODERMA,
            "Merck gives odor, exudation of pus and ulceration as pyoderma signs, diagnosed by "
            "cytology and culture rather than by appearance.",
        )
    if RedFlag.SKIN_CONTAGION in flags:
        add(
            TriageLevel.AMBER,
            ev.MERCK_DERMATOPHYTOSIS,
            "Merck: dermatophytosis is zoonotic and spread by direct contact, and confirming it "
            "takes several tests.",
        )

    if RedFlag.DRINKING_MUCH_MORE in flags:
        add(TriageLevel.AMBER, ev.VCA_THIRST, "VCA associates polydipsia with disease needing work-up.")

    if RedFlag.NOT_EATING in flags:
        if species == ev.DOG or species is None:
            add(TriageLevel.AMBER, ev.VCA_ANOREXIA_DOGS, "VCA: involve the veterinarian early when a dog stops eating.")
        if species == ev.CAT:
            add(
                TriageLevel.AMBER,
                ev.CAT_ANOREXIA_UNDER_24H,
                "Cornell treats feline anorexia as a sign of disease; below 24 hours it still needs a vet.",
            )

    if RedFlag.EXTREME_LETHARGY in flags and not gi_signs:
        add(TriageLevel.AMBER, ev.MISSOURI_LETHARGY_ALONE, "No source covers isolated lethargy; cautious floor.")

    if RedFlag.DIARRHOEA in flags and intake.duration in _MULTI_DAY:
        add(TriageLevel.AMBER, ev.CORNELL_DIARRHOEA_TWO_DAYS, "Cornell: loose stool beyond two days, call the vet.")

    # VCA's page is about LIMPING, so this proxy asks whether the owner has
    # described a leg problem. "Legs or paws" alone used to be read as one,
    # which meant an itchy paw was labelled from a lameness page. The form now
    # separates the two — a paw problem is routed to skin or to limping before
    # these questions are asked — so a skin case on a paw is not a lameness
    # case, and nothing in this ledger speaks to it.
    mobility_context = intake.concern is Concern.MOBILITY or (
        intake.body_area is BodyArea.LEGS_OR_PAWS
        and intake.concern is not Concern.SKIN_OR_COAT
    )
    if mobility_context and intake.duration in _MULTI_DAY:
        add(TriageLevel.AMBER, ev.VCA_LIMPING_OVER_24H, "VCA: lameness beyond 24 hours needs veterinary care.")
    if intake.weight_bearing is False and intake.duration in _MULTI_DAY:
        add(
            TriageLevel.AMBER,
            ev.VCA_LIMPING_NON_WEIGHT_BEARING,
            "VCA: most dogs will not walk on a broken leg, torn ligament or dislocated joint.",
        )

    # -------------------------------------------------------------- GREEN
    if not hits:
        quiet_adult = not fragile and intake.age_category not in _FRAGILE_AGES
        other_signs = flags - {RedFlag.VOMITING, RedFlag.DIARRHOEA}
        if intake.duration is Duration.TODAY and quiet_adult and not other_signs:
            if RedFlag.DIARRHOEA in flags:
                add(
                    TriageLevel.GREEN,
                    ev.CORNELL_DIARRHOEA_SHORT,
                    "Cornell's own two-day threshold implies watching an uncomplicated first day.",
                )
            if RedFlag.VOMITING in flags:
                add(
                    TriageLevel.GREEN,
                    ev.MISSOURI_SINGLE_EPISODE,
                    "Missouri's escalation list implies a well adult with brief vomiting is not in it.",
                )
        if (
            not flags
            and mobility_context
            and intake.duration is Duration.TODAY
            and intake.weight_bearing is not False
            and quiet_adult
        ):
            add(
                TriageLevel.GREEN,
                ev.VCA_LIMPING_SHORT,
                "VCA's 24-hour threshold implies a well dog limping today is watched first.",
            )

    if not hits:
        return Label(
            NEEDS_REVIEW,
            (),
            "No source in the evidence ledger addresses this combination. The system must not "
            "claim a level here, in either direction.",
            ("no_applicable_evidence",),
        )

    best = max(hits, key=lambda hit: SEVERITY[hit[0]])[0]
    supporting = tuple(hit for hit in hits if hit[0] == best)
    return Label(
        level=best,
        findings=tuple(dict.fromkeys(hit[1] for hit in supporting)),
        rationale=" ".join(dict.fromkeys(hit[2] for hit in supporting)),
    )

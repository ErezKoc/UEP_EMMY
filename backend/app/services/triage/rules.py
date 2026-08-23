"""The clinical rule table.

This file is the entire clinical logic of the product, kept in one readable
place so a veterinarian can review it without reading any other code.
`python -m app.services.triage.report` prints it as plain English.

Every rule below traces to a page that was fetched and read on the date in
`sources.py`. Rules we could not source are not here — they are parked in
`candidates.py`, are not loaded by the engine, and cannot affect any result.

STATUS: retrieved, not yet verified. Nobody on the team has independently
opened these sources and signed them off, so `TRIAGE_REQUIRE_VERIFIED_RULES`
must stay false until they do.

Two things the sources make clear, and which the table reflects:
* The emergency list is well agreed between publishers.
* The graded middle is far thinner evidence, so its rules are deliberately
  cautious and any timing extrapolation is marked for veterinary review.
"""

from app.models.animal import AgeCategory
from app.schemas.triage import (
    BodyArea,
    Concern,
    Duration,
    ItchLevel,
    RedFlag,
    TimeSinceEating,
    DiagnosticEvidence,
    ExtrapolationKind,
    TriageLevel,
    Trend,
    UrgencyEvidence,
)
import enum
from dataclasses import dataclass

from app.services.triage.citations import Citation
from app.services.triage.conditions import (
    AgeIn,
    All,
    Any_,
    BodyAreaIn,
    CannotBearWeight,
    ConcernIs,
    DurationIn,
    HasRedFlag,
    IsFragilePatient,
    ItchLevelIn,
    Not,
    NotEatingFor,
    SpeciesIs,
    TrendIs,
)
from app.services.triage.rule import Rule
from app.services.triage.sources import (
    ACVS_URINARY_OBSTRUCTION,
    ACVS_URINARY_OBSTRUCTION_DOGS,
    ALL_SPECIES,
    ASPCA_EMERGENCY,
    ASPCA_POISON_CONTROL,
    CAT_ONLY,
    CORNELL_ANOREXIA,
    CORNELL_DIARRHOEA,
    CORNELL_FELINE_DIARRHOEA,
    DOG_AND_CAT,
    CORNELL_GDV,
    CORNELL_LUTD,
    DOG_ONLY,
    MERCK_ACUTE_GLAUCOMA,
    MERCK_ANTERIOR_UVEITIS,
    MERCK_AURICULAR_HEMATOMA,
    MERCK_CORROSIVE_EYE_EXPOSURE,
    MERCK_DERM_PROBLEMS,
    MERCK_DERMATOPHYTOSIS,
    MERCK_EMERGENCY,
    MERCK_EYE_ANTI_INFLAMMATORY,
    MERCK_OTITIS_EXTERNA,
    MERCK_OTITIS_MEDIA_INTERNA,
    MERCK_PRURITUS,
    MERCK_STINGS,
    MERCK_TRAUMA,
    MERCK_URETHRAL_OBSTRUCTION,
    MERCK_PYODERMA,
    MERCK_SKIN_DIAGNOSIS,
    MISSOURI_VOMITING,
    PET_POISON_HELPLINE,
    Source,
    VCA_ANOREXIA_DOGS,
    VCA_EYE_ISSUES,
    VCA_LIMPING,
    VCA_LIMPING_CATS,
    VCA_THIRST,
)


def _cite(source: Source, supports: str) -> Citation:
    return Citation(
        source=source.name,
        url=source.url,
        accessed=source.accessed,
        supports=supports,
        species=source.species,
    )


_EYE_URGENT_CARE_SIGNS = (
    "The eye is kept closed, your pet is squinting, or the eye appears painful.",
    "The eye becomes cloudy or develops a blue or white area.",
    "The pupils become unequal, or your pet appears unable to see normally.",
    "There is marked swelling, bulging, or rapid worsening.",
    "Discharge becomes yellow-green or bloody.",
    "There may have been an eye injury or chemical exposure.",
)

_EYE_CARE_INSTRUCTIONS = (
    "Prevent rubbing or scratching; an Elizabethan collar may help if your pet tolerates one.",
    "Do not use human eye drops, leftover prescriptions, or another pet's medicine unless a veterinarian specifically instructs you to.",
    "Steroid-containing eye medicine can delay healing or worsen complications when a corneal ulcer is present.",
    "Online veterinary advice can supplement an examination, but it should not delay in-person care.",
)

# One string used to serve both eye rules, and it opened "Redness and watering
# are not specific to one condition" — VCA's signs, not the owner's. An owner
# who picked "Eyes" and ticked nothing was told about redness and watering they
# had never reported, and one who ticked "cloudy eye" was told the same. The
# two rules now say different things, and neither names a sign the owner did
# not give us.
#
# `{reported}` is filled from what was actually ticked; this rule's condition
# guarantees at least one, so the neutral fallback never appears here.
_EYE_SIGNS_REPORTED_REASON = (
    "The signs you reported — {reported} — are not specific to one condition. A photo cannot rule "
    "out corneal damage, inflammation inside the eye, or glaucoma; a veterinarian may need "
    "fluorescein staining and eye-pressure testing."
)

# For a new eye concern with none of the signs above ticked. It names no sign
# at all, because we have not been told one.
_EYE_CONCERN_REASON = (
    "A new eye problem is not specific to one condition. A photo cannot rule out corneal damage, "
    "inflammation inside the eye, or glaucoma; a veterinarian may need fluorescein staining and "
    "eye-pressure testing."
)

_EAR_CONCERN = Any_((ConcernIs(Concern.EARS), BodyAreaIn((BodyArea.EAR,))))

_EAR_URGENT_CARE_SIGNS = (
    "Your pet develops a head tilt, stumbling, circling, or loss of balance.",
    "You notice rapid side-to-side or rotary eye movements.",
    "There is sudden hearing loss or one side of the face begins to droop.",
    "The ear appears severely painful or your pet is in marked distress.",
    "Discharge becomes bloody or pus-like.",
    "The ear flap develops major or fluid-filled swelling.",
    "Scratching or head shaking is causing bleeding or another injury.",
    "A grass seed or another object may be lodged in the ear.",
)

_EAR_CARE_INSTRUCTIONS = (
    "Keep the ear dry and prevent excessive scratching or head shaking if possible.",
    "Do not put cotton buds or other objects into the ear canal.",
    "Do not pour household products into the ear or use leftover or over-the-counter ear medicine unless a veterinarian advises it.",
    "Some ear treatments can cause harm when the eardrum is damaged, so medication choice should follow an examination.",
    "Online veterinary advice can supplement an examination, but it should not delay in-person care.",
)

_EAR_REASON = (
    "Because this ear problem is persistent or worsening, it should be examined. A photo cannot "
    "inspect the ear canal or eardrum; a veterinarian may need an otoscope and a microscope test "
    "to identify the cause."
)

# --------------------------------------------------------------------------
# Skin and coat.
#
# The four Merck dermatology pages behind this section agree on two things and
# are silent on a third. They agree that a skin case is defined by its lesions
# — pruritus, alopecia, scaling and crusting, nodules, odour, erosions and
# ulcerations, nonhealing wounds — and that naming the cause takes a history,
# an examination and tests. They say nothing whatsoever about how quickly an
# animal should be seen. So every rule here recommends an examination and none
# of them states a timeframe.
#
# This is also why "skin or coat" on its own fires nothing: it is the owner's
# word for a category, not a description of the skin. The questions that follow
# it in the form are what these rules actually read.
# --------------------------------------------------------------------------

_SKIN_INFECTION_FLAGS = (
    RedFlag.SKIN_DISCHARGE_OR_PUS,
    RedFlag.SKIN_ODOR,
    RedFlag.SKIN_OPEN_WOUND,
)

_SKIN_LESION_FLAGS = (
    RedFlag.SKIN_ITCHING,
    RedFlag.SKIN_REDNESS,
    RedFlag.SKIN_HAIR_LOSS,
    RedFlag.SKIN_RASH_OR_BUMPS,
    RedFlag.SKIN_SCABS_OR_FLAKING,
    RedFlag.SKIN_SWELLING,
    RedFlag.SKIN_LUMP,
    RedFlag.SKIN_NAIL_OR_PAD_CHANGE,
)

# The headline asserts the proposition the sources actually establish — that
# the cause of a skin problem is worked out by examining it — rather than the
# one they do not: that a patch this mild has to be seen rather than watched.
# "Veterinary examination recommended" sat above a confidence panel admitting
# our sources set no such bar, and an owner reads the headline first.
#
# "An examination is how the cause gets identified" then overstated it in the
# other direction, and "Identifying the cause takes an examination" still read
# as though the examination were the whole of it. Merck's account is that a
# definitive diagnosis takes the history, the physical examination AND
# appropriate tests — scrapings, hair examination, cytology, culture — because
# many skin diseases look alike. "Part of" is the claim that survives all of
# that, and it is the same claim the certainty panel below makes in its own
# words, which is what an owner should find when they look for the evidence.
_SKIN_HEADLINE = "A veterinary examination is part of identifying the cause"

# "arranging one" pointed back at a noun three words into the previous
# sentence, on a card where the two are rendered in different sections and the
# owner may well read this one first.
_SKIN_ADVICE = (
    "We suggest contacting your veterinary clinic and arranging an examination. Our sources "
    "describe how a skin problem is diagnosed; none of them says whether something this mild "
    "needs an appointment or could be watched first, so the suggestion is our cautious default "
    "rather than theirs."
)

# No skin-specific "when to get urgent help" list. There was one, and every line
# of it was invented: plausible-sounding thresholds ("the area is oozing or
# spreading quickly") that no page we hold states as a reason to be seen faster.
# A source saying odour accompanies infection establishes that odour matters
# diagnostically; it does not establish an urgency threshold, and the difference
# is the whole point of this system. Skin results now fall back to the general
# emergency list in `GENERAL_EMERGENCY_SIGNS`, which is sourced independently of
# the skin problem and true regardless of it.

# Explanatory, not instructions — which is why they are `what_to_expect` and not
# `care_instructions`. Two sentences about how skin disease is diagnosed were
# appearing under the heading "Care until the appointment", where they told the
# owner nothing about caring for the animal.
#
# The second one no longer predicts what this veterinarian will do at this
# appointment ("expect the appointment to involve tests"). Merck describes
# scrapings and trichograms as part of the basic database for skin disease; it
# does not say what any particular clinician will order, and neither the
# professional nor the pet-owner page states on what basis tests are chosen.
_SKIN_WHAT_TO_EXPECT = (
    "Many skin diseases look alike. A diagnosis is reached by including or excluding possible"
    " causes and by seeing how the skin responds to treatment, so appearance alone cannot"
    " reliably identify the cause.",
    "Merck describes skin scrapings and examination of hair among the diagnostic methods used for"
    " skin disease, alongside the history and the physical examination.",
)
# --------------------------------------------------------------------------
# Emergency rules — any one of these makes the assessment RED on its own.
# --------------------------------------------------------------------------

EMERGENCY_RULES: tuple[Rule, ...] = (
    # ----------------------------------------------------------------------
    # Breathing, as two questions rather than one.
    #
    # There was a single option, "breathing hard or fast", firing one
    # unconditional emergency rule that cited Merck's "trouble breathing" and
    # the ASPCA's "rapid breathing" together. Those are two signs, and only one
    # of them survives without qualification: a dog that has just run, or is
    # hot, or is excited, breathes hard and fast and is not an emergency. The
    # option collected both readings and could not tell them apart, so a
    # panting-after-exercise report and a dog in respiratory distress arrived
    # here as the same answer.
    #
    # Both halves are still unconditionally red. What changed is what the owner
    # is asked, and therefore which reports reach the rule at all. That is a
    # deliberate narrowing of intake, flagged below for the reviewer, and it
    # takes nothing away from anyone who reports either sign.
    # ----------------------------------------------------------------------
    Rule(
        id="trouble_breathing",
        condition=HasRedFlag(RedFlag.TROUBLE_BREATHING),
        # Merck's alone now. The ASPCA's "rapid breathing" belongs to the rule
        # below, and citing both pages here implied each supported the whole of
        # what the old combined option collected.
        message=(
            "Breathing that looks difficult or laboured is an emergency warning sign. Merck lists "
            "trouble breathing among emergencies needing immediate care."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(MERCK_EMERGENCY, "lists trouble breathing among emergencies needing immediate care"),
        ),
    ),
    Rule(
        id="rapid_breathing_at_rest",
        condition=HasRedFlag(RedFlag.RAPID_BREATHING_AT_REST),
        message=(
            "Breathing unusually fast while resting is an emergency warning sign. The ASPCA lists "
            "rapid breathing among the signs a pet needs emergency care."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(ASPCA_EMERGENCY, "lists rapid breathing among signs a pet needs emergency care"),
        ),
        reviewer_note=(
            "NARROWER THAN ITS SOURCE, DELIBERATELY — and note which half of that is ours. The"
            " positive claim is the ASPCA's: it lists rapid breathing among the signs a pet needs"
            " emergency care, and rapid breathing at rest is a subset of rapid breathing, so"
            " nothing here reaches past the page. What is our judgement is the decision NOT to"
            " escalate every other instance of rapid breathing, because the unqualified question"
            " cannot distinguish a dog in distress from a dog that has just been running."
            " Cornell's canine respiratory-distress material is reported to say healthy dogs pant"
            " heavily with stress, excitement, exertion or cooling; nobody here has read it (see"
            " candidate `respiratory_distress_composite`). Please confirm 'while resting' is the"
            " right qualifier to put in front of an owner."
        ),
    ),
    Rule(
        id="severe_pain",
        condition=HasRedFlag(RedFlag.SEVERE_PAIN),
        message="Signs of severe pain need emergency veterinary care.",
        level_override=TriageLevel.RED,
        citations=(_cite(MERCK_EMERGENCY, "lists severe pain among emergencies needing immediate care"),),
    ),
    Rule(
        id="uncontrolled_bleeding",
        condition=HasRedFlag(RedFlag.UNCONTROLLED_BLEEDING),
        message="Severe or uncontrolled bleeding needs emergency veterinary care.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(MERCK_EMERGENCY, "lists severe or uncontrolled bleeding as an emergency"),
            _cite(ASPCA_EMERGENCY, "lists excessive bleeding as an emergency sign"),
        ),
    ),
    Rule(
        id="suspected_poisoning",
        condition=HasRedFlag(RedFlag.SUSPECTED_POISONING),
        message="Suspected poisoning needs immediate advice, even if your pet still seems well.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(MERCK_EMERGENCY, "lists poisoning among emergencies needing immediate care"),
            _cite(
                PET_POISON_HELPLINE,
                "states that if you think your dog or cat has been poisoned you should call your"
                " veterinarian or the helpline immediately, and that the sooner treatment starts the"
                " better the outcome",
            ),
            _cite(
                ASPCA_POISON_CONTROL,
                "gives (888) 426-4435 as a 24-hour animal poison control line staffed by veterinary"
                " toxicology specialists",
            ),
        ),
        # Poisoning is the one emergency where a phone call can start treatment
        # before the animal arrives anywhere, so the numbers belong in the answer.
        care_instructions=(
            "Call your veterinary practice now. If you cannot reach them, call a 24-hour animal"
            " poison control service: ASPCA Animal Poison Control Center on (888) 426-4435, or Pet"
            " Poison Helpline on (855) 764-7661. A consultation fee may apply.",
            "Have ready what your pet ate, roughly how much, and when. Take the packaging or a"
            " sample of the substance with you if you go to a clinic.",
        ),
        reviewer_note=(
            "Both hotlines are US services. Ask the reviewer which number to show outside the US"
            " before this ships to users in other countries."
        ),
    ),
    Rule(
        id="eye_injury",
        condition=HasRedFlag(RedFlag.EYE_INJURY),
        message="An injury to the eye needs emergency veterinary care.",
        level_override=TriageLevel.RED,
        citations=(_cite(MERCK_EMERGENCY, "lists eye injuries among emergencies needing immediate care"),),
        headline="Emergency eye examination recommended",
        advice=(
            "Call a veterinary clinic now. Use an emergency service if your regular clinic cannot "
            "see your pet promptly."
        ),
        urgent_care_signs=_EYE_URGENT_CARE_SIGNS,
        care_instructions=_EYE_CARE_INSTRUCTIONS,
        reviewer_note="Merck lists eye INJURIES. Non-injury eye signs are handled by the weighted rule.",
    ),
    Rule(
        id="eye_emergency_signs",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        # Deliberately NOT gated on the concern or body area the owner picked.
        # It used to be, and an owner who filed "one pupil is much bigger and
        # she's walking into things" under "other" got no rules and a green
        # verdict. The evidence attaches to the sign, not to how the owner
        # categorised it — and the owner least able to categorise correctly is
        # exactly the one this product exists for.
        condition=Any_(
            (
                HasRedFlag(RedFlag.EYE_PAIN_OR_CLOSED),
                HasRedFlag(RedFlag.EYE_CLOUDY_OR_BLUE),
                HasRedFlag(RedFlag.UNEQUAL_PUPILS_OR_VISION_CHANGE),
                HasRedFlag(RedFlag.EYE_BULGING_OR_SEVERE_SWELLING),
                HasRedFlag(RedFlag.EYE_DISCHARGE_YELLOW_GREEN_OR_BLOODY),
            )
        ),
        message=_EYE_SIGNS_REPORTED_REASON,
        reported_signs=(
            RedFlag.EYE_PAIN_OR_CLOSED,
            RedFlag.EYE_CLOUDY_OR_BLUE,
            RedFlag.UNEQUAL_PUPILS_OR_VISION_CHANGE,
            RedFlag.EYE_BULGING_OR_SEVERE_SWELLING,
            RedFlag.EYE_DISCHARGE_YELLOW_GREEN_OR_BLOODY,
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                VCA_EYE_ISSUES,
                "recommends urgent care for squinting or a closed eye, cloudy eyes, bulging, marked"
                " redness or swelling, watery eyes with red skin, and abnormal discharge",
            ),
            _cite(
                MERCK_ACUTE_GLAUCOMA,
                "describes acute glaucoma as an ophthalmic emergency and identifies pain, corneal"
                " clouding, pupil changes and vision loss as signs requiring pressure measurement",
            ),
        ),
        headline="Same-day urgent eye examination recommended",
        advice=(
            "Contact a veterinary clinic now for a same-day assessment. Use an emergency service if "
            "your clinic is unavailable, the signs are severe, or they are worsening quickly."
        ),
        urgent_care_signs=_EYE_URGENT_CARE_SIGNS,
        care_instructions=_EYE_CARE_INSTRUCTIONS,
        reviewer_note=(
            "A worsening trend on its own no longer reaches this rule; it is handled by the graded"
            " eye pathway. VCA's page is a service landing page rather than a clinical article and"
            " names no species — please confirm both the sign list and that scope."
        ),
    ),
    Rule(
        id="eye_chemical_exposure",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        condition=HasRedFlag(RedFlag.EYE_CHEMICAL_EXPOSURE),
        message=(
            "A chemical splash in the eye needs prolonged flushing followed by an examination that "
            "can check the surface of the eye for damage."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                MERCK_CORROSIVE_EYE_EXPOSURE,
                "states that all species are susceptible, and that eyes should be flushed for a"
                " minimum of 20 minutes and the cornea then stained with fluorescein to detect"
                " corneal injury",
            ),
        ),
        # The cited page states its claim for every species, so this is the one
        # rule in the table that reaches an animal we hold no other evidence for.
        applies_to_species=ALL_SPECIES,
        headline="Emergency eye examination recommended",
        advice=(
            "Contact a veterinary clinic now. Use an emergency service if your regular clinic "
            "cannot see your pet promptly."
        ),
        urgent_care_signs=_EYE_URGENT_CARE_SIGNS,
        care_instructions=(
            "Flush the eye with clean lukewarm water or saline for at least 20 minutes if your pet"
            " will tolerate it, then have the eye examined.",
            *_EYE_CARE_INSTRUCTIONS,
        ),
    ),
    Rule(
        id="limb_cannot_move",
        condition=HasRedFlag(RedFlag.LIMB_CANNOT_MOVE),
        message="A suspected broken bone, or a limb that cannot move, needs emergency care.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(MERCK_EMERGENCY, "lists suspected broken bones or a limb that cannot move as an emergency"),
        ),
    ),
    Rule(
        id="seizure",
        condition=HasRedFlag(RedFlag.SEIZURE),
        message="A seizure needs emergency veterinary care.",
        level_override=TriageLevel.RED,
        citations=(_cite(ASPCA_EMERGENCY, "lists seizures among signs a pet needs emergency care"),),
    ),
    Rule(
        id="collapse_or_unresponsive",
        condition=HasRedFlag(RedFlag.COLLAPSE_OR_UNRESPONSIVE),
        message="Collapse, inability to stand, or unresponsiveness needs emergency care.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                ASPCA_EMERGENCY,
                "lists difficulty standing, apparent paralysis and loss of consciousness as emergency signs",
            ),
        ),
    ),
    Rule(
        id="pale_gums",
        condition=HasRedFlag(RedFlag.PALE_GUMS),
        message="Pale gums can indicate poor circulation and needs emergency assessment.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(ASPCA_EMERGENCY, "lists pale gums as a sign a pet may need emergency care"),
        ),
    ),
    Rule(
        id="unable_to_urinate",
        condition=HasRedFlag(RedFlag.UNABLE_TO_URINATE),
        # Two sentences, in Cornell's own order: the sign is a possible sign of
        # obstruction, and a SUSPECTED obstruction is what needs immediate
        # attention. "which is an emergency in any cat" compressed those into
        # one clause that can be read as though the obstruction were already
        # established — this rule fires on straining, and straining has many
        # causes. The urgency does not depend on which one it is.
        message=(
            "Straining to urinate while producing little or nothing can be a sign of urethral "
            "obstruction. A suspected obstruction requires immediate veterinary attention."
        ),
        level_override=TriageLevel.RED,
        citations=(
            # Cornell first, deliberately: it covers cats, while the ACVS page is
            # about male cats and the form never asks the cat's sex. Citing the
            # male-only page alone left the rule's applicability resting on
            # something the owner was never asked.
            _cite(
                CORNELL_LUTD,
                "states that a cat with a urethral obstruction may strain to urinate, make"
                " frequent attempts, and produce little if any urine; that urethral obstruction"
                " is a true medical emergency and any cat suspected of it must receive immediate"
                " veterinary attention; and that male and neutered male cats are at greater risk"
                " than females rather than being the only cats affected",
            ),
            _cite(
                ACVS_URINARY_OBSTRUCTION,
                "states urinary obstruction requires emergency treatment and can be fatal in 3-6 days;"
                " affected cats strain in the litter box without producing urine",
            ),
        ),
        applies_to_species=CAT_ONLY,
        reviewer_note=(
            "The cat half of a pair. Both this rule and `dog_unable_to_urinate` fire on the same"
            " sign and reach the same level; they are separate because each rests on evidence for"
            " its own species, and the type refuses to let one page's species scope be stretched"
            " over the other. Please review them together."
        ),
    ),
    Rule(
        # The rule that does not need the species answered. Merck states the
        # claim for small animals generally, so this one is not narrowed and
        # reaches an owner who never told us which animal it is — the case the
        # two species rules below cannot cover, and the one the engine used to
        # abstain on. The species rules stay because each carries the better
        # evidence for its own animal; a reviewer should see all three.
        id="unable_to_urinate_either_species",
        condition=HasRedFlag(RedFlag.UNABLE_TO_URINATE),
        # Worded differently from the two species rules on purpose. All three
        # can fire for the same animal, and an owner should not read the same
        # sentence twice; this line carries what is particular to this rule,
        # which is that the emergency is not specific to one species.
        message=(
            "Blocked urine flow is treated as an emergency in dogs and cats alike, and can become "
            "life-threatening within a day or two."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                MERCK_URETHRAL_OBSTRUCTION,
                "calls urethral obstruction an emergency condition in small animals, covering dogs"
                " and cats rather than one of them, and states that complete obstruction causes"
                " uraemia within 36-48 hours and death within about 72",
            ),
        ),
        reviewer_note=(
            "WHY THREE RULES FOR ONE SIGN. Each rests only on evidence for the animals it serves,"
            " because the type refuses to stretch a species-bound page over another species. This"
            " one is the general claim, and it is what answers an owner who did not say whether"
            " the animal is a dog or a cat. If you would rather the unidentified-species case go"
            " back to an abstention, this is the rule to remove."
        ),
    ),
    Rule(
        id="dog_unable_to_urinate",
        condition=All((SpeciesIs("dog"), HasRedFlag(RedFlag.UNABLE_TO_URINATE))),
        # Deliberately the same two sentences as the feline rule, because the
        # claim is the same one: the sign suggests obstruction, and a SUSPECTED
        # obstruction is what needs immediate attention. The rule fires on
        # straining, which has other causes; the urgency does not depend on
        # which cause it turns out to be.
        message=(
            "Straining to urinate while producing little or nothing can be a sign of urethral "
            "obstruction. A suspected obstruction requires immediate veterinary attention."
        ),
        level_override=TriageLevel.RED,
        citations=(
            # ACVS first: it is the page written about dogs, and it states the
            # urgency in the form an owner needs it.
            _cite(
                ACVS_URINARY_OBSTRUCTION_DOGS,
                "states that a pet unable to urinate should be seen by a veterinarian immediately,"
                " that a dog whose urethra is completely blocked will strain without producing any"
                " urine, and that dogs with total urethral obstruction die within days if it is"
                " not relieved",
            ),
            _cite(
                MERCK_URETHRAL_OBSTRUCTION,
                "calls urethral obstruction an emergency condition in small animals, describes"
                " frequent nonproductive attempts to urinate among its signs, and states that"
                " complete obstruction causes uraemia within 36-48 hours and death within about"
                " 72",
            ),
        ),
        applies_to_species=DOG_ONLY,
        reviewer_note=(
            "NEW, AND THE GAP IT CLOSES WAS OURS. Until this rule a dog reported as straining and"
            " producing nothing matched nothing at all and received our abstention — never called"
            " minor, but given no urgency either. The rule was parked as candidate"
            " `urinary_obstruction_outside_cats` on the grounds that we held no non-feline source;"
            " both pages cited here were public the whole time and simply had not been opened."
            " Please confirm the trigger for dogs and whether the wording should differ from the"
            " feline rule. Note what the form does NOT ask: neither sex nor whether the animal is"
            " straining to urinate or to defecate. Merck records that owners mistake obstruction"
            " for constipation, which is an argument for keeping the sign broad, but it is your"
            " call whether the question needs splitting."
        ),
    ),
    Rule(
        id="bloated_abdomen_with_retching",
        condition=HasRedFlag(RedFlag.BLOATED_ABDOMEN_WITH_RETCHING),
        message="A swollen abdomen with unproductive retching is treated as an emergency.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                CORNELL_GDV,
                "states GDV requires immediate medical and surgical intervention and is fatal without it;"
                " lists non-productive retching and a bloated abdomen among its signs",
            ),
        ),
        applies_to_species=DOG_ONLY,
    ),
    Rule(
        id="blood_in_vomit_or_stool",
        condition=HasRedFlag(RedFlag.BLOOD_IN_VOMIT_OR_STOOL),
        message="Blood in vomit, or bloody or tarry stool, needs prompt veterinary attention.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                MISSOURI_VOMITING,
                "lists blood or coffee-grounds material in vomit, and bloody or dark tarry stool,"
                " among situations warranting immediate attention",
            ),
        ),
        reviewer_note=(
            "ADJUDICATE THE EXACT PROPOSITION, which is broader than the page it cites: does ANY"
            " owner-reported blood in vomit or stool — any amount, any frequency, any colour, no"
            " accompanying signs, either species — belong in the emergency branch? Missouri lists"
            " situations; this rule reads any report of the sign. 'Significant GI bleeding can be"
            " an emergency' and 'any blood is an emergency' are different claims and we are"
            " asserting the second. Deliberately left broad in the meantime, because an owner"
            " cannot reliably judge amount, and over-triage here is the cost we said we would"
            " accept — but it is our call, not the source's. Recorded as"
            " candidate `gi_blood_emergency_breadth`."
        ),
    ),
    Rule(
        # The feline counterpart of `dog_not_eating`, and it should always have
        # existed. A cat that had not eaten for under 24 hours matched nothing
        # and was told "nothing in our evidence library matched", while a dog in
        # the same state got an amber on VCA. The gap was in the rule table, not
        # in the library: Cornell's page states the claim without conditioning
        # it on any duration, which is why the two rules below can keep their
        # thresholds and this one carries no threshold at all.
        id="cat_not_eating",
        condition=All((SpeciesIs("cat"), HasRedFlag(RedFlag.NOT_EATING))),
        message="A cat going off its food is worth having checked.",
        weight=3,
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        citations=(
            _cite(
                CORNELL_ANOREXIA,
                "states that a cat which is not eating deserves a full veterinary workup, and"
                " encourages owners to consult a veterinarian immediately on noticing any signs"
                " of feline anorexia, neither of which it conditions on how long the cat has"
                " gone without food",
            ),
        ),
        applies_to_species=CAT_ONLY,
        reviewer_note=(
            "GRADED BELOW WHAT THE PAGE SAYS, DELIBERATELY. Cornell's word is 'immediately'."
            " This rule is amber, not red, because the red rules on either side of it are the"
            " ones with a duration behind them — 24 hours for a mature cat, 12 for a kitten —"
            " and making every skipped meal an emergency would empty those thresholds of"
            " meaning. Amber is our reading of 'consult a veterinarian', not Cornell's grading;"
            " please confirm it, and say whether a cat off its food for under 24 hours should"
            " instead be same-day."
        ),
    ),
    Rule(
        id="cat_not_eating_24h",
        condition=All((SpeciesIs("cat"), HasRedFlag(RedFlag.NOT_EATING), NotEatingFor((TimeSinceEating.OVER_24H,)))),
        message="A cat that has not eaten for a day needs prompt veterinary attention.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                CORNELL_ANOREXIA,
                "states appetite loss can severely affect a mature cat's health if it persists"
                " for as little as 24 hours",
            ),
        ),
        applies_to_species=CAT_ONLY,
    ),
    Rule(
        id="kitten_not_eating_12h",
        condition=All(
            (
                SpeciesIs("cat"),
                AgeIn((AgeCategory.BABY,)),
                HasRedFlag(RedFlag.NOT_EATING),
                NotEatingFor((TimeSinceEating.H12_TO_24H, TimeSinceEating.OVER_24H)),
            )
        ),
        message="A kitten that has not eaten for half a day needs urgent veterinary attention.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                CORNELL_ANOREXIA,
                "states that for a kitten younger than six weeks, avoiding food for just 12 hours"
                " can pose a lethal threat",
            ),
        ),
        applies_to_species=CAT_ONLY,
        reviewer_note="Our 'baby' age band is a coarse proxy for Cornell's 'younger than six weeks'.",
    ),
    Rule(
        id="vomiting_or_diarrhoea_in_fragile_animal",
        condition=All(
            (
                Any_((HasRedFlag(RedFlag.VOMITING), HasRedFlag(RedFlag.DIARRHOEA))),
                IsFragilePatient(),
            )
        ),
        message="Vomiting or diarrhoea in a very young, elderly, or chronically ill pet needs prompt attention.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                MISSOURI_VOMITING,
                "states very young, very old, or chronically ill animals warrant immediate attention"
                " even after only a few episodes",
            ),
        ),
    ),
    Rule(
        id="profuse_vomiting_in_a_day",
        condition=HasRedFlag(RedFlag.VOMITING_MANY_TIMES),
        message=(
            "Vomiting many times in a day is one of the situations Missouri lists as warranting "
            "more immediate veterinary attention."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                MISSOURI_VOMITING,
                "lists profuse vomiting occurring many times in a day, or attempts to vomit"
                " continuing for more than 24 hours, among the situations warranting more"
                " immediate veterinary attention",
            ),
        ),
        reviewer_note=(
            "Added because the form could not see this clause at all: it asked how LONG the"
            " vomiting had gone on and never how often, so the duration-based rule was carrying"
            " both halves of Missouri's criterion. Is 'many times in a day' the right wording to"
            " put in front of an owner?"
        ),
    ),
    Rule(
        id="gi_signs_with_extreme_lethargy",
        condition=All(
            (
                Any_((HasRedFlag(RedFlag.VOMITING), HasRedFlag(RedFlag.DIARRHOEA))),
                HasRedFlag(RedFlag.EXTREME_LETHARGY),
            )
        ),
        # "marked lethargy ... needs prompt attention" was a paraphrase of a
        # paraphrase. Missouri's own construction is an escalation list inside a
        # vomiting or diarrhoeic presentation, and saying so lets a reviewer
        # check the sentence against the page without translating it first.
        message=(
            "Vomiting or diarrhoea in an animal that is extremely lethargic is one of the "
            "situations Missouri lists as warranting more immediate veterinary attention."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                MISSOURI_VOMITING,
                "lists an extremely lethargic or depressed animal among the situations warranting"
                " more immediate veterinary attention in a vomiting or diarrhoeic animal",
            ),
        ),
        extrapolations=frozenset({ExtrapolationKind.MAPPING}),
        reviewer_note=(
            "EXTRAPOLATION (mapping): the form offers \"very tired, won\u2019t move much\", and"
            " Missouri\u2019s item is \"the animal is extremely lethargic or depressed\". Treating"
            " the owner\u2019s words as that clinical description is our step; it is a short one,"
            " but it is ours. Missouri also frames its escalation list inside a vomiting/diarrhoea"
            " presentation, so this rule requires one of those signs. Lethargy reported on its own"
            " stays graded, because no source we hold addresses it alone."
        ),
    ),
    # DELETED: `prolonged_vomiting`, which fired on vomiting plus any duration
    # band beyond "today" and claimed Missouri's "attempts to vomit continue for
    # more than 24 hours". Those are not the same thing — an animal sick once a
    # day for three days has vomited over more than 24 hours without its
    # attempts to vomit continuing for 24 hours — and the form never established
    # which. Missouri's clause is now asked about directly, in
    # `profuse_vomiting_in_a_day`, so nothing sourced was lost by removing this.
    # Duration alone now supports no claim about vomiting; see candidates.py.
    Rule(
        id="major_trauma",
        condition=HasRedFlag(RedFlag.MAJOR_TRAUMA),
        message=(
            "After a car accident, a fall, or an attack, your pet needs to be seen even if they "
            "seem fine — an animal that looks stable can have substantial internal injury."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                ASPCA_EMERGENCY,
                "states pets may need emergency care because of severe trauma caused by an accident or fall",
            ),
            # The ASPCA names accidents and falls; the attack, and the reason
            # "even if they seem fine" is in the message at all, are Merck's.
            _cite(
                MERCK_TRAUMA,
                "describes attacks by other animals causing deep penetrating wounds, spinal"
                " injuries and major cervical, abdominal and thoracic trauma even without"
                " penetrating wounds, and states that a patient appearing normal and stable on"
                " initial examination may have substantial underlying injury that is not apparent"
                " for hours or sometimes days",
            ),
        ),
    ),
    Rule(
        id="heatstroke",
        condition=HasRedFlag(RedFlag.OVERHEATING),
        message="Suspected heatstroke is a life-threatening emergency — start cooling and travel now.",
        level_override=TriageLevel.RED,
        # One rule for both species, not two species-narrowed ones. Splitting it
        # meant neither fired when the owner had not told us the species, so an
        # overheating animal was answered with nothing at all — even though both
        # cited pages state the claim for dogs AND cats.
        citations=(
            _cite(
                MERCK_EMERGENCY,
                "states that heat stroke is an emergency, and instructs owners to move the animal"
                " out of the heat and cool the head and body with cool water, ice packs or wet"
                " towels, to use a fan, to take the pet to the vet right away, and not to immerse"
                " the animal in cold water",
            ),
            _cite(ASPCA_EMERGENCY, "names heatstroke among life-threatening situations"),
        ),
        # Cooling is quoted from Merck above, so the instruction in `message` is
        # traceable. Merck also gives two safety limits worth passing on.
        care_instructions=(
            "Move your pet out of the heat and start cooling now: cool (not cold) water, wet towels,"
            " or ice packs on the head and body, and a fan if you have one.",
            "Do not immerse your pet in cold water. Once their temperature starts to come down you"
            " can offer small amounts of water to drink.",
            "Travel to a veterinary clinic while cooling — heatstroke needs treatment even if your"
            " pet seems to improve.",
        ),
    ),
    Rule(
        id="choking",
        condition=HasRedFlag(RedFlag.CHOKING),
        message="Choking needs emergency veterinary care.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                ASPCA_EMERGENCY,
                "names choking among the causes a pet may need emergency care because of",
            ),
        ),
        reviewer_note=(
            "The ASPCA sentence behind this rule says a pet MAY need emergency care BECAUSE OF"
            " choking, which is weaker than 'choking is an emergency'. We keep it red because an"
            " obstructed airway is acute and the safe direction here is obvious, but the framing"
            " is the same one that made the old insect-sting rule wrong, so please confirm it."
        ),
    ),
    Rule(
        # A sting is an exposure, not a sign. This rule used to fire on the
        # exposure alone and send an owner to an emergency service because their
        # dog had been stung — while the same form's emergency screen had just
        # returned nothing. Merck describes the ordinary sting as local pain and
        # swelling resolving in minutes to a day; what makes one an emergency is
        # the reaction, so that is what the rule now reads.
        id="sting_with_emergency_signs",
        condition=All(
            (
                HasRedFlag(RedFlag.INSECT_STING_REACTION),
                Any_(
                    (
                        HasRedFlag(RedFlag.TROUBLE_BREATHING),
                        # Added with the breathing split: the ASPCA's own sign
                        # list is where this escalation comes from, and rapid
                        # breathing is on it.
                        HasRedFlag(RedFlag.RAPID_BREATHING_AT_REST),
                        HasRedFlag(RedFlag.COLLAPSE_OR_UNRESPONSIVE),
                        HasRedFlag(RedFlag.PALE_GUMS),
                        HasRedFlag(RedFlag.SEIZURE),
                        HasRedFlag(RedFlag.BLOOD_IN_VOMIT_OR_STOOL),
                    )
                ),
            )
        ),
        message=(
            "A sting together with breathing difficulty, collapse, pale gums, a seizure or blood "
            "in vomit or stool is the reaction that needs emergency care, not the sting on its "
            "own."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                ASPCA_EMERGENCY,
                "gives pale gums, rapid breathing, difficulty standing, apparent paralysis, loss"
                " of consciousness, seizures and excessive bleeding as signs a pet needs"
                " emergency care, and names an insect sting among the causes a pet may need"
                " emergency care because of",
            ),
            _cite(
                MERCK_STINGS,
                "describes the ordinary sting as localized pain, swelling and erythema occurring"
                " within minutes and resolving quickly unless a severe reaction occurs, and"
                " describes prostration, seizures or CNS depression, bloody diarrhea, bloody"
                " vomiting and hyperthermia after multiple stings, with anaphylaxis possible",
            ),
        ),
        reviewer_note=(
            "REPLACES a rule that made every reported sting an emergency on the strength of the"
            " ASPCA's 'may need emergency care because of ... an insect sting'. That sentence"
            " names causes, not emergencies, and the page never says a sting alone is"
            " life-threatening. PLEASE ADJUDICATE the middle ground, which we now leave"
            " uncovered: major or spreading swelling, a sting in the mouth or throat, many"
            " stings at once, or facial swelling in an animal that is otherwise well. Merck"
            " notes stings are most common on the face and in the mouth and describes systemic"
            " effects from massive envenomation, but gives no threshold for seeking care, so we"
            " have not invented one. What would you use?"
        ),
    ),
    Rule(
        id="black_tarry_stool",
        condition=HasRedFlag(RedFlag.BLACK_TARRY_STOOL),
        message="Black or tarry stool can mean bleeding higher in the gut and needs prompt attention.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(MISSOURI_VOMITING, "lists dark, tarry stool among situations warranting immediate attention"),
        ),
    ),
    Rule(
        id="diarrhoea_with_lethargy_or_anorexia",
        condition=All(
            (
                HasRedFlag(RedFlag.DIARRHOEA),
                Any_((HasRedFlag(RedFlag.EXTREME_LETHARGY), HasRedFlag(RedFlag.NOT_EATING))),
            )
        ),
        message="Diarrhoea together with lethargy or not eating needs prompt veterinary attention.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                CORNELL_DIARRHOEA,
                "lists the pet stopping eating, and lethargy, among red flags requiring immediate"
                " veterinary attention when a dog has diarrhoea",
            ),
        ),
        applies_to_species=DOG_ONLY,
    ),
)


# --------------------------------------------------------------------------
# Weighted rules — these accumulate into a concern score.
# The published evidence here is thinner, so the table is deliberately small.
# --------------------------------------------------------------------------

WEIGHTED_RULES: tuple[Rule, ...] = (
    Rule(
        id="ear_neurological_signs",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        # Ungated, for the same reason as the eye rule: a head tilt reads as a
        # "behaviour" problem to an owner, and used to be discarded when they
        # said so. Weighted rather than an emergency — see the reviewer note.
        condition=Any_(
            (
                HasRedFlag(RedFlag.EAR_HEAD_TILT),
                HasRedFlag(RedFlag.EAR_BALANCE_PROBLEMS),
                HasRedFlag(RedFlag.EAR_RAPID_EYE_MOVEMENTS),
                HasRedFlag(RedFlag.EAR_SUDDEN_HEARING_LOSS),
                HasRedFlag(RedFlag.EAR_FACIAL_DROOP),
            )
        ),
        message=(
            "Head tilt, loss of balance, abnormal eye movements, sudden hearing loss or facial "
            "weakness can indicate disease deeper in the ear, which needs an examination a photo "
            "cannot substitute for."
        ),
        weight=3,
        citations=(
            _cite(
                MERCK_OTITIS_MEDIA_INTERNA,
                "lists head tilt, loss of coordination, circling, falling, nystagmus, hearing loss"
                " and facial nerve paralysis among signs of middle or inner ear disease; states"
                " that diagnosis begins with a complete history, a physical examination and, when"
                " possible, an otoscopic examination; and that treatment is most successful when"
                " started early in the disease course",
            ),
        ),
        headline="Veterinary examination recommended",
        advice=(
            "Contact your veterinary clinic and arrange an examination. Go sooner, or use an "
            "emergency service, if your pet cannot stand, is repeatedly falling, or is in obvious "
            "distress."
        ),
        urgent_care_signs=_EAR_URGENT_CARE_SIGNS,
        care_instructions=_EAR_CARE_INSTRUCTIONS,
        reviewer_note=(
            "PLEASE ADJUDICATE: an earlier version treated these signs as a same-day emergency."
            " Nothing on the cited Merck pages calls them urgent or gives any timing, so they are"
            " now graded rather than red. If vestibular signs should be same-day in practice,"
            " please say so and name a source, and the rule will be raised."
        ),
    ),
    Rule(
        id="ear_warning_signs",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        # Every ear sign the form offers, evaluated on the sign alone. Gating
        # these on the owner having also chosen "ears" left five of them —
        # head shaking, odour, discharge, redness and pain — reachable only
        # through the concern-based pathway, so an owner who filed a smelly,
        # painful ear under "skin or coat" got no rules and no answer.
        condition=Any_(
            (
                HasRedFlag(RedFlag.EAR_HEAD_SHAKING_OR_SCRATCHING),
                HasRedFlag(RedFlag.EAR_ODOR),
                HasRedFlag(RedFlag.EAR_DISCHARGE),
                HasRedFlag(RedFlag.EAR_REDNESS),
                HasRedFlag(RedFlag.EAR_PAIN),
                HasRedFlag(RedFlag.EAR_BLOODY_OR_PUS_DISCHARGE),
                HasRedFlag(RedFlag.EAR_FLAP_SWELLING),
                HasRedFlag(RedFlag.EAR_SELF_INJURY),
                HasRedFlag(RedFlag.EAR_FOREIGN_BODY),
            )
        ),
        message=(
            "Head shaking or scratching, odour, discharge, redness, pain, a swollen ear flap, "
            "injury from scratching, or a possible object in the ear all need an examination that "
            "can see inside the ear canal."
        ),
        weight=3,
        citations=(
            _cite(
                MERCK_OTITIS_EXTERNA,
                "lists head shaking, aural pruritus, pain, malodor, otic discharge, erythema, edema"
                " and foreign bodies among the signs of otitis externa in dogs and cats, and states"
                " diagnosis is based on history, otoscopic examination and cytological evaluation",
            ),
            _cite(
                MERCK_AURICULAR_HEMATOMA,
                "describes fluid-filled ear-flap swelling associated with trauma from head shaking"
                " or scratching and the need to manage the underlying cause",
            ),
        ),
        headline="Veterinary examination recommended",
        advice=(
            "Contact your veterinary clinic and arrange an examination. Go sooner if the ear looks "
            "severely painful, the swelling is growing quickly, or your pet is in distress."
        ),
        urgent_care_signs=_EAR_URGENT_CARE_SIGNS,
        care_instructions=_EAR_CARE_INSTRUCTIONS,
        reviewer_note=(
            "PLEASE ADJUDICATE: the structural signs here (bloody or pus-like discharge, ear-flap"
            " swelling, self-injury, foreign body) were previously same-day red. Neither cited page"
            " uses urgency language — Merck's auricular-hematoma page describes no time-critical"
            " management at all — so they are graded alongside the otitis externa signs. Confirm"
            " whether an ear-flap hematoma or a lodged grass seed warrants faster care than this."
        ),
    ),
    Rule(
        id="extreme_lethargy",
        condition=HasRedFlag(RedFlag.EXTREME_LETHARGY),
        message="Marked lethargy suggests your pet should be seen.",
        weight=3,
        citations=(
            _cite(
                MISSOURI_VOMITING,
                "lists an extremely lethargic or depressed animal among situations warranting"
                " immediate attention",
            ),
        ),
        extrapolations=frozenset({ExtrapolationKind.THRESHOLD}),
        reviewer_note=(
            "EXTRAPOLATION (threshold): Missouri frames lethargy alongside vomiting, so lethargy"
            " WITH a gastrointestinal sign is now a separate emergency rule"
            " (gi_signs_with_extreme_lethargy). This rule covers lethargy reported on its own,"
            " which no source we hold addresses — the bar for acting on it is ours. Should"
            " isolated lethargy be graded like this, or does it warrant same-day care?"
        ),
    ),
    Rule(
        id="increased_thirst",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        condition=HasRedFlag(RedFlag.DRINKING_MUCH_MORE),
        message="A lasting increase in thirst is worth investigating.",
        # Weighted to reach amber on its own: the source treats increased thirst
        # as needing diagnostic work-up, which is more than 'monitor at home'.
        weight=3,
        citations=(
            _cite(
                VCA_THIRST,
                "describes increased thirst and urination as associated with kidney disease, diabetes,"
                " hormone disorders, liver disease and other conditions requiring diagnosis",
            ),
        ),
    ),
    Rule(
        id="eye_signs_without_injury",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        # The three ordinary signs are triggers in their own right, not just
        # extra detail, for the reason `eye_emergency_signs` gives above: the
        # evidence attaches to the sign, not to the box the owner filed it
        # under. Someone reporting a red, watering eye under "something else"
        # reaches the same pathway as someone who picked "Eyes".
        condition=Any_(
            (
                ConcernIs(Concern.EYES),
                BodyAreaIn((BodyArea.EYE,)),
                HasRedFlag(RedFlag.EYE_REDNESS),
                HasRedFlag(RedFlag.EYE_WATERING),
                HasRedFlag(RedFlag.EYE_IRRITATION),
            )
        ),
        message=_EYE_CONCERN_REASON,
        weight=3,
        # Merck calls acute glaucoma an ophthalmic emergency, so timing evidence
        # for the eye pathway exists — though not for the 24 hours this rule
        # names; see the reviewer note.
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(
                VCA_EYE_ISSUES,
                "states that redness, watering and irritation may be caused by debris but can also"
                " indicate infection, injury or another condition needing prompt attention",
            ),
            _cite(
                MERCK_ANTERIOR_UVEITIS,
                "requires fluorescein staining during evaluation and describes uveitis as potentially"
                " secondary to trauma, corneal ulceration, lens disease, neoplasia or systemic disease",
            ),
            _cite(
                MERCK_ACUTE_GLAUCOMA,
                "describes acute glaucoma as an ophthalmic emergency diagnosed by measuring"
                " intraocular pressure",
            ),
            _cite(
                MERCK_EYE_ANTI_INFLAMMATORY,
                "requires fluorescein staining before ocular steroids and states corticosteroids are"
                " contraindicated when a corneal ulcer is present",
            ),
        ),
        headline="Veterinary examination recommended within 24 hours",
        advice=(
            "Contact your veterinary clinic today and arrange an examination, ideally within 24 "
            "hours."
        ),
        urgent_care_signs=_EYE_URGENT_CARE_SIGNS,
        care_instructions=_EYE_CARE_INSTRUCTIONS,
        extrapolations=frozenset({ExtrapolationKind.TIMING, ExtrapolationKind.MAPPING}),
        reviewer_note=(
            "EXTRAPOLATION (timing): the 24-hour figure in the headline is ours. VCA says eye signs need"
            " prompt attention and Merck calls acute glaucoma an ophthalmic emergency; neither"
            " names 24 hours for a new eye concern in general. Confirm the window or replace it."
            " This pathway is for a new eye concern without a listed urgent warning sign. Injury,"
            " pain, clouding, pupil or vision change, bulging, abnormal discharge, chemical exposure,"
            " or rapid worsening are handled by the same-day urgent rule."
            "\n      EXTRAPOLATION (mapping), NEWLY DECLARED — it was always here and was not"
            " written down. VCA's page is about redness, watering and irritation. This rule also"
            " fires on the bare fact that the owner picked 'Eyes' and ticked nothing, which is us"
            " deciding that an unspecified eye concern is the thing VCA describes. Until"
            " 2026-08-22 the rule then TOLD that owner about 'redness and watering', signs they"
            " had never reported and the form had never offered; the form now asks about all"
            " three and the message names no sign it was not given."
            "\n      THE OPEN QUESTION IS WHETHER FIRING WITHOUT THEM IS RIGHT. A reviewer"
            " proposed gating this rule on the three signs, so an eye concern with nothing ticked"
            " would reach no rule and get our abstention. We have not done that, because it turns"
            " a worried owner's 'something is wrong with her eye' into 'we can't assess this one'."
            " Please rule on it: keep the rule firing on the concern alone, or gate it."
        ),
    ),
    Rule(
        id="persistent_or_worsening_ear_problem",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        condition=All(
            (
                _EAR_CONCERN,
                Any_(
                    (
                        DurationIn(
                            (Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)
                        ),
                        TrendIs(Trend.WORSENING),
                        HasRedFlag(RedFlag.EAR_HEAD_SHAKING_OR_SCRATCHING),
                        HasRedFlag(RedFlag.EAR_ODOR),
                        HasRedFlag(RedFlag.EAR_DISCHARGE),
                        HasRedFlag(RedFlag.EAR_REDNESS),
                        HasRedFlag(RedFlag.EAR_PAIN),
                    )
                ),
            )
        ),
        message=_EAR_REASON,
        weight=3,
        citations=(
            _cite(
                MERCK_OTITIS_EXTERNA,
                "describes head shaking, itching, pain, odor, redness, discharge and swelling in"
                " dogs and cats; diagnosis uses history, otoscopy and cytology, and treatment"
                " depends on the specific cause",
            ),
            _cite(
                MERCK_OTITIS_MEDIA_INTERNA,
                "states that examination of deeper ear disease begins with history, physical"
                " examination and otoscopic evaluation when possible",
            ),
        ),
        headline="Veterinary appointment recommended within 24-48 hours",
        advice=(
            "Contact your veterinary clinic today and arrange an examination within 24-48 hours. "
            "This timing is a cautious recommendation based on persistence or worsening, not a "
            "diagnosis."
        ),
        urgent_care_signs=_EAR_URGENT_CARE_SIGNS,
        care_instructions=_EAR_CARE_INSTRUCTIONS,
        extrapolations=frozenset({ExtrapolationKind.TIMING}),
        reviewer_note=(
            "EXTRAPOLATION (timing): the sources support veterinary examination and cause-directed"
            " treatment"
            " but do not set a universal 24-48 hour threshold. This cautious timing is triggered only"
            " by persistence, worsening, or specific ear signs and needs veterinary review."
        ),
    ),
    Rule(
        id="not_weight_bearing",
        condition=All(
            (
                CannotBearWeight(),
                DurationIn((Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)),
            )
        ),
        message="Refusing to put weight on a limb for more than a day needs veterinary attention.",
        weight=3,
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(
                VCA_LIMPING,
                "states that if lameness persists more than 24 hours, seek veterinary care, and that"
                " most dogs will not walk on a broken leg, torn ligament, or dislocated joint",
            ),
        ),
        applies_to_species=DOG_ONLY,
        reviewer_note=(
            "Rewritten after research: previously this fired regardless of duration. A limb that CANNOT"
            " MOVE remains a separate emergency rule."
        ),
    ),
    Rule(
        id="lameness_over_24h",
        condition=All(
            (
                ConcernIs(Concern.MOBILITY),
                DurationIn((Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)),
            )
        ),
        message="Limping that has lasted more than a day should be checked.",
        weight=3,
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(VCA_LIMPING, "states that if lameness persists for more than 24 hours, seek veterinary care"),
        ),
        applies_to_species=DOG_ONLY,
    ),
    Rule(
        id="dog_not_eating",
        condition=All((SpeciesIs("dog"), HasRedFlag(RedFlag.NOT_EATING))),
        message="A dog going off its food is worth having checked.",
        weight=3,
        citations=(
            _cite(
                VCA_ANOREXIA_DOGS,
                "states that changes in eating habits warrant investigation, that refusal to eat is"
                " strongly associated with illness, and advises involving the veterinarian early",
            ),
        ),
        applies_to_species=DOG_ONLY,
        reviewer_note=(
            "VCA gives no hour threshold for dogs, unlike Cornell's 24 hours for cats, so this is graded"
            " rather than timed. What threshold would you use for dogs?"
        ),
    ),
    Rule(
        id="diarrhoea_over_two_days",
        condition=All(
            (
                HasRedFlag(RedFlag.DIARRHOEA),
                DurationIn((Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)),
            )
        ),
        message="Loose stool lasting more than a couple of days should be checked.",
        weight=3,
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(CORNELL_DIARRHOEA, "states that if loose stool lasts more than two days, call the vet"),
        ),
        applies_to_species=DOG_ONLY,
        reviewer_note="Our '2–7 days' band starts at day two, slightly earlier than Cornell's wording.",
    ),
    Rule(
        id="skin_lesion_needs_examination",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        # Ungated on the concern, like the eye and ear rules: an owner who files
        # a bald, scabby patch under "something else" has still described a
        # dermatological presentation, and the evidence attaches to the sign.
        condition=Any_(tuple(HasRedFlag(flag) for flag in _SKIN_LESION_FLAGS)),
        # Reads back only what the owner ticked. This used to list every
        # presentation the rule covers, so someone reporting an itchy red patch
        # was told about hair loss, crusting, nodules and lumps as well.
        message=(
            "You reported {reported}. Many skin diseases look alike, so appearance alone cannot "
            "reliably identify the cause: it is worked out from the history — how long it has "
            "gone on, how much your pet is licking or scratching, where the lesions are — "
            "together with a complete physical examination."
        ),
        reported_signs=_SKIN_LESION_FLAGS,
        weight=3,
        citations=(
            _cite(
                MERCK_SKIN_DIAGNOSIS,
                "states that a complete physical examination should always be performed to help"
                " diagnose a skin disease, with very close inspection of all the hair and skin;"
                " that many skin diseases look alike and a definitive diagnosis is made by"
                " including or excluding possible causes and evaluating responses to treatment;"
                " and lists duration, presence and severity of pruritus, progression and lesion"
                " distribution among the dermatologic history",
            ),
            _cite(
                MERCK_DERM_PROBLEMS,
                "organises skin disease by presentation — pruritus, alopecia, scaling and"
                " crusting, nodules or tumors, odor, erosions and ulcerations, and nonhealing"
                " wounds — and records lesion distribution as focal, multifocal, symmetrical or"
                " generalized",
            ),
        ),
        headline=_SKIN_HEADLINE,
        advice=_SKIN_ADVICE,
        what_to_expect=_SKIN_WHAT_TO_EXPECT,
        urgency_evidence=UrgencyEvidence.NOT_STATED,
        # The recommendation itself is Merck's: a complete physical examination
        # should always be performed to help diagnose a skin disease. What we
        # add is deciding that "red and itchy" is a skin disease to diagnose.
        extrapolations=frozenset(
            {ExtrapolationKind.MAPPING, ExtrapolationKind.THRESHOLD}
        ),
        reviewer_note=(
            "EXTRAPOLATION (mapping): Merck states what a clinician needs in order to diagnose a skin"
            " problem — and 'a complete physical examination should always be performed' is close"
            " to an instruction. Reading it as 'this animal should be booked in for one' is still"
            " our step: the page addresses veterinarians and never tells an owner when to seek"
            " care. The rule therefore carries no timeframe at all. Please confirm the level, and"
            " say whether any of these presentations (a new lump, a rapidly enlarging swelling)"
            " should be seen faster than the rest. Also: two cited pages cover animals generally,"
            " but the rule is held to dogs and cats to match the rest of the table. Should skin"
            " guidance extend to other species?"
        ),
    ),
    Rule(
        id="skin_infection_or_wound_signs",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        condition=Any_(tuple(HasRedFlag(flag) for flag in _SKIN_INFECTION_FLAGS)),
        message=(
            "You reported {reported}. Pus or discharge, a strong smell and broken or raw skin are "
            "the signs Merck describes for bacterial skin infection. Which organism is involved "
            "is established by testing a sample, and the treatment that works follows from that "
            "result."
        ),
        reported_signs=_SKIN_INFECTION_FLAGS,
        weight=3,
        citations=(
            _cite(
                MERCK_PYODERMA,
                "gives pain, crusting, odor and exudation of blood and pus as the hallmarks of"
                " deep pyoderma in dogs, with erythema, swelling, ulcerations and draining tracts"
                " also possible; states diagnosis rests on characteristic lesions plus"
                " confirmation of bacteria, that cytological evaluation is one of the most"
                " valuable tools, and that treatment should be based on culture and"
                " susceptibility testing",
            ),
            _cite(
                MERCK_DERM_PROBLEMS,
                "names erosions and ulcerations, odor, and nonhealing wounds among the"
                " dermatological presentations it organises skin disease by",
            ),
        ),
        headline=_SKIN_HEADLINE,
        advice=_SKIN_ADVICE,
        what_to_expect=(
            "Merck states that treatment for a bacterial skin infection should be based on the"
            " results of culture and susceptibility testing — which product works is decided"
            " after testing, not before it.",
            *_SKIN_WHAT_TO_EXPECT,
        ),
        urgency_evidence=UrgencyEvidence.NOT_STATED,
        extrapolations=frozenset(
            {ExtrapolationKind.MAPPING, ExtrapolationKind.THRESHOLD}
        ),
        reviewer_note=(
            "EXTRAPOLATION (mapping): deciding that the signs the owner ticked are the pyoderma"
            " signs Merck describes is our step. PLEASE ADJUDICATE, two further questions."
            " (1) Merck calls deep pyoderma 'more serious because"
            " it expands into the dermis, with a higher risk of bacteremia', but gives no timing"
            " and no emergency wording, so these signs are graded like the rest of the skin table."
            " Should pus, odour and draining tracts be seen sooner than that? (2) An explicit 'do"
            " not put leftover or over-the-counter products on this' warning was removed, because"
            " no page we hold states it as a recommendation — only that treatment should follow"
            " culture and susceptibility testing. Would you sign off such a warning in your own"
            " name so it can go back in?"
        ),
    ),
    Rule(
        id="skin_problem_the_animal_cannot_leave_alone",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        condition=ItchLevelIn((ItchLevel.FREQUENT, ItchLevel.CANNOT_SETTLE)),
        message=(
            "You told us your pet is licking, scratching or chewing at it a great deal. Merck "
            "records how severe that is as part of the dermatologic history, and states that "
            "diseases beginning with itching can lead to self-trauma and then to secondary skin "
            "lesions or infections."
        ),
        weight=3,
        citations=(
            _cite(
                MERCK_SKIN_DIAGNOSIS,
                "records the presence and severity of pruritus, as indicated by behaviors such as"
                " licking, rubbing, scratching or chewing, among the dermatologic history, and"
                " states that diseases that begin with pruritus can lead to self-trauma and"
                " subsequent development of secondary skin lesions or infections",
            ),
            _cite(
                MERCK_PRURITUS,
                "defines pruritus as an unpleasant sensation that provokes the desire to scratch,"
                " calls it the most common dermatological problem in small and large animals, and"
                " states that diagnosis requires a methodical workup",
            ),
        ),
        headline=_SKIN_HEADLINE,
        advice=_SKIN_ADVICE,
        what_to_expect=_SKIN_WHAT_TO_EXPECT,
        urgency_evidence=UrgencyEvidence.NOT_STATED,
        extrapolations=frozenset(
            {ExtrapolationKind.MAPPING, ExtrapolationKind.THRESHOLD}
        ),
        reviewer_note=(
            "EXTRAPOLATION (mapping), narrower than it was. Merck's skin-diagnosis page does record the"
            " SEVERITY of pruritus as part of the history, so asking the question is sourced."
            " What remains ours is the scale: four bands, and the line between 'sometimes' and"
            " 'a lot' deciding whether this rule fires. Merck grades nothing and gives no"
            " threshold. Where would you draw it?"
        ),
    ),
    Rule(
        id="skin_problem_affecting_another_animal_or_person",
        diagnostic_evidence=DiagnosticEvidence.DESCRIBED,
        condition=HasRedFlag(RedFlag.SKIN_CONTAGION),
        message=(
            "You told us another animal or a person at home has a skin problem too. Merck records "
            "contact with possibly contagious animals as part of the history a skin diagnosis is "
            "built on, and some skin infections spread between animals and to people."
        ),
        weight=3,
        citations=(
            _cite(
                MERCK_SKIN_DIAGNOSIS,
                "lists contact with other possibly contagious animals among the dermatologic"
                " history, naming fleas, scabies, cheyletiellosis and dermatophytosis",
            ),
            _cite(
                MERCK_DERMATOPHYTOSIS,
                "states that dermatophytosis is a zoonotic disease transmitted by direct contact"
                " with an infected animal, that no single test is a gold standard and multiple"
                " tests are typically used to confirm infection, and that infected small animals"
                " should remain isolated from other pets until there is clear evidence of"
                " clinical cure",
            ),
        ),
        headline=_SKIN_HEADLINE,
        advice=_SKIN_ADVICE,
        care_instructions=(
            "Merck advises that an animal with a confirmed fungal skin infection be kept away from"
            " other pets until there is clear evidence of cure. Whether that applies here depends"
            " on what the examination finds.",
        ),
        what_to_expect=_SKIN_WHAT_TO_EXPECT,
        urgency_evidence=UrgencyEvidence.NOT_STATED,
        extrapolations=frozenset(
            {ExtrapolationKind.MAPPING, ExtrapolationKind.THRESHOLD}
        ),
        reviewer_note=(
            "EXTRAPOLATION (mapping): contact with possibly contagious animals is explicitly part of Merck's"
            " dermatologic history, so collecting this is sourced. Treating it as a reason to"
            " examine THIS animal is our step. Merck also calls dermatophytosis self-limiting in"
            " otherwise healthy animals, resolving in 6-12 weeks, so nothing here makes contagion"
            " time-critical. Is this the right level? A hand-washing instruction was removed for"
            " lack of a source — would you sign one off?"
        ),
    ),
    # ------------------------------------------------------------------ cats
    #
    # Added 2026-08-23. Everything below closes the same gap: the graded rules
    # for limping and loose stool rested on VCA's canine limping page and
    # Cornell's CANINE diarrhoea page, whose species scope - correctly - kept
    # them off cats. The effect was that a limping cat and a cat with diarrhoea
    # were told "We can't assess this safely" while the identical dog got an
    # amber result, which reads to the owner as a judgement about their animal
    # and was in fact a judgement about which pages we had opened.
    Rule(
        id="cat_not_weight_bearing",
        condition=All(
            (
                CannotBearWeight(),
                DurationIn((Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)),
            )
        ),
        message="Refusing to put weight on a limb for more than a day needs veterinary attention.",
        weight=3,
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(
                VCA_LIMPING_CATS,
                "states that if lameness persists for more than 24 hours, seek veterinary care, and"
                " that most cats will not walk on a broken leg, torn ligament, or dislocated joint",
            ),
        ),
        applies_to_species=CAT_ONLY,
        reviewer_note=(
            "The feline counterpart of `not_weight_bearing`. Same wording and same threshold,"
            " because VCA's cat page states both in the same terms as its dog page."
        ),
    ),
    Rule(
        id="cat_lameness_over_24h",
        condition=All(
            (
                ConcernIs(Concern.MOBILITY),
                DurationIn((Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)),
            )
        ),
        message="Limping that has lasted more than a day should be checked.",
        weight=3,
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(
                VCA_LIMPING_CATS,
                "states that if lameness persists for more than 24 hours, seek veterinary care",
            ),
        ),
        applies_to_species=CAT_ONLY,
        reviewer_note="The feline counterpart of `lameness_over_24h`.",
    ),
    Rule(
        id="cat_diarrhoea_needs_examination",
        condition=HasRedFlag(RedFlag.DIARRHOEA),
        message=(
            "Cornell's feline guidance is that a cat with diarrhoea should be examined by a "
            "veterinarian as soon as the signs are noticed."
        ),
        weight=3,
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(
                CORNELL_FELINE_DIARRHOEA,
                "states that it is most important for a veterinarian to examine an affected animal"
                " as soon as the clinical signs are noticed, as some over-the-counter medications"
                " can be harmful to cats",
            ),
        ),
        applies_to_species=CAT_ONLY,
        reviewer_note=(
            "Deliberately NOT a mirror of the dog rule, which needs two days of loose stool before"
            " it fires. Cornell's feline page makes the examination claim with no duration"
            " attached, so this fires on the first day. Two things for you to weigh: the sentence"
            " sits in a paragraph warning against over-the-counter remedies, so it may be aimed at"
            " self-medication rather than at every loose stool; and it makes any feline diarrhoea"
            " amber, where the same sign in a dog on day one is now green. Is that the right"
            " reading, and is the asymmetry between the two species one you would keep?"
        ),
    ),
    Rule(
        id="cat_diarrhoea_with_systemic_signs",
        condition=All(
            (
                HasRedFlag(RedFlag.DIARRHOEA),
                DurationIn((Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)),
                Any_(
                    (
                        HasRedFlag(RedFlag.NOT_EATING),
                        HasRedFlag(RedFlag.EXTREME_LETHARGY),
                        HasRedFlag(RedFlag.VOMITING),
                    )
                ),
            )
        ),
        message=(
            "Diarrhoea lasting more than a day or two alongside poor appetite, lethargy or "
            "vomiting is what Cornell's feline guidance says to seek care for as soon as possible."
        ),
        weight=3,
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(
                CORNELL_FELINE_DIARRHOEA,
                "states that if the diarrhea persists for longer than a day or two and the cat is"
                " also showing systemic signs, such as poor appetite, lethargy, or vomiting, you"
                " should seek veterinary care as soon as possible",
            ),
        ),
        applies_to_species=CAT_ONLY,
        reviewer_note=(
            "Cornell's sentence joins the duration AND the systemic signs with 'and', so this rule"
            " does too rather than splitting them. It overlaps `cat_diarrhoea_needs_examination` on"
            " purpose: they are different sentences making different claims, and the owner sees"
            " both reasons."
        ),
    ),
    # ------------------------------------------------- vomiting and loose stool
    #
    # Added 2026-08-23. `prolonged_vomiting` was deleted - see the note above
    # this tuple - because it claimed a Missouri clause the form could not see,
    # and nothing replaced it. So plain vomiting matched NO rule at all unless
    # it was profuse, bloody, in a fragile patient, or paired with extreme
    # lethargy: "my dog was sick twice yesterday", one of the most ordinary
    # things an owner arrives with, came back as "We can't assess this safely".
    #
    # The fix is not to reinstate an urgency claim nobody sourced. Both pages
    # below publish HOME CARE for exactly this animal, so these rules carry a
    # weight low enough to stay green on their own, and put the source's own
    # instructions in front of the owner instead of a refusal.
    Rule(
        id="vomiting_home_care_in_healthy_adult",
        condition=All((HasRedFlag(RedFlag.VOMITING), Not(IsFragilePatient()))),
        message=(
            "Missouri publishes home care for an otherwise healthy adult pet that has vomited, "
            "with the signs that mean it should be seen instead."
        ),
        # One, not three. The score has to leave this green on its own - the
        # source's whole point is that this animal can be looked after at home -
        # while still adding to the picture if something else fires alongside it.
        weight=1,
        headline="You can start home care for this",
        advice=(
            "Missouri's guidance for an otherwise healthy adult pet is to withhold food for about "
            "12 hours while leaving water available, then reintroduce food gradually. Contact a "
            "veterinary practice instead if the vomiting happens many times in a day, if attempts "
            "to vomit continue for more than 24 hours, or if the vomit contains blood or looks "
            "like coffee grounds."
        ),
        care_instructions=(
            "Do not feed your pet for 12 hours, but continue to allow access to water.",
            "If the vomiting has stopped after about 12 hours, offer a small amount of bland food:"
            " a prescription diet from your veterinarian, or boiled chicken and rice.",
            "Repeat small meals every few hours if they stay down, move to moderately sized meals"
            " the next day, and return to the usual food gradually by about the fourth day.",
        ),
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            _cite(
                MISSOURI_VOMITING,
                "gives home care for an otherwise healthy adult pet that has vomited - do not feed"
                " for 12 hours but continue to allow access to water, then offer bland food such"
                " as boiled chicken and rice in small quantities, building back to regular food by"
                " about day four - and lists vomiting many times in a day, attempts to vomit"
                " continuing for more than 24 hours, and vomit containing blood or resembling"
                " coffee grounds as warranting more immediate attention",
            ),
        ),
        reviewer_note=(
            "This rule exists to stop plain vomiting returning UNASSESSED, which is what it did"
            " between `prolonged_vomiting` being deleted and this being added. It makes no urgency"
            " claim of its own: the escalation triggers it names are Missouri's, and each already"
            " has its own emergency rule, so a case meeting one goes red regardless of this. The"
            " fragile-patient exclusion is Missouri's too - that animal is covered by"
            " `vomiting_or_diarrhoea_in_fragile_animal`. Is 12 hours of withheld food advice you"
            " are willing to have us give without an examination?"
        ),
    ),
    Rule(
        id="diarrhoea_home_care_in_healthy_adult",
        condition=All(
            (
                HasRedFlag(RedFlag.DIARRHOEA),
                # Written as "not one of the longer bands" rather than "today",
                # so it also covers an owner who skipped the duration question.
                # Gated on `today` alone, answering that question turned an
                # unassessed result into a green one, which is the safety
                # invariant `test_filling_in_an_optional_field_never_lowers_
                # urgency` exists to catch: an optional answer must never calm
                # the verdict. From day two `diarrhoea_over_two_days` takes over.
                Not(DurationIn((Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH))),
                # Cornell publishes a separate feline page that does NOT say
                # this — it asks for an examination as soon as signs are noticed,
                # with no threshold — so a cat follows its own page, not this one.
                # The clause is here rather than in `applies_to_species` because
                # the rule must still fire when we were never told the species:
                # excluding it there would leave that owner with no result at all.
                Not(SpeciesIs("cat")),
                Not(IsFragilePatient()),
            )
        ),
        message=(
            "Cornell describes mild, short-lived diarrhoea as something that can be managed at "
            "home, with the signs that mean it should be seen instead."
        ),
        weight=1,
        headline="You can start home care for this",
        advice=(
            "Cornell's guidance for a mild case is to withhold food for 12 to 24 hours, then "
            "introduce a bland diet, with fresh water available throughout. Seek veterinary care "
            "if your dog stops eating, is lethargic, the stool is black or tarry, there is "
            "vomiting alongside it, or it has not resolved in 48 to 72 hours."
        ),
        care_instructions=(
            "Withhold all food for 12 to 24 hours, then introduce a bland diet.",
            "Feed a bland diet such as boiled chicken or low-fat hamburger, and white rice.",
            "Have fresh water available at all times.",
        ),
        urgency_evidence=UrgencyEvidence.STATED,
        citations=(
            # Not `_cite`: that copies the SOURCE's species scope, and this page
            # is registered dog-only for good reason - every other claim on it
            # is canine. This one sentence says "in both cats and dogs" in its
            # own words, and the citation records the scope of the sentence.
            Citation(
                source=CORNELL_DIARRHOEA.name,
                url=CORNELL_DIARRHOEA.url,
                accessed=CORNELL_DIARRHOEA.accessed,
                species=DOG_AND_CAT,
                supports="states that most cases resolve on their own and that mild cases can be treated at"
                " home by withholding food for 12-24 hours and then feeding a bland diet of boiled"
                " chicken or low-fat hamburger and white rice with fresh water available at all"
                " times, and that veterinary care should be sought if the pet stops eating, is"
                " lethargic, the diarrhea is black or tarry, there is associated vomiting, or it"
                " does not resolve in 48-72 hours",
            ),
        ),
        reviewer_note=(
            "Two things to check. First, the species scope: this cites a page published by"
            " Cornell's CANINE centre, and the only sentence on it that names cats is the"
            " bland-diet one - \"mild cases of diarrhea in both cats and dogs can be treated at"
            " home\" - so the citation is scoped to both species and the rule then excludes cats"
            " by hand, because Cornell's feline page asks for an examination instead. The net"
            " effect is that the rule reaches dogs and animals whose species we were never told."
            " Second, it stops at the first day: from day two the same page says call the vet and"
            " `diarrhoea_over_two_days` takes over, so the two never contradict each other."
        ),
    ),
)


#: The signs Merck's emergency page and the ASPCA's emergency-care page list as
#: needing emergency veterinary care. Used as the safety net on any result whose
#: own rules supply no sourced urgent-care list — a skin answer, for instance,
#: because nothing we hold states an urgency threshold for skin. These signs are
#: sourced independently of whatever the owner came in about, and they do not
#: stop being true because our rule table has a gap.
@dataclass(frozen=True)
class GeneralEmergencySign:
    """One line of the safety-net list, and the page(s) that state it."""

    text: str
    sources: tuple[Source, ...]
    #: The emergency questions this line answers for. Not decoration: the form
    #: asks about a fixed set of emergency triggers, this list is what an owner
    #: is told to come back for, and the two used to be maintained by hand
    #: independently of each other. They had already drifted — the form asked
    #: about a urinary blockage, a bloated abdomen with retching, blood in
    #: vomit or stool, an eye injury and a limb that cannot move, and none of
    #: the five appeared in the list shown afterwards. `covers` is what
    #: `test_every_emergency_question_has_a_line_to_come_back_for` reads, so
    #: adding a trigger to the form without a line here now fails the suite.
    covers: tuple[RedFlag, ...] = ()
    #: Whose emergency this is, where the source only establishes it for one
    #: species — mirroring `applies_to_species` on the rules. A urethral
    #: blockage is Cornell's claim about cats and GDV is Cornell's about dogs;
    #: neither page speaks for the other animal, and this list is shown to
    #: everyone.
    species: frozenset[str] | None = None


#: The safety net shown when a result's own rules supply no sourced urgent-care
#: list. Attributed one line at a time, because they are not uniformly sourced:
#: severe pain is Merck's, the gum colour and the seizure are the ASPCA's, and a
#: reviewer checking the other page for either would come away empty. Several
#: entries are situations rather than clinical signs, which is why the section
#: is headed "Emergency warning signs or situations".
GENERAL_EMERGENCY_SIGNS: tuple[GeneralEmergencySign, ...] = (
    GeneralEmergencySign(
        # Qualified to match the trigger it covers. An earlier version kept the
        # bare "rapid or laboured" on the reasoning that an owner reads this
        # line later, with the animal at rest by then — which is simply not
        # true. They may read it straight after a walk, while the dog is hot,
        # excited, or has just been carried to the car. Leaving it unqualified
        # put the over-broad predicate back on the page one section below the
        # question we had just narrowed, and the disclosure is the half that
        # tells them when to act.
        "Difficulty or laboured breathing, or breathing unusually fast while resting.",
        (MERCK_EMERGENCY, ASPCA_EMERGENCY),
        covers=(RedFlag.TROUBLE_BREATHING, RedFlag.RAPID_BREATHING_AT_REST),
    ),
    GeneralEmergencySign(
        "Collapse, an inability to stand, or unresponsiveness.",
        (ASPCA_EMERGENCY,),
        covers=(RedFlag.COLLAPSE_OR_UNRESPONSIVE,),
    ),
    GeneralEmergencySign(
        "Pale or white gums.", (ASPCA_EMERGENCY,), covers=(RedFlag.PALE_GUMS,)
    ),
    GeneralEmergencySign("A seizure.", (ASPCA_EMERGENCY,), covers=(RedFlag.SEIZURE,)),
    GeneralEmergencySign(
        "Bleeding that will not stop.",
        (MERCK_EMERGENCY, ASPCA_EMERGENCY),
        covers=(RedFlag.UNCONTROLLED_BLEEDING,),
    ),
    # Merck's list only. The ASPCA emergency page does not name pain as a
    # threshold, and pairing both pages with this line implied that it did.
    GeneralEmergencySign(
        "Signs of severe pain.", (MERCK_EMERGENCY,), covers=(RedFlag.SEVERE_PAIN,)
    ),
    # ------------------------------------------------------------------
    # The five below were asked about on the form and then missing from the
    # list shown afterwards, so an owner whose dog developed a bloated abdomen
    # an hour after a skin result was told nothing about it. Each carries the
    # citation its own emergency rule already carries; none of them is a new
    # claim, only a claim that was already being made in one place and not the
    # other.
    # ------------------------------------------------------------------
    GeneralEmergencySign(
        "An injury to the eye.",
        (MERCK_EMERGENCY,),
        covers=(RedFlag.EYE_INJURY,),
    ),
    GeneralEmergencySign(
        "A suspected broken bone, or a limb that cannot move.",
        (MERCK_EMERGENCY,),
        covers=(RedFlag.LIMB_CANNOT_MOVE,),
    ),
    GeneralEmergencySign(
        "Blood in vomit, or bloody or black tarry stool.",
        (MISSOURI_VOMITING,),
        covers=(RedFlag.BLOOD_IN_VOMIT_OR_STOOL, RedFlag.BLACK_TARRY_STOOL),
    ),
    # Named as a cat's emergency in the line itself as well as in `species`,
    # because an owner who never told us the animal is shown every line.
    GeneralEmergencySign(
        "Straining to urinate while producing little or nothing. In a cat this can be a sign of "
        "urethral obstruction, which Cornell calls a true medical emergency needing immediate "
        "attention when it is suspected.",
        (CORNELL_LUTD, ACVS_URINARY_OBSTRUCTION),
        covers=(RedFlag.UNABLE_TO_URINATE,),
        species=CAT_ONLY,
    ),
    GeneralEmergencySign(
        "A swollen or bloated abdomen with retching that brings nothing up. In a dog this is a "
        "sign of gastric dilatation-volvulus, which Cornell says is fatal without immediate "
        "treatment.",
        (CORNELL_GDV,),
        covers=(RedFlag.BLOATED_ABDOMEN_WITH_RETCHING,),
        species=DOG_ONLY,
    ),
    # "Call as soon as you suspect it" is the helpline's own instruction — it
    # says to call if you THINK your pet has been poisoned, not once signs
    # appear. The earlier wording ("even if your pet still seems well") went
    # further than the emergency page it was shown beside.
    GeneralEmergencySign(
        "Suspected poisoning — the sources say to call as soon as you suspect it, rather than "
        "waiting to see what happens.",
        (MERCK_EMERGENCY, PET_POISON_HELPLINE),
        covers=(RedFlag.SUSPECTED_POISONING,),
    ),
    # The ASPCA names severe trauma from an accident or fall; "an attack", and
    # the warning that follows it, are Merck's trauma page.
    GeneralEmergencySign(
        "Major trauma — hit by a car, a fall, or an attack by another animal. An animal that "
        "seems unhurt can still have serious internal injury.",
        (ASPCA_EMERGENCY, MERCK_TRAUMA),
        covers=(RedFlag.MAJOR_TRAUMA,),
    ),
    # "Heatstroke", not "overheating": both pages name heat STROKE, and neither
    # establishes that being too hot is the same emergency.
    GeneralEmergencySign(
        "Suspected heatstroke.",
        (MERCK_EMERGENCY, ASPCA_EMERGENCY),
        covers=(RedFlag.OVERHEATING,),
    ),
    GeneralEmergencySign("Choking.", (ASPCA_EMERGENCY,), covers=(RedFlag.CHOKING,)),
    # Not "an insect sting": the ASPCA names the sting as a cause a pet MAY
    # need emergency care because of, and its emergency SIGNS are the list
    # above. What belongs here is the reaction.
    GeneralEmergencySign(
        "A sting followed by breathing difficulty, weakness or collapse, pale gums, or a seizure.",
        (ASPCA_EMERGENCY, MERCK_STINGS),
        covers=(RedFlag.INSECT_STING_REACTION,),
    ),
)

class ScreeningBehaviour(str, enum.Enum):
    """What reporting an emergency-screening trigger, on its own, means.

    Two of them, because the form has always had both and only one was
    modelled. "Stung by an insect" is a question we ask, and a sting on its own
    is deliberately NOT an emergency: the ASPCA names a sting among the causes
    a pet MAY need emergency care because of, and never says a sting alone is
    life-threatening. The rule therefore reads sting AND a systemic sign.

    That difference used to live in a test's exception list, where a maintainer
    reading the rule table would never find it, and where the test could only
    say "this flag is allowed not to be red" rather than "here is the predicate
    it is red under". It is a property of the clinical model, so it is declared
    with the model.
    """

    #: Reporting this alone is an emergency.
    EMERGENCY = "emergency"
    #: Reporting this alone is not. It escalates only with `escalates_with`.
    CONDITIONAL = "conditional"


@dataclass(frozen=True)
class EmergencyScreeningTrigger:
    """One emergency question the form asks, and what our model does with it."""

    flag: RedFlag
    behaviour: ScreeningBehaviour
    #: CONDITIONAL only: the signs that turn it into an emergency. Every one of
    #: them must itself appear in `GENERAL_EMERGENCY_SIGNS`, or an owner told
    #: "come back if the reaction starts" has nowhere to read what the reaction
    #: looks like.
    escalates_with: tuple[RedFlag, ...] = ()
    #: The animals this CLAIM covers, where the limit is clinical. GDV is a
    #: condition of dogs; that is a fact about the disease.
    claim_species: frozenset[str] | None = None
    #: Words that must survive into everything the owner reads about this
    #: trigger — the form's label, the reason on the card, and the safety-net
    #: line. Set where the trigger is deliberately narrower than the bare sign,
    #: which is exactly where the three copies drift apart without anyone
    #: noticing: the identifier `rapid_breathing_at_rest` stayed put in all
    #: three places while one of them quietly said "rapid breathing".
    owner_facing_qualifier: str | None = None
    #: Set instead when the scope above is narrower than the clinical trigger
    #: because OUR CITATIONS are species-bound, not because the claim is — the
    #: distinction a reviewer drew about urinary obstruction, and one the model
    #: could not previously express. Names the candidate holding the open
    #: question, so the gap cannot be forgotten and cannot be closed in one
    #: place only.
    citation_bound_to: str | None = None


#: The emergency triggers the intake form asks about, and their behaviour.
#:
#: The form asks these in two questions — "is your pet showing any of these
#: right now?" and "has anything happened to them recently?" — and its own
#: copies of the lists live in `SymptomIntakeForm.tsx`, because the labels and
#: the ordering are a UI decision. What must not be a second opinion is which
#: triggers exist and what each one means, so this is the declaration and
#: `tests/eval/test_safety_invariants.py` checks the form, the rule table and
#: the safety-net list against it.
EMERGENCY_SCREENING: tuple[EmergencyScreeningTrigger, ...] = (
    EmergencyScreeningTrigger(RedFlag.TROUBLE_BREATHING, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(
        RedFlag.RAPID_BREATHING_AT_REST,
        ScreeningBehaviour.EMERGENCY,
        owner_facing_qualifier="while resting",
    ),
    EmergencyScreeningTrigger(RedFlag.COLLAPSE_OR_UNRESPONSIVE, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.PALE_GUMS, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.SEIZURE, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.UNCONTROLLED_BLEEDING, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.SEVERE_PAIN, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.EYE_INJURY, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.LIMB_CANNOT_MOVE, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.BLOOD_IN_VOMIT_OR_STOOL, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.MAJOR_TRAUMA, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.OVERHEATING, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.CHOKING, ScreeningBehaviour.EMERGENCY),
    EmergencyScreeningTrigger(RedFlag.SUSPECTED_POISONING, ScreeningBehaviour.EMERGENCY),
    # Clinically a dog's emergency: Cornell describes GDV as a life-threatening
    # condition of dogs and Merck says it primarily affects large and giant
    # breeds. The narrowing is the claim's, not our library's.
    EmergencyScreeningTrigger(
        RedFlag.BLOATED_ABDOMEN_WITH_RETCHING,
        ScreeningBehaviour.EMERGENCY,
        claim_species=DOG_ONLY,
    ),
    # No longer narrowed. This trigger carried `claim_species=CAT_ONLY` and a
    # `citation_bound_to` pointing at an open candidate, for the reason the
    # field exists: straining while producing nothing is a blockage sign in
    # more than one species, and what was cat-only was our reading list, not
    # the claim. Dogs are now covered by `dog_unable_to_urinate` on ACVS's dog
    # article and Merck's obstruction page, so both qualifiers come off and the
    # trigger means what it always should have: an emergency for either animal.
    EmergencyScreeningTrigger(
        RedFlag.UNABLE_TO_URINATE,
        ScreeningBehaviour.EMERGENCY,
    ),
    # The one conditional trigger. Asked because the reaction is what we screen
    # on; red only with the reaction.
    EmergencyScreeningTrigger(
        RedFlag.INSECT_STING_REACTION,
        ScreeningBehaviour.CONDITIONAL,
        escalates_with=(
            RedFlag.TROUBLE_BREATHING,
            RedFlag.RAPID_BREATHING_AT_REST,
            RedFlag.COLLAPSE_OR_UNRESPONSIVE,
            RedFlag.PALE_GUMS,
            RedFlag.SEIZURE,
            RedFlag.BLOOD_IN_VOMIT_OR_STOOL,
        ),
    ),
)

#: Just the flags, for the parity check against the form.
EMERGENCY_SCREENING_FLAGS: frozenset[RedFlag] = frozenset(
    trigger.flag for trigger in EMERGENCY_SCREENING
)

GENERAL_EMERGENCY_NOTE = (
    "These are our general emergency screening signs and situations, each with the page that "
    "states it. They do not come from the sources behind the result above."
)


ALL_RULES: tuple[Rule, ...] = EMERGENCY_RULES + WEIGHTED_RULES

# Score at or above this is amber; below it is green. Ties round up: the cost of
# an unnecessary check-up is far lower than the cost of a missed problem.
AMBER_THRESHOLD = 3

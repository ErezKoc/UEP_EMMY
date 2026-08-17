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
    RedFlag,
    TimeSinceEating,
    TriageLevel,
    Trend,
)
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
    NotEatingFor,
    SpeciesIs,
    TrendIs,
)
from app.services.triage.rule import Rule
from app.services.triage.sources import (
    ACVS_URINARY_OBSTRUCTION,
    ALL_SPECIES,
    ASPCA_EMERGENCY,
    ASPCA_POISON_CONTROL,
    CAT_ONLY,
    CORNELL_ANOREXIA,
    CORNELL_DIARRHOEA,
    CORNELL_GDV,
    DOG_ONLY,
    MERCK_ACUTE_GLAUCOMA,
    MERCK_ANTERIOR_UVEITIS,
    MERCK_AURICULAR_HEMATOMA,
    MERCK_CORROSIVE_EYE_EXPOSURE,
    MERCK_EMERGENCY,
    MERCK_EYE_ANTI_INFLAMMATORY,
    MERCK_OTITIS_EXTERNA,
    MERCK_OTITIS_MEDIA_INTERNA,
    MISSOURI_VOMITING,
    PET_POISON_HELPLINE,
    Source,
    VCA_ANOREXIA_DOGS,
    VCA_EYE_ISSUES,
    VCA_LIMPING,
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

_EYE_REASON = (
    "Redness and watering are not specific to one condition. A photo cannot rule out corneal damage, "
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
# Emergency rules — any one of these makes the assessment RED on its own.
# --------------------------------------------------------------------------

EMERGENCY_RULES: tuple[Rule, ...] = (
    Rule(
        id="trouble_breathing",
        condition=HasRedFlag(RedFlag.TROUBLE_BREATHING),
        message="Difficulty breathing needs emergency veterinary care.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(MERCK_EMERGENCY, "lists trouble breathing among emergencies needing immediate care"),
            _cite(ASPCA_EMERGENCY, "lists rapid breathing among signs a pet needs emergency care"),
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
        message=_EYE_REASON,
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
        message="Straining to urinate while producing little or nothing can mean a blockage, which is an emergency.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                ACVS_URINARY_OBSTRUCTION,
                "states urinary obstruction requires emergency treatment and can be fatal in 3-6 days;"
                " affected cats strain in the litter box without producing urine",
            ),
        ),
        applies_to_species=CAT_ONLY,
        reviewer_note=(
            "ACVS describes urethral obstruction in male cats. This rule is therefore deliberately"
            " limited to cats until a suitable source for other species is reviewed."
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
        id="gi_signs_with_extreme_lethargy",
        condition=All(
            (
                Any_((HasRedFlag(RedFlag.VOMITING), HasRedFlag(RedFlag.DIARRHOEA))),
                HasRedFlag(RedFlag.EXTREME_LETHARGY),
            )
        ),
        message=(
            "Vomiting or diarrhoea together with marked lethargy needs prompt veterinary attention."
        ),
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                MISSOURI_VOMITING,
                "lists an extremely lethargic or depressed animal among the situations warranting"
                " more immediate veterinary attention in a vomiting or diarrhoeic animal",
            ),
        ),
        reviewer_note=(
            "Missouri frames its escalation list inside a vomiting/diarrhoea presentation, so this"
            " rule requires one of those signs. Lethargy reported on its own stays graded, because"
            " no source we hold addresses it alone."
        ),
    ),
    Rule(
        id="prolonged_vomiting",
        condition=All(
            (
                HasRedFlag(RedFlag.VOMITING),
                DurationIn((Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH)),
            )
        ),
        message="Vomiting that continues beyond a day needs veterinary attention.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                MISSOURI_VOMITING,
                "lists profuse vomiting many times in a day, or attempts continuing more than 24 hours,"
                " among situations warranting immediate attention",
            ),
        ),
        reviewer_note="Our shortest duration band is 'today', so anything longer is treated as beyond 24 hours.",
    ),
    Rule(
        id="major_trauma",
        condition=HasRedFlag(RedFlag.MAJOR_TRAUMA),
        message="After a car accident, a fall, or an attack, your pet needs to be seen even if they seem fine.",
        level_override=TriageLevel.RED,
        citations=(
            _cite(
                ASPCA_EMERGENCY,
                "states pets may need emergency care because of severe trauma caused by an accident or fall",
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
        citations=(_cite(ASPCA_EMERGENCY, "lists choking among life-threatening situations"),),
    ),
    Rule(
        id="insect_sting_reaction",
        condition=HasRedFlag(RedFlag.INSECT_STING_REACTION),
        message="A sting with swelling or breathing changes needs emergency care.",
        level_override=TriageLevel.RED,
        citations=(_cite(ASPCA_EMERGENCY, "lists an insect sting among life-threatening situations"),),
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
                " and facial nerve paralysis among signs of middle or inner ear disease, and states"
                " that treatment is most successful when started early in the disease course",
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
        reviewer_note=(
            "Missouri frames lethargy alongside vomiting, so lethargy WITH a gastrointestinal sign"
            " is now a separate emergency rule (gi_signs_with_extreme_lethargy). This rule covers"
            " lethargy reported on its own, which no source we hold addresses. Should isolated"
            " lethargy be graded like this, or does it warrant same-day care?"
        ),
    ),
    Rule(
        id="increased_thirst",
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
        condition=Any_((ConcernIs(Concern.EYES), BodyAreaIn((BodyArea.EYE,)))),
        message=_EYE_REASON,
        weight=3,
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
        reviewer_note=(
            "This pathway is for a new eye concern without a listed urgent warning sign. Injury,"
            " pain, clouding, pupil or vision change, bulging, abnormal discharge, chemical exposure,"
            " or rapid worsening are handled by the same-day urgent rule."
        ),
    ),
    Rule(
        id="persistent_or_worsening_ear_problem",
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
        reviewer_note=(
            "EXTRAPOLATION: the sources support veterinary examination and cause-directed treatment"
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
        citations=(
            _cite(CORNELL_DIARRHOEA, "states that if loose stool lasts more than two days, call the vet"),
        ),
        applies_to_species=DOG_ONLY,
        reviewer_note="Our '2–7 days' band starts at day two, slightly earlier than Cornell's wording.",
    ),
)


ALL_RULES: tuple[Rule, ...] = EMERGENCY_RULES + WEIGHTED_RULES

# Score at or above this is amber; below it is green. Ties round up: the cost of
# an unnecessary check-up is far lower than the cost of a missed problem.
AMBER_THRESHOLD = 3

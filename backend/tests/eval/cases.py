"""The evaluation set: hand-written vignettes, boundaries, and generated cases.

Reproducible by construction — the generated portion uses a fixed seed
(`GENERATOR_SEED`) and no wall-clock or environment input, so `CASES` is byte
for byte the same on every run and on every machine.

Expected levels are never written down here. They are computed by `oracle.py`
from `evidence.py`, so a case cannot be quietly relabelled to make the engine
look right.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import product

from app.models.animal import AgeCategory
from app.schemas.triage import (
    BodyArea,
    Concern,
    Duration,
    ItchLevel,
    RedFlag,
    SkinSpread,
    SymptomIntake,
    TimeSinceEating,
    Trend,
)

GENERATOR_SEED = 20260816

VIGNETTE = "vignette"
BOUNDARY = "boundary"
GENERATED = "generated"

UNSUPPORTED_SPECIES = ("rabbit", "ferret", "guinea pig", "parrot", "bearded dragon", "horse")


@dataclass(frozen=True)
class Case:
    id: str
    origin: str
    description: str
    intake: SymptomIntake


def _v(case_id: str, description: str, **intake) -> Case:
    return Case(case_id, VIGNETTE, description, SymptomIntake(**intake))


def _b(case_id: str, description: str, **intake) -> Case:
    return Case(case_id, BOUNDARY, description, SymptomIntake(**intake))


# ===========================================================================
# 1. Hand-written vignettes — realistic presentations an owner might describe.
# ===========================================================================

VIGNETTES: tuple[Case, ...] = (
    # --- unambiguous emergencies, dogs -------------------------------------
    _v(
        "vig_dog_dyspnoea",
        "Adult Labrador breathing hard at rest with an extended neck, worse over the afternoon.",
        concern=Concern.BREATHING, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.TROUBLE_BREATHING], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_gdv",
        "Deep-chested Great Dane, hard swollen belly, retching without bringing anything up.",
        concern=Concern.DIGESTION, body_area=BodyArea.BELLY, duration=Duration.TODAY,
        trend=Trend.WORSENING, red_flags=[RedFlag.BLOATED_ABDOMEN_WITH_RETCHING],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_heatstroke",
        "Bulldog collapsed after a walk on a hot day, panting hard and drooling.",
        concern=Concern.OTHER, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.OVERHEATING, RedFlag.COLLAPSE_OR_UNRESPONSIVE],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_hit_by_car",
        "Terrier hit by a car, walking but the owner is unsure about internal injury.",
        concern=Concern.OTHER, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.MAJOR_TRAUMA], species="dog", age_category=AgeCategory.YOUNG,
    ),
    _v(
        "vig_dog_chocolate",
        "Spaniel ate a box of dark chocolate an hour ago and currently seems fine.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.SUSPECTED_POISONING], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_seizure_first",
        "Beagle had a first witnessed seizure lasting about a minute.",
        concern=Concern.BEHAVIOUR, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.SEIZURE], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_haematemesis",
        "Collie vomiting coffee-grounds material since yesterday, quiet in himself.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, trend=Trend.WORSENING,
        red_flags=[RedFlag.VOMITING, RedFlag.BLOOD_IN_VOMIT_OR_STOOL],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_melaena",
        "Older Rottweiler passing black tarry stool for two days.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.BLACK_TARRY_STOOL, RedFlag.DIARRHOEA],
        species="dog", age_category=AgeCategory.SENIOR,
    ),
    _v(
        "vig_dog_parvo_picture",
        "Unvaccinated puppy with diarrhoea, off food and flat since this morning.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.DIARRHOEA, RedFlag.NOT_EATING, RedFlag.EXTREME_LETHARGY],
        time_since_eating=TimeSinceEating.H12_TO_24H,
        species="dog", age_category=AgeCategory.BABY,
    ),
    _v(
        "vig_dog_open_fracture",
        "Whippet caught a leg in a fence and will not move it at all.",
        concern=Concern.MOBILITY, body_area=BodyArea.LEGS_OR_PAWS, duration=Duration.TODAY,
        trend=Trend.WORSENING, red_flags=[RedFlag.LIMB_CANNOT_MOVE, RedFlag.SEVERE_PAIN],
        weight_bearing=False, species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_bee_sting_face",
        "Boxer stung on the muzzle, face swelling and breathing noisier.",
        concern=Concern.OTHER, body_area=BodyArea.HEAD_OR_FACE, duration=Duration.TODAY,
        trend=Trend.WORSENING, red_flags=[RedFlag.INSECT_STING_REACTION, RedFlag.TROUBLE_BREATHING],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_choking_ball",
        "Retriever coughing and pawing at his mouth after chewing a ball.",
        concern=Concern.BREATHING, body_area=BodyArea.MOUTH, duration=Duration.TODAY,
        trend=Trend.WORSENING, red_flags=[RedFlag.CHOKING], species="dog",
        age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_pale_gums_bleeding",
        "Senior dog with a bleeding mass that will not stop and very pale gums.",
        concern=Concern.OTHER, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.PALE_GUMS, RedFlag.UNCONTROLLED_BLEEDING],
        species="dog", age_category=AgeCategory.SENIOR,
    ),

    # --- unambiguous emergencies, cats -------------------------------------
    _v(
        "vig_cat_blocked_bladder",
        "Male cat in and out of the litter tray all morning, straining, nothing produced.",
        concern=Concern.URINATION, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.UNABLE_TO_URINATE], species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_anorexia_36h",
        "Indoor cat has eaten nothing since the day before yesterday, hiding.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, trend=Trend.WORSENING,
        red_flags=[RedFlag.NOT_EATING], time_since_eating=TimeSinceEating.OVER_24H,
        species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_kitten_anorexia_14h",
        "Five-week-old kitten refusing the bottle since last night.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.NOT_EATING], time_since_eating=TimeSinceEating.H12_TO_24H,
        species="cat", age_category=AgeCategory.BABY,
    ),
    _v(
        "vig_cat_lily_exposure",
        "Cat seen chewing a lily leaf; no signs yet.",
        concern=Concern.OTHER, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.SUSPECTED_POISONING], species="cat", age_category=AgeCategory.YOUNG,
    ),
    _v(
        "vig_cat_saddle_thrombus",
        "Cat suddenly cannot use her back legs and is crying; gums look pale.",
        concern=Concern.MOBILITY, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.LIMB_CANNOT_MOVE, RedFlag.SEVERE_PAIN, RedFlag.PALE_GUMS],
        weight_bearing=False, species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_dyspnoea_openmouth",
        "Cat open-mouth breathing on the floor, will not settle.",
        concern=Concern.BREATHING, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.TROUBLE_BREATHING], species="cat", age_category=AgeCategory.SENIOR,
    ),
    _v(
        "vig_cat_fall_from_window",
        "Cat fell from a third-floor window, now quiet but walking.",
        concern=Concern.OTHER, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.MAJOR_TRAUMA], species="cat", age_category=AgeCategory.YOUNG,
    ),
    _v(
        "vig_senior_cat_vomiting_chronic_kidney",
        "Senior cat with known kidney disease vomiting since this morning.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.VOMITING], has_chronic_illness=True,
        species="cat", age_category=AgeCategory.SENIOR,
    ),

    # --- eye presentations --------------------------------------------------
    _v(
        "vig_dog_glaucoma_picture",
        "Pug with a painful, cloudy, bulging eye that appeared overnight.",
        concern=Concern.EYES, body_area=BodyArea.EYE, duration=Duration.TODAY,
        trend=Trend.WORSENING,
        red_flags=[RedFlag.EYE_PAIN_OR_CLOSED, RedFlag.EYE_CLOUDY_OR_BLUE,
                   RedFlag.EYE_BULGING_OR_SEVERE_SWELLING],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_conjunctivitis_mild",
        "Cat with a slightly watery, pink eye for a couple of days, eating normally.",
        concern=Concern.EYES, body_area=BodyArea.EYE, duration=Duration.DAYS_2_7,
        trend=Trend.UNCHANGED, species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_bleach_splash_eye",
        "Cleaning product splashed into a dog's eye ten minutes ago.",
        concern=Concern.EYES, body_area=BodyArea.EYE, duration=Duration.TODAY,
        trend=Trend.WORSENING, red_flags=[RedFlag.EYE_CHEMICAL_EXPOSURE],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_corneal_scratch",
        "Dog came back from the woods holding one eye shut and rubbing it.",
        concern=Concern.EYES, body_area=BodyArea.EYE, duration=Duration.TODAY,
        trend=Trend.WORSENING, red_flags=[RedFlag.EYE_PAIN_OR_CLOSED],
        species="dog", age_category=AgeCategory.YOUNG,
    ),
    _v(
        "vig_cat_eye_injury_cat_fight",
        "Cat came home from a fight with a damaged eye.",
        concern=Concern.EYES, body_area=BodyArea.EYE, duration=Duration.TODAY,
        trend=Trend.WORSENING, red_flags=[RedFlag.EYE_INJURY],
        species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_purulent_eye_discharge",
        "Dog with thick yellow-green discharge from one eye for three days.",
        concern=Concern.EYES, body_area=BodyArea.EYE, duration=Duration.DAYS_2_7,
        trend=Trend.WORSENING, red_flags=[RedFlag.EYE_DISCHARGE_YELLOW_GREEN_OR_BLOODY],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_eye_signs_reported_without_eye_concern",
        "Owner picks 'other' as the concern but reports one pupil much larger and bumping into things.",
        concern=Concern.OTHER, body_area=BodyArea.HEAD_OR_FACE, duration=Duration.TODAY,
        trend=Trend.WORSENING, red_flags=[RedFlag.UNEQUAL_PUPILS_OR_VISION_CHANGE],
        species="dog", age_category=AgeCategory.SENIOR,
    ),
    _v(
        "vig_chemical_eye_without_eye_concern",
        "Owner picks 'other'; reports drain cleaner splashed in the cat's eye.",
        concern=Concern.OTHER, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.EYE_CHEMICAL_EXPOSURE], species="cat", age_category=AgeCategory.ADULT,
    ),

    # --- ear presentations --------------------------------------------------
    _v(
        "vig_dog_otitis_externa",
        "Cocker Spaniel shaking his head, smelly brown discharge, sore for a week.",
        concern=Concern.EARS, body_area=BodyArea.EAR, duration=Duration.WEEKS_1_4,
        trend=Trend.WORSENING,
        red_flags=[RedFlag.EAR_HEAD_SHAKING_OR_SCRATCHING, RedFlag.EAR_ODOR,
                   RedFlag.EAR_DISCHARGE, RedFlag.EAR_PAIN],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_vestibular_signs",
        "Cat with a head tilt, falling to one side and flicking eyes since this morning.",
        concern=Concern.EARS, body_area=BodyArea.EAR, duration=Duration.TODAY,
        trend=Trend.WORSENING,
        red_flags=[RedFlag.EAR_HEAD_TILT, RedFlag.EAR_BALANCE_PROBLEMS,
                   RedFlag.EAR_RAPID_EYE_MOVEMENTS],
        species="cat", age_category=AgeCategory.SENIOR,
    ),
    _v(
        "vig_dog_aural_haematoma",
        "Labrador's ear flap has ballooned up after days of scratching.",
        concern=Concern.EARS, body_area=BodyArea.EAR, duration=Duration.DAYS_2_7,
        trend=Trend.WORSENING,
        red_flags=[RedFlag.EAR_FLAP_SWELLING, RedFlag.EAR_HEAD_SHAKING_OR_SCRATCHING],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_grass_seed_ear",
        "Dog started shaking his head violently right after a walk through long grass.",
        concern=Concern.EARS, body_area=BodyArea.EAR, duration=Duration.TODAY,
        trend=Trend.WORSENING,
        red_flags=[RedFlag.EAR_FOREIGN_BODY, RedFlag.EAR_HEAD_SHAKING_OR_SCRATCHING],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_ear_signs_without_ear_concern",
        "Owner picks 'behaviour'; reports the dog is circling with a head tilt.",
        concern=Concern.BEHAVIOUR, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.EAR_HEAD_TILT, RedFlag.EAR_BALANCE_PROBLEMS],
        species="dog", age_category=AgeCategory.SENIOR,
    ),
    _v(
        "vig_cat_facial_droop_no_ear_concern",
        "Owner picks 'other'; one side of the cat's face has dropped and she cannot hear.",
        concern=Concern.OTHER, body_area=BodyArea.HEAD_OR_FACE, duration=Duration.DAYS_2_7,
        trend=Trend.WORSENING,
        red_flags=[RedFlag.EAR_FACIAL_DROOP, RedFlag.EAR_SUDDEN_HEARING_LOSS],
        species="cat", age_category=AgeCategory.SENIOR,
    ),

    # --- graded / non-emergency --------------------------------------------
    _v(
        "vig_dog_lame_five_days",
        "Spaniel limping on a front leg for five days, still weight bearing, bright.",
        concern=Concern.MOBILITY, body_area=BodyArea.LEGS_OR_PAWS, duration=Duration.DAYS_2_7,
        trend=Trend.UNCHANGED, weight_bearing=True, species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_lame_today_only",
        "Dog came back from the park limping this afternoon, still using the leg.",
        concern=Concern.MOBILITY, body_area=BodyArea.LEGS_OR_PAWS, duration=Duration.TODAY,
        trend=Trend.UNCHANGED, weight_bearing=True, species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_non_weight_bearing_three_days",
        "Dog has been holding a hind leg up completely for three days.",
        concern=Concern.MOBILITY, body_area=BodyArea.LEGS_OR_PAWS, duration=Duration.DAYS_2_7,
        trend=Trend.UNCHANGED, weight_bearing=False, species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_polydipsia",
        "Middle-aged dog emptying the water bowl and asking to go out at night, three weeks.",
        concern=Concern.URINATION, duration=Duration.WEEKS_1_4, trend=Trend.WORSENING,
        red_flags=[RedFlag.DRINKING_MUCH_MORE], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_polydipsia_senior",
        "Senior cat drinking far more than usual for a month, weight dropping.",
        concern=Concern.URINATION, duration=Duration.OVER_MONTH, trend=Trend.WORSENING,
        red_flags=[RedFlag.DRINKING_MUCH_MORE], species="cat", age_category=AgeCategory.SENIOR,
    ),
    _v(
        "vig_dog_off_food_one_meal",
        "Dog skipped breakfast but is otherwise bright and playing.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.NOT_EATING], time_since_eating=TimeSinceEating.UNDER_12H,
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_off_food_one_meal",
        "Cat skipped breakfast but is otherwise bright — the feline mirror of the dog case.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.NOT_EATING], time_since_eating=TimeSinceEating.UNDER_12H,
        species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_not_eating_duration_unknown",
        "Cat has gone off food; owner does not know how long it has been.",
        concern=Concern.DIGESTION, trend=Trend.WORSENING, red_flags=[RedFlag.NOT_EATING],
        species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_diarrhoea_four_days",
        "Dog with soft stool for four days, eating and bright.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.DIARRHOEA], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_diarrhoea_today_only",
        "Dog had two loose stools today after scavenging; otherwise well.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.DIARRHOEA], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_vomited_once",
        "Adult dog vomited once this morning and then ate normally.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.IMPROVING,
        red_flags=[RedFlag.VOMITING], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_vomiting_three_days",
        "Dog vomiting on and off for three days, still drinking.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.VOMITING], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_vomiting_plus_flat",
        "Dog vomited several times today and is now very flat and unresponsive to play.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.VOMITING, RedFlag.EXTREME_LETHARGY],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_vomiting_plus_flat",
        "Cat vomited repeatedly today and is now hiding and very flat.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.VOMITING, RedFlag.EXTREME_LETHARGY],
        species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_lethargy_alone",
        "Dog has been unusually flat all day; no other signs the owner can name.",
        concern=Concern.BEHAVIOUR, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.EXTREME_LETHARGY], species="dog", age_category=AgeCategory.ADULT,
    ),

    # --- reported concern with no flag ticked ------------------------------
    _v(
        "vig_dog_breathing_concern_no_flag",
        "Owner chooses 'breathing' and says it is getting worse, but ticks no red flag.",
        concern=Concern.BREATHING, duration=Duration.TODAY, trend=Trend.WORSENING,
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_urination_concern_no_flag",
        "Owner chooses 'urination', worsening for two days, ticks no red flag.",
        concern=Concern.URINATION, duration=Duration.DAYS_2_7, trend=Trend.WORSENING,
        species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_skin_lump_month",
        "Dog has a lump on the flank that has been there over a month and is growing.",
        concern=Concern.SKIN_OR_COAT, body_area=BodyArea.BACK, duration=Duration.OVER_MONTH,
        trend=Trend.WORSENING, species="dog", age_category=AgeCategory.SENIOR,
    ),
    _v(
        "vig_cat_behaviour_change_senior",
        "Senior cat yowling at night and hiding for weeks.",
        concern=Concern.BEHAVIOUR, duration=Duration.WEEKS_1_4, trend=Trend.WORSENING,
        species="cat", age_category=AgeCategory.SENIOR,
    ),

    # --- breed-only ---------------------------------------------------------
    _v("vig_breed_only_dog", "Owner wants a breed guess for a rescue dog.",
       concern=Concern.BREED_ONLY, species="dog", age_category=AgeCategory.ADULT),
    _v("vig_breed_only_cat", "Owner wants a breed guess for a cat.",
       concern=Concern.BREED_ONLY, species="cat", age_category=AgeCategory.YOUNG),
    _v("vig_breed_only_no_species", "Owner wants a breed guess and gave no species.",
       concern=Concern.BREED_ONLY),
    _v(
        "vig_breed_only_with_seizure",
        "Owner opens the breed tool but also reports the dog had a seizure.",
        concern=Concern.BREED_ONLY, red_flags=[RedFlag.SEIZURE],
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_breed_only_with_poisoning_cat",
        "Owner opens the breed tool but also reports suspected poisoning.",
        concern=Concern.BREED_ONLY, red_flags=[RedFlag.SUSPECTED_POISONING],
        species="cat", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_breed_only_with_trouble_breathing_rabbit",
        "Breed tool opened for a rabbit, with laboured breathing also reported.",
        concern=Concern.BREED_ONLY, red_flags=[RedFlag.TROUBLE_BREATHING], species="rabbit",
    ),

    # --- species unknown ----------------------------------------------------
    _v(
        "vig_unknown_species_poisoning",
        "Owner answers 'not sure' to species and reports poisoning with bloody vomit.",
        concern=Concern.DIGESTION, body_area=BodyArea.BELLY, trend=Trend.WORSENING,
        red_flags=[RedFlag.SUSPECTED_POISONING, RedFlag.BLOOD_IN_VOMIT_OR_STOOL,
                   RedFlag.VOMITING, RedFlag.EXTREME_LETHARGY],
        time_since_eating=TimeSinceEating.OVER_24H, has_chronic_illness=True,
    ),
    _v(
        "vig_unknown_species_seizure",
        "No pet linked, owner reports a seizure.",
        concern=Concern.BEHAVIOUR, duration=Duration.TODAY, red_flags=[RedFlag.SEIZURE],
    ),
    _v(
        "vig_unknown_species_not_eating_24h",
        "No species given; the animal has not eaten for over a day.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, red_flags=[RedFlag.NOT_EATING],
        time_since_eating=TimeSinceEating.OVER_24H,
    ),

    # --- unsupported species ------------------------------------------------
    _v(
        "vig_rabbit_gut_stasis",
        "Rabbit has not eaten or passed droppings since yesterday and is hunched.",
        concern=Concern.DIGESTION, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.NOT_EATING, RedFlag.EXTREME_LETHARGY],
        time_since_eating=TimeSinceEating.H12_TO_24H, species="rabbit",
        age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_rabbit_seizure",
        "Rabbit is having a seizure.",
        concern=Concern.BEHAVIOUR, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.SEIZURE], species="rabbit", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_ferret_collapse",
        "Ferret collapsed and has pale gums.",
        concern=Concern.OTHER, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.COLLAPSE_OR_UNRESPONSIVE, RedFlag.PALE_GUMS],
        species="ferret", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_parrot_bleeding",
        "Parrot has broken a blood feather and is bleeding heavily.",
        concern=Concern.OTHER, duration=Duration.TODAY, trend=Trend.WORSENING,
        red_flags=[RedFlag.UNCONTROLLED_BLEEDING], species="parrot",
    ),
    _v(
        "vig_guinea_pig_skin_month",
        "Guinea pig has had scurfy patches for over a month, getting worse.",
        concern=Concern.SKIN_OR_COAT, duration=Duration.OVER_MONTH, trend=Trend.WORSENING,
        species="guinea pig", age_category=AgeCategory.ADULT,
    ),

    # --- skin and coat, the pathway that used to abstain ---------------------
    _v(
        "vig_dog_itchy_red_paws_week",
        "The reported case: dog, skin or coat, legs or paws, 2-7 days, about the same — but "
        "now describing the skin as itchy and red, which is what the rules read.",
        concern=Concern.SKIN_OR_COAT, body_area=BodyArea.LEGS_OR_PAWS,
        duration=Duration.DAYS_2_7, trend=Trend.UNCHANGED,
        red_flags=[RedFlag.SKIN_ITCHING, RedFlag.SKIN_REDNESS],
        itch_level=ItchLevel.FREQUENT, skin_spread=SkinSpread.SEVERAL_AREAS,
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_paw_problem_undescribed",
        "The same case with the skin never described: no lesion, no itch level. Nothing in the "
        "evidence base can be matched, and the engine must still abstain rather than guess.",
        concern=Concern.SKIN_OR_COAT, body_area=BodyArea.LEGS_OR_PAWS,
        duration=Duration.DAYS_2_7, trend=Trend.UNCHANGED,
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_oozing_smelly_skin_fold",
        "Dog with a raw, oozing, foul-smelling skin fold for a fortnight.",
        concern=Concern.SKIN_OR_COAT, body_area=BodyArea.BELLY, duration=Duration.WEEKS_1_4,
        trend=Trend.WORSENING,
        red_flags=[
            RedFlag.SKIN_OPEN_WOUND, RedFlag.SKIN_DISCHARGE_OR_PUS, RedFlag.SKIN_ODOR,
        ],
        itch_level=ItchLevel.OCCASIONAL, skin_spread=SkinSpread.ONE_AREA,
        species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_scaly_patches_owner_itchy_too",
        "Cat with crusty bald patches; the owner has developed an itchy patch on their arm.",
        concern=Concern.SKIN_OR_COAT, duration=Duration.WEEKS_1_4, trend=Trend.WORSENING,
        red_flags=[
            RedFlag.SKIN_HAIR_LOSS, RedFlag.SKIN_SCABS_OR_FLAKING, RedFlag.SKIN_CONTAGION,
        ],
        itch_level=ItchLevel.OCCASIONAL, skin_spread=SkinSpread.SEVERAL_AREAS,
        species="cat", age_category=AgeCategory.YOUNG,
    ),
    _v(
        "vig_dog_cannot_stop_scratching",
        "Dog scratching so constantly it cannot settle, with nothing yet visible on the skin.",
        concern=Concern.SKIN_OR_COAT, body_area=BodyArea.ALL_OVER, duration=Duration.DAYS_2_7,
        trend=Trend.WORSENING, itch_level=ItchLevel.CANNOT_SETTLE,
        skin_spread=SkinSpread.WIDESPREAD, species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_dog_paw_lick_routed_to_lameness",
        "Paw problem the owner routed to limping rather than skin: the leg is the issue, not "
        "the skin on it.",
        concern=Concern.MOBILITY, body_area=BodyArea.LEGS_OR_PAWS, duration=Duration.DAYS_2_7,
        trend=Trend.UNCHANGED, weight_bearing=True, species="dog",
        age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_cat_new_lump_not_bothering",
        "Cat with a new lump on the flank that does not seem to bother them.",
        concern=Concern.SKIN_OR_COAT, body_area=BodyArea.BACK, duration=Duration.WEEKS_1_4,
        trend=Trend.UNCHANGED, red_flags=[RedFlag.SKIN_LUMP], itch_level=ItchLevel.NONE,
        skin_spread=SkinSpread.ONE_AREA, species="cat", age_category=AgeCategory.SENIOR,
    ),

    # --- messy input --------------------------------------------------------
    _v(
        "vig_species_with_whitespace",
        "Species arrives as ' cat ' from an upstream field that was not trimmed.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, red_flags=[RedFlag.NOT_EATING],
        time_since_eating=TimeSinceEating.OVER_24H, species=" cat ",
        age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_species_uppercase",
        "Species arrives as 'CAT' from an upstream field.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, red_flags=[RedFlag.NOT_EATING],
        time_since_eating=TimeSinceEating.OVER_24H, species="CAT",
        age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_species_titlecase_dog",
        "Species arrives as 'Dog' from an upstream field.",
        concern=Concern.DIGESTION, red_flags=[RedFlag.NOT_EATING], species="Dog",
        age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_age_unknown_with_vomiting",
        "Age category is 'unknown' and the dog has been vomiting for days.",
        concern=Concern.DIGESTION, duration=Duration.DAYS_2_7, red_flags=[RedFlag.VOMITING],
        species="dog", age_category=AgeCategory.UNKNOWN,
    ),
    _v(
        "vig_conflicting_improving_emergency",
        "Owner says things are improving but also reports uncontrolled bleeding.",
        concern=Concern.SKIN_OR_COAT, duration=Duration.TODAY, trend=Trend.IMPROVING,
        red_flags=[RedFlag.UNCONTROLLED_BLEEDING], species="dog", age_category=AgeCategory.ADULT,
    ),
    _v(
        "vig_everything_at_once",
        "Panicking owner ticks nearly every box at once.",
        concern=Concern.OTHER, body_area=BodyArea.ALL_OVER, duration=Duration.TODAY,
        trend=Trend.WORSENING,
        red_flags=list(RedFlag), time_since_eating=TimeSinceEating.OVER_24H,
        has_chronic_illness=True, weight_bearing=False, species="dog",
        age_category=AgeCategory.SENIOR,
    ),
    _v(
        "vig_nothing_at_all",
        "Empty form submitted with no answers at all.",
    ),
)


# ===========================================================================
# 2. Boundary cases — each evidence threshold, just under and just over.
# ===========================================================================

def _boundary_cases() -> tuple[Case, ...]:
    cases: list[Case] = []

    # Cornell feline anorexia: 24h for a mature cat, 12h for a young kitten.
    for species, age, bucket in product(
        ("cat", "dog", None),
        (AgeCategory.BABY, AgeCategory.YOUNG, AgeCategory.ADULT, AgeCategory.SENIOR,
         AgeCategory.UNKNOWN, None),
        (TimeSinceEating.UNDER_12H, TimeSinceEating.H12_TO_24H, TimeSinceEating.OVER_24H, None),
    ):
        cases.append(
            _b(
                f"bnd_anorexia_{species or 'unknown'}_{age.value if age else 'none'}_"
                f"{bucket.value if bucket else 'none'}",
                "Anorexia threshold boundary: "
                f"species={species}, age={age.value if age else None}, "
                f"time_since_eating={bucket.value if bucket else None}.",
                concern=Concern.DIGESTION, red_flags=[RedFlag.NOT_EATING],
                time_since_eating=bucket, species=species, age_category=age,
            )
        )

    # Missouri vomiting: the 'today' band versus everything longer, crossed with
    # the fragile-patient clause.
    for duration, age, chronic in product(
        (Duration.TODAY, Duration.DAYS_2_7, Duration.WEEKS_1_4, Duration.OVER_MONTH, None),
        (AgeCategory.BABY, AgeCategory.ADULT, AgeCategory.SENIOR, None),
        (True, False, None),
    ):
        cases.append(
            _b(
                f"bnd_vomiting_{duration.value if duration else 'none'}_"
                f"{age.value if age else 'none'}_chronic{chronic}",
                f"Vomiting duration/fragility boundary: duration={duration}, age={age}, "
                f"chronic={chronic}.",
                concern=Concern.DIGESTION, duration=duration, red_flags=[RedFlag.VOMITING],
                has_chronic_illness=chronic, species="dog", age_category=age,
            )
        )

    # Cornell diarrhoea: the two-day line, and the anorexia/lethargy red flags.
    for species, duration, extra in product(
        ("dog", "cat"),
        (Duration.TODAY, Duration.DAYS_2_7, None),
        ((), (RedFlag.NOT_EATING,), (RedFlag.EXTREME_LETHARGY,)),
    ):
        cases.append(
            _b(
                f"bnd_diarrhoea_{species}_{duration.value if duration else 'none'}_"
                f"{'_'.join(f.value for f in extra) or 'alone'}",
                f"Diarrhoea boundary: species={species}, duration={duration}, extra={extra}.",
                concern=Concern.DIGESTION, duration=duration,
                red_flags=[RedFlag.DIARRHOEA, *extra], species=species,
                age_category=AgeCategory.ADULT,
            )
        )

    # VCA lameness: the 24-hour line, crossed with weight bearing and species.
    for species, duration, bearing in product(
        ("dog", "cat", None),
        (Duration.TODAY, Duration.DAYS_2_7, Duration.WEEKS_1_4, None),
        (True, False, None),
    ):
        cases.append(
            _b(
                f"bnd_lameness_{species or 'unknown'}_{duration.value if duration else 'none'}_"
                f"bearing{bearing}",
                f"Lameness boundary: species={species}, duration={duration}, "
                f"weight_bearing={bearing}.",
                concern=Concern.MOBILITY, body_area=BodyArea.LEGS_OR_PAWS, duration=duration,
                weight_bearing=bearing, species=species, age_category=AgeCategory.ADULT,
            )
        )

    # Every eye sign, with and without the eye concern that gates the rule.
    eye_flags = (
        RedFlag.EYE_INJURY, RedFlag.EYE_PAIN_OR_CLOSED, RedFlag.EYE_CLOUDY_OR_BLUE,
        RedFlag.UNEQUAL_PUPILS_OR_VISION_CHANGE, RedFlag.EYE_BULGING_OR_SEVERE_SWELLING,
        RedFlag.EYE_DISCHARGE_YELLOW_GREEN_OR_BLOODY, RedFlag.EYE_CHEMICAL_EXPOSURE,
    )
    for flag, in_context in product(eye_flags, (True, False)):
        cases.append(
            _b(
                f"bnd_eye_{flag.value}_{'in' if in_context else 'out'}_context",
                f"Eye sign {flag.value} reported "
                f"{'with' if in_context else 'without'} an eye concern or body area.",
                concern=Concern.EYES if in_context else Concern.OTHER,
                body_area=BodyArea.EYE if in_context else BodyArea.HEAD_OR_FACE,
                duration=Duration.TODAY, red_flags=[flag], species="dog",
                age_category=AgeCategory.ADULT,
            )
        )

    # Every ear sign, with and without the ear concern that gates the rule.
    ear_flags = tuple(flag for flag in RedFlag if flag.value.startswith("ear_"))
    for flag, in_context in product(ear_flags, (True, False)):
        cases.append(
            _b(
                f"bnd_ear_{flag.value}_{'in' if in_context else 'out'}_context",
                f"Ear sign {flag.value} reported "
                f"{'with' if in_context else 'without'} an ear concern or body area.",
                concern=Concern.EARS if in_context else Concern.OTHER,
                body_area=BodyArea.EAR if in_context else BodyArea.HEAD_OR_FACE,
                duration=Duration.TODAY, red_flags=[flag], species="dog",
                age_category=AgeCategory.ADULT,
            )
        )

    # Every emergency sign on its own, for each species position, with nothing
    # else reported — the barest possible presentation of each rule.
    for flag, species in product(
        sorted(
            {
                RedFlag.TROUBLE_BREATHING, RedFlag.SEVERE_PAIN, RedFlag.UNCONTROLLED_BLEEDING,
                RedFlag.SUSPECTED_POISONING, RedFlag.LIMB_CANNOT_MOVE, RedFlag.SEIZURE,
                RedFlag.COLLAPSE_OR_UNRESPONSIVE, RedFlag.PALE_GUMS, RedFlag.MAJOR_TRAUMA,
                RedFlag.CHOKING, RedFlag.INSECT_STING_REACTION, RedFlag.OVERHEATING,
                RedFlag.UNABLE_TO_URINATE, RedFlag.BLOATED_ABDOMEN_WITH_RETCHING,
                RedFlag.BLOOD_IN_VOMIT_OR_STOOL, RedFlag.BLACK_TARRY_STOOL,
                RedFlag.DRINKING_MUCH_MORE, RedFlag.EXTREME_LETHARGY,
            },
            key=lambda f: f.value,
        ),
        ("dog", "cat", None, "rabbit"),
    ):
        cases.append(
            _b(
                f"bnd_solo_{flag.value}_{species or 'unknown'}",
                f"{flag.value} reported alone for species={species}.",
                concern=Concern.OTHER, red_flags=[flag], species=species,
                age_category=AgeCategory.ADULT,
            )
        )

    # Every concern with no red flag at all, for each species position — the
    # "owner described something we have no rule for" family.
    for concern, species in product(Concern, ("dog", "cat", None, "rabbit")):
        cases.append(
            _b(
                f"bnd_bare_concern_{concern.value}_{species or 'unknown'}",
                f"Concern {concern.value} reported alone for species={species}.",
                concern=concern, duration=Duration.DAYS_2_7, trend=Trend.WORSENING,
                species=species, age_category=AgeCategory.ADULT,
            )
        )

    return tuple(cases)


BOUNDARY_CASES = _boundary_cases()


# ===========================================================================
# 3. Generated cases — seeded systematic sampling of the intake space.
# ===========================================================================

_SPECIES_POOL = ("dog", "dog", "cat", "cat", None, "unknown", *UNSUPPORTED_SPECIES)
_AGE_POOL = (
    AgeCategory.BABY, AgeCategory.YOUNG, AgeCategory.ADULT, AgeCategory.SENIOR,
    AgeCategory.UNKNOWN, None,
)
_ALL_FLAGS = tuple(RedFlag)


def _generated_cases(count: int = 400) -> tuple[Case, ...]:
    rng = random.Random(GENERATOR_SEED)
    cases: list[Case] = []
    for index in range(count):
        # Weighted so most cases carry at least one sign and therefore reach a
        # real evidence label; a tail of them carry none.
        flag_count = rng.choices((0, 1, 2, 3, 4), weights=(12, 40, 25, 15, 8))[0]
        flags = rng.sample(_ALL_FLAGS, flag_count)
        intake = SymptomIntake(
            concern=rng.choice(tuple(Concern)),
            body_area=rng.choice((*BodyArea, None)),
            duration=rng.choice((*Duration, None)),
            trend=rng.choice((*Trend, None)),
            red_flags=flags,
            time_since_eating=rng.choice((*TimeSinceEating, None)),
            has_chronic_illness=rng.choice((True, False, None)),
            weight_bearing=rng.choice((True, False, None)),
            species=rng.choice(_SPECIES_POOL),
            age_category=rng.choice(_AGE_POOL),
            # Drawn last on purpose: the skin answers were added after the first
            # audit ran, and appending them here leaves every earlier draw — and
            # so every case the audit had already scored — byte for byte the same.
            itch_level=rng.choice((*ItchLevel, None)),
            skin_spread=rng.choice((*SkinSpread, None)),
        )
        cases.append(
            Case(
                id=f"gen_{index:04d}",
                origin=GENERATED,
                description=(
                    f"Generated (seed {GENERATOR_SEED}): species={intake.species!r}, "
                    f"age={intake.age_category}, concern={intake.concern.value}, "
                    f"flags={[f.value for f in flags]}"
                ),
                intake=intake,
            )
        )
    return tuple(cases)


GENERATED_CASES = _generated_cases()

CASES: tuple[Case, ...] = (*VIGNETTES, *BOUNDARY_CASES, *GENERATED_CASES)


def cases_by_origin(origin: str) -> tuple[Case, ...]:
    return tuple(case for case in CASES if case.origin == origin)


assert len({case.id for case in CASES}) == len(CASES), "Case ids must be unique."
assert len(CASES) >= 500, f"The audit requires at least 500 scenarios, built {len(CASES)}."

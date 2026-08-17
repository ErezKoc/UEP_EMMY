"""What the owner reports, and what the triage engine answers.

Every question here exists because a published source uses it to decide
urgency — see `services/triage/rules.py` for which source drives which
question. Nothing is asked out of curiosity.

Everything except the concern is optional, so an owner who only wants a breed
estimate can skip the whole form.
"""

import enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.species import clean_species_label
from app.models.animal import AgeCategory


class Concern(str, enum.Enum):
    """Why the owner is here — the first question, and the escape hatch."""

    BREED_ONLY = "breed_only"
    SKIN_OR_COAT = "skin_or_coat"
    EYES = "eyes"
    EARS = "ears"
    MOBILITY = "mobility"
    DIGESTION = "digestion"
    BREATHING = "breathing"
    URINATION = "urination"
    BEHAVIOUR = "behaviour"
    OTHER = "other"


class BodyArea(str, enum.Enum):
    HEAD_OR_FACE = "head_or_face"
    EAR = "ear"
    EYE = "eye"
    MOUTH = "mouth"
    CHEST = "chest"
    BELLY = "belly"
    BACK = "back"
    LEGS_OR_PAWS = "legs_or_paws"
    TAIL = "tail"
    ALL_OVER = "all_over"


class Duration(str, enum.Enum):
    TODAY = "today"
    DAYS_2_7 = "days_2_7"
    WEEKS_1_4 = "weeks_1_4"
    OVER_MONTH = "over_month"


class Trend(str, enum.Enum):
    WORSENING = "worsening"
    UNCHANGED = "unchanged"
    IMPROVING = "improving"


class RedFlag(str, enum.Enum):
    """Signs the intake form offers.

    Each one is used by at least one rule in `rules.py`, and every rule names
    the source that treats the sign as urgent.
    """

    # Merck — emergencies requiring immediate care
    TROUBLE_BREATHING = "trouble_breathing"
    SEVERE_PAIN = "severe_pain"
    UNCONTROLLED_BLEEDING = "uncontrolled_bleeding"
    SUSPECTED_POISONING = "suspected_poisoning"
    EYE_INJURY = "eye_injury"
    EYE_PAIN_OR_CLOSED = "eye_pain_or_closed"
    EYE_CLOUDY_OR_BLUE = "eye_cloudy_or_blue"
    UNEQUAL_PUPILS_OR_VISION_CHANGE = "unequal_pupils_or_vision_change"
    EYE_BULGING_OR_SEVERE_SWELLING = "eye_bulging_or_severe_swelling"
    EYE_DISCHARGE_YELLOW_GREEN_OR_BLOODY = "eye_discharge_yellow_green_or_bloody"
    EYE_CHEMICAL_EXPOSURE = "eye_chemical_exposure"
    EAR_HEAD_SHAKING_OR_SCRATCHING = "ear_head_shaking_or_scratching"
    EAR_ODOR = "ear_odor"
    EAR_DISCHARGE = "ear_discharge"
    EAR_REDNESS = "ear_redness"
    EAR_PAIN = "ear_pain"
    EAR_FLAP_SWELLING = "ear_flap_swelling"
    EAR_HEAD_TILT = "ear_head_tilt"
    EAR_BALANCE_PROBLEMS = "ear_balance_problems"
    EAR_RAPID_EYE_MOVEMENTS = "ear_rapid_eye_movements"
    EAR_SUDDEN_HEARING_LOSS = "ear_sudden_hearing_loss"
    EAR_FACIAL_DROOP = "ear_facial_droop"
    EAR_BLOODY_OR_PUS_DISCHARGE = "ear_bloody_or_pus_discharge"
    EAR_SELF_INJURY = "ear_self_injury"
    EAR_FOREIGN_BODY = "ear_foreign_body"
    LIMB_CANNOT_MOVE = "limb_cannot_move"

    # ASPCA — emergency signs and situations
    SEIZURE = "seizure"
    COLLAPSE_OR_UNRESPONSIVE = "collapse_or_unresponsive"
    PALE_GUMS = "pale_gums"
    MAJOR_TRAUMA = "major_trauma"
    CHOKING = "choking"
    INSECT_STING_REACTION = "insect_sting_reaction"

    # Cornell + Merck — heatstroke
    OVERHEATING = "overheating"

    # ACVS — urinary obstruction
    UNABLE_TO_URINATE = "unable_to_urinate"

    # Cornell — GDV
    BLOATED_ABDOMEN_WITH_RETCHING = "bloated_abdomen_with_retching"

    # Missouri + Cornell — vomiting and diarrhoea.
    # Vomiting and diarrhoea are separate signs because the sources give them
    # different thresholds (Missouri: vomiting beyond 24h; Cornell: loose stool
    # beyond two days).
    BLOOD_IN_VOMIT_OR_STOOL = "blood_in_vomit_or_stool"
    BLACK_TARRY_STOOL = "black_tarry_stool"
    VOMITING = "vomiting"
    DIARRHOEA = "diarrhoea"
    EXTREME_LETHARGY = "extreme_lethargy"

    # Cornell — feline anorexia
    NOT_EATING = "not_eating"

    # VCA — polydipsia
    DRINKING_MUCH_MORE = "drinking_much_more"


class TimeSinceEating(str, enum.Enum):
    """Asked only when the owner reports the animal is not eating.

    The buckets match the thresholds Cornell gives for cats (24 hours for a
    mature cat, 12 hours for a kitten under six weeks).
    """

    UNDER_12H = "under_12h"
    H12_TO_24H = "h12_to_24h"
    OVER_24H = "over_24h"


class TriageLevel(str, enum.Enum):
    """How urgently the animal should be seen — or that we cannot say.

    `UNASSESSED` is not a fourth point on the urgency scale; it is a refusal to
    place the case on the scale at all. It is returned when the owner described
    something and no published source we hold covers it — an unsupported
    species, or a combination our rules do not reach. It exists because the
    alternative was returning `GREEN`, and green is the reassuring end of a
    red/amber/green scale: an owner reporting a seizing rabbit was being shown
    the same colour as an owner told to monitor at home. Absence of evidence is
    not evidence of safety, and the response type now says so.
    """

    RED = "red"
    AMBER = "amber"
    GREEN = "green"
    UNASSESSED = "unassessed"


class SymptomIntake(BaseModel):
    """The owner's answers.

    `species` and `age_category` are filled in server-side from the linked pet
    rather than asked again, and `has_chronic_illness` exists because Missouri
    treats an animal with an existing chronic disease as needing care sooner.
    """

    concern: Concern = Concern.BREED_ONLY
    body_area: BodyArea | None = None
    duration: Duration | None = None
    trend: Trend | None = None
    red_flags: list[RedFlag] = Field(default_factory=list)
    time_since_eating: TimeSinceEating | None = None
    has_chronic_illness: bool | None = None
    weight_bearing: bool | None = None

    species: str | None = None
    age_category: AgeCategory | None = None

    @field_validator("species", mode="before")
    @classmethod
    def tidy_species(cls, value: object) -> object:
        """Strip and collapse whitespace before anything compares this.

        The rule table normalises again when it matches, but doing it here too
        means the value stored in a symptom-check row and shown back in history
        is the tidy one. Casing is left alone: `normalise_species` handles that
        at comparison time, and the owner's own spelling is theirs to keep.
        """
        if isinstance(value, str):
            return clean_species_label(value)
        return value


class SourceLink(BaseModel):
    name: str
    url: str


class FiredRule(BaseModel):
    """One rule that matched, shown to the owner as a reason for the result."""

    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    message: str
    weight: int
    sources: list[str]
    source_links: list[SourceLink] = Field(default_factory=list)


class TriageAssessment(BaseModel):
    """The engine's verdict, with every reason it reached that verdict."""

    level: TriageLevel
    headline: str
    score: int
    threshold: int
    fired_rules: list[FiredRule]
    advice: str
    urgent_care_signs: list[str] = Field(default_factory=list)
    care_instructions: list[str] = Field(default_factory=list)
    disclaimer: str
    rules_fully_verified: bool

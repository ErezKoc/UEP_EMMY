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
    #: "Breathing looks difficult or laboured". The value is unchanged so that
    #: checks stored before the split still read back, but the QUESTION is not:
    #: it used to be "breathing hard or fast", one option covering two signs
    #: that need different qualification. A dog can breathe hard and fast for a
    #: minute after a run, and this rule is an unconditional emergency.
    TROUBLE_BREATHING = "trouble_breathing"
    #: "Breathing unusually fast while resting". The other half, with the
    #: qualifier that separates it from panting after exercise, excitement or
    #: heat. Also an unconditional emergency — the qualifier narrows what gets
    #: reported, not what we do about it.
    RAPID_BREATHING_AT_REST = "rapid_breathing_at_rest"
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
    # The ordinary eye signs, added 2026-08-22. VCA's page is about redness,
    # watering and irritation, and the eye rule resting on it described those
    # signs back to owners who had never been offered them as answers — the
    # form asked only about the urgent ones above. Asking is what lets the
    # rule quote the owner instead of the source.
    EYE_REDNESS = "eye_redness"
    EYE_WATERING = "eye_watering"
    EYE_IRRITATION = "eye_irritation"
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

    # Merck integumentary system — the presentations its dermatology pages
    # name. A skin case is defined by what is on the skin, not by the word
    # the owner picked for it, so "skin or coat" on its own tells the rule
    # table nothing and these do.
    SKIN_ITCHING = "skin_itching"
    SKIN_REDNESS = "skin_redness"
    SKIN_HAIR_LOSS = "skin_hair_loss"
    SKIN_RASH_OR_BUMPS = "skin_rash_or_bumps"
    SKIN_SCABS_OR_FLAKING = "skin_scabs_or_flaking"
    SKIN_SWELLING = "skin_swelling"
    SKIN_LUMP = "skin_lump"
    SKIN_NAIL_OR_PAD_CHANGE = "skin_nail_or_pad_change"
    SKIN_OPEN_WOUND = "skin_open_wound"
    SKIN_DISCHARGE_OR_PUS = "skin_discharge_or_pus"
    SKIN_ODOR = "skin_odor"
    SKIN_CONTAGION = "skin_contagion"

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
    # Missouri's escalation item has two clauses — "profuse vomiting occurs many
    # times in a day OR attempts to vomit continue for more than 24 hours" — and
    # the form could only ever see the second one, through the duration band.
    VOMITING_MANY_TIMES = "vomiting_many_times"
    DIARRHOEA = "diarrhoea"
    EXTREME_LETHARGY = "extreme_lethargy"

    # Cornell — feline anorexia
    NOT_EATING = "not_eating"

    # VCA — polydipsia
    DRINKING_MUCH_MORE = "drinking_much_more"


class ItchLevel(str, enum.Enum):
    """How much the skin problem is bothering the animal.

    Merck names pruritus a dermatological presentation in its own right and
    says the itch is a clinical sign rather than a diagnosis. It does NOT grade
    severity, so these bands are ours: they exist to separate an owner who
    noticed a red patch from one whose animal cannot settle, and the rule that
    uses them is marked as reasoning past its source.
    """

    NONE = "none"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"
    CANNOT_SETTLE = "cannot_settle"


class SkinSpread(str, enum.Enum):
    """How widely the skin problem is distributed.

    Merck's dermatology framework records distribution as focal, multifocal,
    symmetrical or generalized, and treats it as part of the history a diagnosis
    needs. No source we hold attaches an urgency to any pattern, so this answer
    is carried into the record a veterinarian sees and drives no rule — see
    `services/triage/candidates.py`.
    """

    ONE_AREA = "one_area"
    SEVERAL_AREAS = "several_areas"
    WIDESPREAD = "widespread"


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
    itch_level: ItchLevel | None = None
    skin_spread: SkinSpread | None = None
    has_chronic_illness: bool | None = None
    weight_bearing: bool | None = None

    #: Did the owner actually answer the emergency screen?
    #:
    #: `None` means we do not know, which is what every call that predates this
    #: field says, and what a direct API call that omits it says. It exists
    #: because the screening line on the result — "you did not select any of the
    #: emergency warning signs" — is a statement about what the OWNER did, and
    #: an empty `red_flags` list cannot tell the difference between someone who
    #: read seventeen emergency signs and ticked none, and someone who scrolled
    #: past the question. Only the first of those has been screened, and only
    #: the first should be told so.
    emergency_screen_answered: bool | None = None

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


class ExtrapolationKind(str, enum.Enum):
    """What kind of step past its source a rule takes, when it takes one.

    "This rule extrapolates" was one flag doing three jobs, and the three are
    not equally serious. A rule that invents a deadline its source never gives
    is doing something quite different from one that decides an owner's words
    for "red and itchy" describe a skin problem — and the second should not
    weaken our stated confidence in the recommendation, because the source makes
    the recommendation itself in so many words.
    """

    #: The owner's answers had to be classified into the source's category —
    #: deciding that "red and itchy" is the skin disease the page writes about.
    MAPPING = "mapping"
    #: The source describes what a problem of this kind needs, but does not say
    #: that a presentation of THIS severity crosses the bar for an appointment
    #: rather than watching. "An examination establishes the diagnosis" is not
    #: the same claim as "this mild, localised patch should be brought in", and
    #: the second is the one the owner acts on.
    THRESHOLD = "threshold"
    #: The rule recommends more than the source recommends.
    RECOMMENDATION = "recommendation"
    #: The rule names a timeframe the source does not give.
    TIMING = "timing"


class DiagnosticEvidence(str, enum.Enum):
    """Do this rule's own sources describe how the cause gets worked out?

    Declared per rule because it varies, and the confidence report was assuming
    it. Merck's dermatology pages describe the history, the examination and the
    tests; Missouri's vomiting page is about choosing between home care and
    prompt attention and says nothing about diagnosis at all. Telling an owner
    "the pages cited above state how the cause is identified" under a Missouri
    result was the report describing a source it was not looking at.
    """

    #: A cited page describes the history, examination or testing involved.
    DESCRIBED = "described"
    #: No cited page speaks to it. The default: silence, not denial.
    NOT_DESCRIBED = "not_described"


class UrgencyEvidence(str, enum.Enum):
    """Does a cited page say how quickly the animal should be seen?

    Kept apart from the rule's own weight because they answer different
    questions. "Merck records lesion distribution as part of the dermatologic
    history" establishes that a skin problem needs looking at; it establishes
    nothing whatsoever about how soon. Conflating the two is how an app ends up
    inventing a deadline, so the distinction is declared per rule and reported
    to the owner rather than left implicit.
    """

    #: At least one cited page uses urgency language or names a time window.
    STATED = "stated"
    #: No cited page says anything about timing. The default, deliberately.
    NOT_STATED = "not_stated"


class ConfidenceLevel(str, enum.Enum):
    """How far one aspect of the answer can be relied on.

    Bands rather than a number: a percentage would imply we had measured how
    often the engine is right, and nobody has.
    """

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    #: Not the same as LOW, and separated because they were being shown in the
    #: same word. LOW means we looked and the sources do not support it. This
    #: means the question was never in scope for this rule — a urinary
    #: obstruction rule rests on how fast to act, so whether its pages also
    #: describe how the cause is worked out is something we never recorded.
    #: Rendering both as "None" told an owner that evidence had been sought and
    #: found missing, which is a claim about the sources rather than about us.
    NOT_ASSESSED = "not_assessed"


class ConfidenceKind(str, enum.Enum):
    """Which question a dimension answers — three unrelated ones share the panel.

    They were previously rated on one shared vocabulary, and "Match to your
    answers: Strong" sat directly above a recommendation whose evidence was
    rated Partial. An owner reads the first word and takes it for how sure we
    are of the advice, when all it says is that a rule's conditions were met.
    The kind is carried so each question can be worded in its own terms.
    """

    #: Did the answers given meet the conditions of a rule? Bookkeeping, not
    #: evidence: a rule can match perfectly and rest on nothing.
    MATCH = "match"
    #: How far published sources support one part of what we told them.
    EVIDENCE = "evidence"
    #: Whether a veterinarian has checked the rules behind this answer.
    REVIEW = "review"


class ConfidenceDimension(BaseModel):
    """One thing we can be more or less sure of, named and rated separately."""

    name: str
    level: ConfidenceLevel
    detail: str
    #: Defaulted so a verdict stored before the kinds existed still parses; the
    #: dimensions it holds are all evidence ones except the two renamed below,
    #: which read acceptably either way.
    kind: ConfidenceKind = ConfidenceKind.EVIDENCE


class ConfidenceReport(BaseModel):
    """How far this answer can be relied on, broken into its parts.

    Deliberately not a single number. "Moderate confidence" invites the reading
    "moderately sure something is wrong with your pet", which is a claim about
    the animal rather than about our evidence, and it compresses four unrelated
    questions into one: did the answers match a rule, does a source support
    examining this, does any source say how soon, and has a veterinarian checked
    any of it. Those can and do differ — a case can match our rules perfectly
    and still rest on no urgency evidence at all — so they are reported apart.
    """

    dimensions: list[ConfidenceDimension] = Field(default_factory=list)
    #: What this answer rests on: how many rules matched, what we did not know.
    based_on: list[str] = Field(default_factory=list)
    #: Questions the owner skipped whose answers would have changed the level,
    #: worded as the form asked them.
    would_change_the_answer: list[str] = Field(default_factory=list)


class SourceLink(BaseModel):
    name: str
    url: str


class UrgentSign(BaseModel):
    """One "get help now" line, with the page that states it.

    Attributed one at a time. Nine signs sharing two citations meant the list
    looked uniformly sourced while at least one line — severe pain — is stated
    by only one of the two pages, and a reviewer checking the other would not
    have found it.
    """

    text: str
    sources: list[SourceLink] = Field(default_factory=list)


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
    #: The one thing an owner wants settled before they read anything else:
    #: whether what they described tripped an emergency rule. It used to be
    #: inferable only from the card's colour and from the absence of alarm in
    #: three paragraphs of evidence reporting. Deliberately a restatement of
    #: their own answers — "you reported none of these" — and not the clinical
    #: claim "this is not an emergency", which nothing here establishes.
    screening_note: str | None = None
    score: int
    threshold: int
    fired_rules: list[FiredRule]
    advice: str
    urgent_care_signs: list[UrgentSign] = Field(default_factory=list)
    #: Where the urgent-care list came from, when it is not the fired rules'
    #: own. A skin answer shows the general emergency signs, and saying so
    #: matters: the sources under the skin reasons do not establish them.
    urgent_care_note: str | None = None
    urgent_care_sources: list[SourceLink] = Field(default_factory=list)
    care_instructions: list[str] = Field(default_factory=list)
    #: Explanatory notes about the appointment itself. Kept apart from
    #: `care_instructions`, which tell the owner what to do at home — a heading
    #: reading "Care until the appointment" over two sentences about how skin
    #: disease is diagnosed was mislabelling one as the other.
    what_to_expect: list[str] = Field(default_factory=list)
    disclaimer: str
    rules_fully_verified: bool

    @field_validator("urgent_care_signs", mode="before")
    @classmethod
    def accept_plain_strings(cls, value: object) -> object:
        """Read back a check stored before the signs carried their own sources."""
        if isinstance(value, list):
            return [{"text": item} if isinstance(item, str) else item for item in value]
        return value
    #: Optional so a verdict stored before confidence existed still parses.
    confidence: ConfidenceReport | None = None

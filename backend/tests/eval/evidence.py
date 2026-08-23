"""The evidence ledger — what each source was independently read to say.

Every URL below was fetched and read during an audit sweep, separately from
whatever `app/services/triage/sources.py` claims. The first sweep ran on
2026-08-16; the dermatology pages at the end of this file were read on
2026-08-18, when the skin pathway was added; the urinary pages on
2026-08-22; and the two feline pages on 2026-08-23, when the graded rules
for limping and diarrhoea were found to cover dogs only. Each `Finding` records:

* the quoted or closely paraphrased statement the page actually makes,
* the species the page addresses,
* the urgency that statement establishes *on its own*, and
* whether reaching the engine's behaviour needs a step the page does not take.

`oracle.py` derives every expected triage level from this file and nothing else.
This module deliberately does NOT import the production rule table.

NOT CLINICALLY VALIDATED. These readings were made by a software auditor from
published pages. No veterinarian has reviewed either the readings or the labels
derived from them. `verified_by` is left unset everywhere for that reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

#: The first sweep, and the default date a finding was read on.
FIRST_AUDIT = date(2026, 8, 16)
#: The dermatology sweep, which added the Merck skin pages.
DERMATOLOGY_AUDIT = date(2026, 8, 18)
#: The urinary sweep, which read the two obstruction pages that cover dogs, and
#: re-read Cornell's anorexia page for what it says below its own 24-hour mark.
URINARY_AUDIT = date(2026, 8, 22)
#: The feline sweep. Same shape of gap as the urinary one, found the same way:
#: the graded limping and diarrhoea rules cited VCA's canine limping page and
#: Cornell's canine diarrhoea page, so a cat reporting either sign matched no
#: rule and was told the checker could not assess it. Both publishers have a
#: feline page; neither was ever unavailable to us. Cornell's feline page turns
#: out NOT to say what its canine one says, which is why the two species are
#: read separately below rather than one being mirrored onto the other.
FELINE_AUDIT = date(2026, 8, 23)
#: The most recent read in this ledger. Staleness and "not in the future" checks
#: are measured from here, so adding a later sweep does not backdate the rest.
AUDIT_DATE = FELINE_AUDIT

DOG = "dog"
CAT = "cat"
DOG_AND_CAT = frozenset({DOG, CAT})
DOG_ONLY = frozenset({DOG})
CAT_ONLY = frozenset({CAT})
ANY_SPECIES = None


class Urgency:
    """What a statement establishes about how fast the animal must be seen.

    Deliberately coarser than the product's red/amber/green so that a source
    saying "needs examination" is not silently upgraded to "emergency".
    """

    EMERGENCY = "emergency"          # source says immediate / emergency / life-threatening
    PROMPT_EXAM = "prompt_exam"      # source says see a vet, without emergency language
    WATCHFUL = "watchful"            # source's own threshold implies monitoring below it
    NONE = "none"                    # source establishes no urgency at all


@dataclass(frozen=True)
class Finding:
    """One statement, read from one page, usable as a label justification."""

    id: str
    source_name: str
    url: str
    species: frozenset[str] | None
    statement: str
    urgency: str
    accessed: date = FIRST_AUDIT
    # Set when the audit had to reason beyond the page's literal wording to use
    # this finding at the urgency recorded above. A label resting on such a
    # finding is reported as inference-dependent rather than confirmed.
    inference: str = ""
    # Set to record something the page notably does NOT say. This does not
    # weaken the finding's own urgency — it is evidence against a stronger
    # claim built elsewhere on the same page.
    negative_finding: str = ""
    page_type: str = "clinical article"
    # A named veterinarian who confirmed this reading. Nobody has.
    verified_by: str | None = None

    @property
    def is_inferred(self) -> bool:
        return bool(self.inference)


# ---------------------------------------------------------------------------
# Merck Veterinary Manual — What to Do in a Dog or Cat Emergency
# Read 2026-08-16. Real article page. Publisher: Merck & Co. veterinary
# reference, editorially reviewed. Credible.
# ---------------------------------------------------------------------------

MERCK_EMERGENCY_URL = (
    "https://www.merckvetmanual.com/special-pet-topics/emergencies"
    "/what-to-do-in-a-dog-or-cat-emergency"
)

MERCK_LIST = tuple(
    Finding(
        id=f"merck_emergency.{slug}",
        source_name="Merck Veterinary Manual — What to Do in a Dog or Cat Emergency",
        url=MERCK_EMERGENCY_URL,
        species=DOG_AND_CAT,
        statement=(
            "Names the following among situations needing immediate veterinary care: "
            "poisoning, severe pain, severe or uncontrolled bleeding, trouble breathing, "
            f"eye injuries, suspected broken bones or a limb that can't move — this entry: {label}."
        ),
        urgency=Urgency.EMERGENCY,
    )
    for slug, label in (
        ("poisoning", "poisoning"),
        ("severe_pain", "severe pain"),
        ("bleeding", "severe or uncontrolled bleeding"),
        ("breathing", "trouble breathing"),
        ("eye_injury", "eye injuries"),
        ("limb", "suspected broken bones or a limb that can't move"),
    )
)

MERCK_HEATSTROKE = Finding(
    id="merck_emergency.heatstroke",
    source_name="Merck Veterinary Manual — What to Do in a Dog or Cat Emergency",
    url=MERCK_EMERGENCY_URL,
    species=DOG_AND_CAT,
    statement=(
        "Discusses heat stroke as an emergency condition requiring immediate care. "
        "It is not one of the six bulleted entries in the page's headline emergency list."
    ),
    urgency=Urgency.EMERGENCY,
)

# ---------------------------------------------------------------------------
# ASPCA — Emergency Care for Your Pet. Read 2026-08-16. Real article page.
# Publisher: ASPCA, a recognised animal-welfare authority. Credible.
# ---------------------------------------------------------------------------

ASPCA_EMERGENCY_URL = "https://www.aspca.org/pet-care/general-pet-care/emergency-care-your-pet"

# The page makes TWO different claims and the first reading of it ran them
# together. Re-read 2026-08-18 after a reviewer challenged the sting rule.
#
#   SIGNS — "Pale gums / Rapid breathing / Weak or rapid pulse / Change in body
#   temperature / Difficulty standing / Apparent paralysis / Loss of
#   consciousness / Seizures / Excessive bleeding" are given as signs a pet
#   needs emergency care.
#
#   CAUSES — "Your dog may need emergency care because of severe trauma —
#   caused by an accident or fall — choking, heatstroke, an insect sting,
#   household poisoning or other life-threatening situation." That is "MAY need
#   emergency care BECAUSE OF", which is not the same as "this is an emergency".
#
# The distinction matters most for the sting: an exposure whose consequences
# range from a weal that resolves in an hour to anaphylaxis. Reading the causes
# sentence as though it named nine emergencies is what let a dog stung days ago,
# with an itchy paw and nothing else, be told to call an emergency service.
ASPCA_TRANSPORT = Finding(
    id="aspca_emergency.transport",
    source_name="ASPCA — Emergency Care for Your Pet",
    url=ASPCA_EMERGENCY_URL,
    species=DOG_AND_CAT,
    statement=(
        "\"Once you feel confident and safe transporting your pet, immediately bring him to an "
        "emergency care facility.\" \"Ask a friend or family member to call the clinic so the "
        "staff knows to expect you and your pet.\""
    ),
    urgency=Urgency.EMERGENCY,
    accessed=DERMATOLOGY_AUDIT,
)

_ASPCA_SIGNS_STATEMENT = (
    "Lists as signs a pet needs emergency care: \"Pale gums / Rapid breathing / Weak or rapid "
    "pulse / Change in body temperature / Difficulty standing / Apparent paralysis / Loss of "
    "consciousness / Seizures / Excessive bleeding\" — this entry: {label}."
)

_ASPCA_CAUSES_STATEMENT = (
    "\"Your dog may need emergency care because of severe trauma — caused by an accident or "
    "fall — choking, heatstroke, an insect sting, household poisoning or other life-threatening "
    "situation.\" — this entry: {label}."
)

_ASPCA_CAUSES_CAVEAT = (
    "The page frames these as causes a pet MAY need emergency care because of, not as "
    "emergencies in themselves, and it nowhere says that an insect sting alone is "
    "life-threatening. Escalating on the exposure rather than on the reaction is not supported "
    "by this sentence."
)

ASPCA_LIST = tuple(
    Finding(
        id=f"aspca_emergency.{slug}",
        source_name="ASPCA — Emergency Care for Your Pet",
        url=ASPCA_EMERGENCY_URL,
        species=DOG_AND_CAT,
        statement=(
            _ASPCA_SIGNS_STATEMENT if kind == "sign" else _ASPCA_CAUSES_STATEMENT
        ).format(label=label),
        urgency=Urgency.EMERGENCY,
        negative_finding="" if kind == "sign" else _ASPCA_CAUSES_CAVEAT,
    )
    for slug, label, kind in (
        ("pale_gums", "pale gums", "sign"),
        ("collapse", "difficulty standing / apparent paralysis / loss of consciousness", "sign"),
        ("seizure", "seizures", "sign"),
        ("bleeding", "excessive bleeding", "sign"),
        ("trauma", "severe trauma caused by an accident or fall", "cause"),
        ("choking", "choking", "cause"),
        ("sting", "an insect sting", "cause"),
        ("poisoning", "household poisoning", "cause"),
        ("heatstroke", "heatstroke", "cause"),
        # Appended, not inserted: `oracle.py` indexes this tuple by position.
        # The quote recorded above has always contained "Rapid breathing"; it
        # had no entry of its own because one combined breathing flag was
        # attributed to Merck's "trouble breathing" instead.
        ("rapid_breathing", "rapid breathing", "sign"),
    )
)

# ---------------------------------------------------------------------------
# Cornell Feline Health Center — Anorexia. Read 2026-08-16. Real article page.
# Publisher: Cornell University College of Veterinary Medicine. Credible.
# ---------------------------------------------------------------------------

CORNELL_ANOREXIA_URL = (
    "https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center"
    "/health-information/feline-health-topics/anorexia"
)

CAT_ANOREXIA_24H = Finding(
    id="cornell_anorexia.mature_24h",
    source_name="Cornell Feline Health Center — Anorexia",
    url=CORNELL_ANOREXIA_URL,
    species=CAT_ONLY,
    statement=(
        "\"anorexia can have a severe impact on a mature cat's health if it persists for as "
        "little as 24 hours\""
    ),
    urgency=Urgency.EMERGENCY,
)

KITTEN_ANOREXIA_12H = Finding(
    id="cornell_anorexia.kitten_12h",
    source_name="Cornell Feline Health Center — Anorexia",
    url=CORNELL_ANOREXIA_URL,
    species=CAT_ONLY,
    statement=(
        "\"For a kitten younger than six weeks of age, food avoidance for just 12 hours can "
        "pose a lethal threat.\""
    ),
    urgency=Urgency.EMERGENCY,
    inference=(
        "The page's threshold is age < 6 weeks. The intake form's coarsest young band is "
        "'baby', which spans well past six weeks, so applying the 12-hour threshold to the "
        "whole band escalates some kittens the page does not cover. Direction: over-triage."
    ),
)

CAT_ANOREXIA_UNDER_24H = Finding(
    id="cornell_anorexia.mature_under_24h",
    source_name="Cornell Feline Health Center — Anorexia",
    url=CORNELL_ANOREXIA_URL,
    species=CAT_ONLY,
    statement=(
        "The page sets 24 hours as the point at which appetite loss severely affects a mature "
        "cat, and describes anorexia generally as a sign of underlying disease warranting "
        "veterinary attention. Re-read 2026-08-22 for what it says BELOW that threshold, and it "
        "says it directly rather than by implication: \"Dr. McDaniel strongly encourages owners "
        "to consult a veterinarian immediately upon noticing any signs of feline anorexia\", and "
        "\"A cat that is not eating deserves to have a full veterinary workup.\" Neither "
        "sentence is conditioned on a duration."
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=URINARY_AUDIT,
    # The `inference` this finding used to carry has been removed, not
    # downgraded. It read: "Reading a sub-24-hour feline anorexia case as
    # 'needs a vet, not yet an emergency' is the auditor's inference from the
    # page's own threshold; the page does not state a level for shorter
    # durations." That was written from the 24-hour sentence alone. The page
    # also carries the two unconditioned sentences quoted above, so the label
    # rests on what it states, and the 22 cases that were reported as
    # inference-dependent abstentions were never short of evidence.
)

# ---------------------------------------------------------------------------
# ACVS — Urinary Obstruction in Male Cats. Read 2026-08-16. Real article page.
# Publisher: American College of Veterinary Surgeons. Credible specialty body.
# ---------------------------------------------------------------------------

# Read 2026-08-18, after a reviewer pointed out that the ACVS page we were
# citing is specifically about MALE cats and the form never asks the cat's sex.
# This page covers cats, names males as higher risk rather than the only ones
# affected, and states the emergency in stronger terms than the ACVS page does.
CORNELL_LUTD = Finding(
    id="cornell.lutd",
    source_name="Cornell Feline Health Center - Feline Lower Urinary Tract Disease",
    url=(
        "https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-"
        "center/health-information/feline-health-topics/feline-lower-urinary-tract-disease"
    ),
    species=CAT_ONLY,
    statement=(
        "\"A cat experiencing a urethral obstruction usually behaves similarly to cats with LUTS "
        "of other causes, and may strain to urinate, make frequent attempts to urinate, and "
        "produce little, if any, urine.\" \"Urethral obstruction is a true medical emergency, and "
        "any cat suspected of suffering from this condition must receive immediate veterinary "
        "attention.\" \"The time from complete urinary obstruction until death may be less than "
        "twenty-four to forty-eight hours, so immediate treatment is essential.\" \"Male and "
        "neutered male cats are at greater risk for obstruction than females because their "
        "urethra is longer and narrower.\" Last updated October 2016; no author named."
    ),
    urgency=Urgency.EMERGENCY,
    accessed=DERMATOLOGY_AUDIT,
)

# Read 2026-08-18, after a reviewer pointed out that the ACVS page we were
# citing is specifically about MALE cats and the form never asks the cat's sex.
# This page covers cats, names males as higher risk rather than the only ones
# affected, and states the emergency in stronger terms than the ACVS page does.
CORNELL_LUTD = Finding(
    id="cornell.lutd",
    source_name="Cornell Feline Health Center - Feline Lower Urinary Tract Disease",
    url=(
        "https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-"
        "center/health-information/feline-health-topics/feline-lower-urinary-tract-disease"
    ),
    species=CAT_ONLY,
    statement=(
        "\"A cat experiencing a urethral obstruction usually behaves similarly to cats with LUTS "
        "of other causes, and may strain to urinate, make frequent attempts to urinate, and "
        "produce little, if any, urine.\" \"Urethral obstruction is a true medical emergency, and "
        "any cat suspected of suffering from this condition must receive immediate veterinary "
        "attention.\" \"The time from complete urinary obstruction until death may be less than "
        "twenty-four to forty-eight hours, so immediate treatment is essential.\" \"Male and "
        "neutered male cats are at greater risk for obstruction than females because their "
        "urethra is longer and narrower.\" Last updated October 2016; no author named."
    ),
    urgency=Urgency.EMERGENCY,
    accessed=DERMATOLOGY_AUDIT,
)

# ---------------------------------------------------------------------------
# The dog side of urinary obstruction. Read 2026-08-22.
#
# Recorded because the ledger had no page covering a DOG that strains and
# produces nothing: Cornell's LUTD page and the ACVS male-cat page are both
# feline, so the auditor had no basis for any label and the engine abstained.
# ---------------------------------------------------------------------------

ACVS_OBSTRUCTION_DOGS = Finding(
    id="acvs.urinary_obstruction_dogs",
    source_name="American College of Veterinary Surgeons - Urinary Obstruction in Dogs",
    url="https://www.acvs.org/small-animal/urinary-obstruction-in-dogs/",
    species=DOG_ONLY,
    statement=(
        "\"Your pet should be seen by a veterinarian immediately if he/she is unable to "
        "urinate.\" \"Dogs with total urethral obstruction will die within days if the "
        "obstruction is not relieved.\" Partially obstructed dogs \"urinate small amounts "
        "frequently\", \"strain to urinate\", and pass urine in drips rather than a stream; "
        "\"if the urethra is completely blocked, your dog will strain without producing any "
        "urine.\" The page is about dogs, and states the signs for \"he/she\" rather than "
        "for males only, though the surgical sections it goes on to describe are male-specific."
    ),
    urgency=Urgency.EMERGENCY,
    accessed=URINARY_AUDIT,
)

MERCK_URETHRAL_OBSTRUCTION = Finding(
    id="merck.urethral_obstruction",
    source_name="Merck Veterinary Manual - Urethral Obstruction in Small Animals",
    url=(
        "https://www.merckvetmanual.com/urinary-system/urolithiasis-in-small-animals"
        "/urethral-obstruction-in-small-animals"
    ),
    species=DOG_AND_CAT,
    statement=(
        "\"UO is an emergency condition, and stabilization should be prioritized in severely "
        "affected patients.\" \"Complete UO causes uremia within 36-48 hours, which leads to "
        "depression, vomiting, diarrhea, dehydration, coma, and death within approximately 72 "
        "hours.\" \"Life-threatening hyperkalemia can develop with UO and should be addressed "
        "promptly.\" Signs include \"frequent nonproductive attempts to urinate\" and "
        "vocalising while trying; owners \"mistake the signs of UO for constipation\". The "
        "page covers dogs and cats, naming male cats as uniquely predisposed rather than as "
        "the only patients affected."
    ),
    urgency=Urgency.EMERGENCY,
    accessed=URINARY_AUDIT,
)

ACVS_OBSTRUCTION = Finding(
    id="acvs.urinary_obstruction",
    source_name="American College of Veterinary Surgeons — Urinary Obstruction in Male Cats",
    url="https://www.acvs.org/small-animal/urinary-obstruction-in-male-cats/",
    species=CAT_ONLY,
    statement=(
        "\"Cats that have urinary obstruction require emergency treatment\"; \"Complete "
        "obstruction can cause death of the cat in 3–6 days\"; obstructed cats \"may attempt "
        "to urinate in the litter box but will produce no urine\"."
    ),
    urgency=Urgency.EMERGENCY,
    inference=(
        "The page addresses MALE cats specifically. Applying it to female cats extends the "
        "evidence beyond its stated population. Direction: over-triage."
    ),
)

# ---------------------------------------------------------------------------
# Cornell Riney Canine Health Center — GDV. Read 2026-08-16. Real article page.
# ---------------------------------------------------------------------------

CORNELL_GDV = Finding(
    id="cornell.gdv",
    source_name="Cornell Riney Canine Health Center — Gastric dilatation volvulus (GDV) or bloat",
    url=(
        "https://www.vet.cornell.edu/departments-centers-and-institutes/riney-canine-health-center"
        "/canine-health-topics/gastric-dilatation-volvulus-gdv-or-bloat"
    ),
    species=DOG_ONLY,
    statement=(
        "\"GDV requires immediate medical and surgical intervention\"; \"Without medical and "
        "surgical intervention, GDV is fatal.\" Signs include \"Non-productive retching or "
        "attempting to vomit with no production\" and \"Bloated abdomen\"."
    ),
    urgency=Urgency.EMERGENCY,
)

# ---------------------------------------------------------------------------
# University of Missouri VHC — Vomiting and Diarrhea. Read 2026-08-16.
# Real article page. Publisher: university teaching hospital. Credible.
# ---------------------------------------------------------------------------

MISSOURI_URL = (
    "https://vhc.missouri.edu/small-animal-hospital/emergency-and-critical-care"
    "/vomiting-and-diarrhea/"
)
_MISSOURI_PREFIX = (
    "Lists situations warranting more immediate veterinary attention in a vomiting or "
    "diarrhoeic animal: very young or very old animals; animals with chronic disease; "
    "trouble breathing; apparent pain; possible poisoning or foreign body; extreme lethargy "
    "or depression; profuse vomiting many times a day or retching continuing more than 24 "
    "hours; vomit containing blood or coffee-grounds material; diarrhoea containing more "
    "than a small amount of blood or dark and tarry; apparent dehydration."
)

MISSOURI_BLOOD = Finding(
    id="missouri.blood_in_vomit_or_stool",
    source_name="University of Missouri Veterinary Health Center — Vomiting and Diarrhea",
    url=MISSOURI_URL,
    species=DOG_AND_CAT,
    statement=_MISSOURI_PREFIX + " This entry: blood or coffee-grounds vomit, bloody stool.",
    urgency=Urgency.EMERGENCY,
)

MISSOURI_TARRY = Finding(
    id="missouri.dark_tarry_stool",
    source_name="University of Missouri Veterinary Health Center — Vomiting and Diarrhea",
    url=MISSOURI_URL,
    species=DOG_AND_CAT,
    statement=_MISSOURI_PREFIX + " This entry: dark, tarry diarrhoea.",
    urgency=Urgency.EMERGENCY,
)

MISSOURI_VOMITING_OVER_24H = Finding(
    id="missouri.vomiting_over_24h",
    source_name="University of Missouri Veterinary Health Center — Vomiting and Diarrhea",
    url=MISSOURI_URL,
    species=DOG_AND_CAT,
    statement=(
        _MISSOURI_PREFIX
        + " This entry: profuse vomiting many times a day, or attempts to vomit continuing "
        "more than 24 hours."
    ),
    urgency=Urgency.EMERGENCY,
    inference=(
        "RETRACTED 2026-08-18. This finding used to be read as: the intake form's shortest "
        "duration band is 'today', so any longer band means vomiting exceeding 24 hours, which "
        "satisfies the clause. A reviewer pointed out that Missouri's clause is 'attempts to "
        "vomit CONTINUE for more than 24 hours', and an animal sick once a day for three days "
        "does not obviously meet it. The audit accepts that: the finding now supports a label "
        "only when frequency is actually reported. The product made the same step and has "
        "dropped the rule that rested on it."
    ),
)

MISSOURI_FRAGILE = Finding(
    id="missouri.fragile_patient",
    source_name="University of Missouri Veterinary Health Center — Vomiting and Diarrhea",
    url=MISSOURI_URL,
    species=DOG_AND_CAT,
    statement=(
        _MISSOURI_PREFIX
        + " This entry: very young (puppies and kittens) or very old animals, and animals "
        "with chronic disease such as diabetes or kidney disease."
    ),
    urgency=Urgency.EMERGENCY,
)

MISSOURI_LETHARGY_WITH_GI = Finding(
    id="missouri.lethargy_with_gi_signs",
    source_name="University of Missouri Veterinary Health Center — Vomiting and Diarrhea",
    url=MISSOURI_URL,
    species=DOG_AND_CAT,
    statement=(
        _MISSOURI_PREFIX + " This entry: \"The animal is extremely lethargic or depressed\"."
    ),
    urgency=Urgency.EMERGENCY,
    negative_finding=(
        "The page frames this entry inside a vomiting/diarrhoea presentation and says nothing "
        "about lethargy on its own. This finding is therefore used only when vomiting or "
        "diarrhoea is also reported; isolated lethargy is handled by "
        "`missouri.lethargy_alone`, which is explicitly an inference."
    ),
)

MISSOURI_LETHARGY_ALONE = Finding(
    id="missouri.lethargy_alone",
    source_name="University of Missouri Veterinary Health Center — Vomiting and Diarrhea",
    url=MISSOURI_URL,
    species=DOG_AND_CAT,
    statement=(
        "Treats extreme lethargy or depression as a reason to escalate, but only within a "
        "vomiting or diarrhoea presentation. The page makes no claim about lethargy alone."
    ),
    urgency=Urgency.PROMPT_EXAM,
    inference=(
        "No source in the ledger addresses isolated lethargy. PROMPT_EXAM is the auditor's "
        "cautious floor, not a published level."
    ),
)

MISSOURI_SINGLE_EPISODE = Finding(
    id="missouri.uncomplicated_single_episode",
    source_name="University of Missouri Veterinary Health Center — Vomiting and Diarrhea",
    url=MISSOURI_URL,
    species=DOG_AND_CAT,
    statement=(
        "By listing the situations that warrant MORE immediate attention, the page implies "
        "an otherwise well adult with brief, uncomplicated vomiting is not in that group."
    ),
    urgency=Urgency.WATCHFUL,
    inference=(
        "Reading the complement of a 'when to escalate' list as permission to monitor is an "
        "inference. Used only for adult, non-chronically-ill animals with no other sign."
    ),
)

# ---------------------------------------------------------------------------
# Cornell Riney Canine Health Center — Diarrhea. Read 2026-08-16. Real article.
# ---------------------------------------------------------------------------

CORNELL_DIARRHOEA_URL = (
    "https://www.vet.cornell.edu/departments-centers-and-institutes/riney-canine-health-center"
    "/canine-health-topics/diarrhea"
)

CORNELL_DIARRHOEA_RED_FLAGS = Finding(
    id="cornell.diarrhoea_red_flags",
    source_name="Cornell Riney Canine Health Center — Diarrhea",
    url=CORNELL_DIARRHOEA_URL,
    species=DOG_ONLY,
    statement=(
        "\"If a pet stops eating, is lethargic, the diarrhea is black or tarry in quality, "
        "there is associated vomiting, or the diarrhea doesn't resolve in 48-72 hours then "
        "veterinary care should be sought.\""
    ),
    urgency=Urgency.EMERGENCY,
    inference=(
        "The page says veterinary care 'should be sought', not that it is an emergency. This "
        "audit still labels diarrhoea plus anorexia or lethargy at EMERGENCY because the "
        "Missouri page independently places the same combination in its immediate-attention "
        "list for dogs and cats."
    ),
)

CORNELL_DIARRHOEA_TWO_DAYS = Finding(
    id="cornell.diarrhoea_two_days",
    source_name="Cornell Riney Canine Health Center — Diarrhea",
    url=CORNELL_DIARRHOEA_URL,
    species=DOG_ONLY,
    statement="\"If loose stool lasts more than two days, call the vet\"",
    urgency=Urgency.PROMPT_EXAM,
)

CORNELL_DIARRHOEA_SHORT = Finding(
    id="cornell.diarrhoea_under_two_days",
    source_name="Cornell Riney Canine Health Center — Diarrhea",
    url=CORNELL_DIARRHOEA_URL,
    species=DOG_ONLY,
    statement=(
        "The page's own threshold — call the vet after more than two days — implies that "
        "uncomplicated loose stool below that threshold is watched rather than escalated."
    ),
    urgency=Urgency.WATCHFUL,
    inference="Complement of a stated threshold; used only when no other sign is reported.",
)

CORNELL_DIARRHOEA_HOME_CARE = Finding(
    id="cornell.diarrhoea_home_care",
    source_name="Cornell Riney Canine Health Center — Diarrhea",
    url=CORNELL_DIARRHOEA_URL,
    # The one claim on this canine-centre page that names both species, and it
    # names them in its own words. Scoped accordingly, so the rule that gives
    # home-care advice can reach a pet whose species we were never told.
    species=DOG_AND_CAT,
    statement=(
        "\"Mild cases of diarrhea in both cats and dogs can be treated at home by feeding a "
        "bland diet such as boiled chicken or low-fat hamburger, and white rice.\" \"Another "
        "tip is to start by withholding all food for 12-24 hours, then introduce the bland "
        "diet.\" \"Have fresh water available at all times.\""
    ),
    urgency=Urgency.WATCHFUL,
    negative_finding=(
        "Only this sentence covers cats. Every other claim on the page - including the two-day "
        "threshold - is canine, which is why the SOURCE stays dog-only in sources.py and only "
        "this citation widens. Cornell publishes a separate feline diarrhoea page that says "
        "something different, and a cat follows that one instead."
    ),
    accessed=FELINE_AUDIT,
)

# ---------------------------------------------------------------------------
# Cornell Feline Health Center — Diarrhea. Read 2026-08-23. Real article page.
#
# Read because the canine page above was carrying the whole diarrhoea pathway
# and is correctly scoped to dogs. It is NOT the same guidance: the canine page
# gives a two-day threshold and home care below it, and this one asks for an
# examination as soon as signs are noticed, with no threshold at all.
# ---------------------------------------------------------------------------

CORNELL_FELINE_DIARRHOEA_URL = (
    "https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center"
    "/health-information/feline-health-topics/diarrhea"
)

CORNELL_FELINE_DIARRHOEA_EXAMINE = Finding(
    id="cornell.feline_diarrhoea_examine_when_noticed",
    source_name="Cornell Feline Health Center — Diarrhea",
    url=CORNELL_FELINE_DIARRHOEA_URL,
    species=CAT_ONLY,
    statement=(
        "\"While there are many medications and other therapies available that may effectively "
        "relieve feline diarrhea, it is most important for a veterinarian to examine an affected "
        "animal as soon as the clinical signs are noticed, as some over the counter medications "
        "can be harmful to cats.\""
    ),
    urgency=Urgency.PROMPT_EXAM,
    negative_finding=(
        "The sentence sits in a paragraph about over-the-counter remedies, so it can be read as "
        "aimed at owners about to self-medicate rather than at every loose stool. The audit "
        "records it at PROMPT_EXAM on its plain wording and flags the reading for the reviewing "
        "veterinarian, because it is what makes feline diarrhoea amber on day one where the "
        "same sign in a dog is watched."
    ),
    accessed=FELINE_AUDIT,
)

CORNELL_FELINE_DIARRHOEA_SYSTEMIC = Finding(
    id="cornell.feline_diarrhoea_systemic_signs",
    source_name="Cornell Feline Health Center — Diarrhea",
    url=CORNELL_FELINE_DIARRHOEA_URL,
    species=CAT_ONLY,
    statement=(
        "\"If the diarrhea persists for longer than a day or two and the cat is also showing "
        "systemic signs, such as poor appetite, lethargy, or vomiting, you should seek "
        "veterinary care as soon as possible.\""
    ),
    urgency=Urgency.PROMPT_EXAM,
    negative_finding=(
        "Duration and systemic signs are joined with \"and\", not \"or\". The page does not say "
        "that two days of loose stool alone warrants care — unlike Cornell's canine page, which "
        "does. Missouri independently escalates diarrhoea with anorexia or extreme lethargy for "
        "both species, and that is where the emergency reading of this combination comes from."
    ),
    accessed=FELINE_AUDIT,
)

# ---------------------------------------------------------------------------
# Cornell Riney Canine Health Center — Heatstroke. Read 2026-08-16.
# ---------------------------------------------------------------------------

CORNELL_HEATSTROKE = Finding(
    id="cornell.heatstroke",
    source_name="Cornell Riney Canine Health Center — Heatstroke: A medical emergency",
    url=(
        "https://www.vet.cornell.edu/departments-centers-and-institutes/riney-canine-health-center"
        "/canine-health-information/heatstroke-medical-emergency"
    ),
    species=DOG_ONLY,
    statement=(
        "\"Heatstroke is a life-threatening condition ... This can cause severe damage to body "
        "organs and can result in death.\" Signs: heavy panting, drooling, bloody diarrhoea, "
        "vomiting, weakness, confusion, seizures, collapse."
    ),
    urgency=Urgency.EMERGENCY,
)

# ---------------------------------------------------------------------------
# VCA Animal Hospitals — read 2026-08-16.
# Publisher: a large corporate veterinary hospital group. Clinically credible,
# but its pages are commercial as well as educational; the urgent-care page in
# particular is a service landing page rather than a peer-reviewed article.
# ---------------------------------------------------------------------------

VCA_EYE_URL = "https://vcahospitals.com/urgent-care/health-concerns/eye-issues"

VCA_EYE_URGENT = Finding(
    id="vca.eye_urgent_signs",
    source_name="VCA Animal Hospitals — Urgent Care for Eye Issues",
    url=VCA_EYE_URL,
    species=DOG_AND_CAT,
    statement=(
        "Lists as reasons to seek urgent care: squinting or holding the eye closed, cloudy "
        "eyes, bulging eyes, red and swollen conjunctiva, watery eyes with red surrounding "
        "skin, and drainage or discharge."
    ),
    urgency=Urgency.EMERGENCY,
    page_type="urgent-care service landing page (marketing as well as educational)",
    inference=(
        "The page says 'pets' and never names a species. Treating it as dog-and-cat evidence "
        "is an assumption. It is also promotional for the publisher's own urgent-care "
        "service, which weakens it as an independent urgency authority."
    ),
)

VCA_EYE_NONSPECIFIC = Finding(
    id="vca.eye_nonspecific_signs",
    source_name="VCA Animal Hospitals — Urgent Care for Eye Issues",
    url=VCA_EYE_URL,
    species=DOG_AND_CAT,
    statement=(
        "\"Dust, dirt and even fur can get into your pet's eyes and cause redness, itching, "
        "watering or irritation. However, some eye issues are signs of an infection, injury "
        "or other serious condition that requires prompt medical attention.\""
    ),
    urgency=Urgency.PROMPT_EXAM,
    page_type="urgent-care service landing page (marketing as well as educational)",
)

VCA_THIRST = Finding(
    id="vca.increased_thirst",
    source_name="VCA Animal Hospitals — Testing for Increased Thirst and Urination",
    url="https://vcahospitals.com/know-your-pet/testing-for-increased-thirst-and-urination",
    species=DOG_AND_CAT,
    statement=(
        "Associates increased thirst and urination with kidney disorders, hormone disorders "
        "including hyperadrenocorticism and diabetes mellitus and insipidus, and liver "
        "disease, and describes the diagnostic testing used to work them up. The page states "
        "no urgency and gives no timeframe for seeing a veterinarian."
    ),
    urgency=Urgency.PROMPT_EXAM,
    inference=(
        "The page is about diagnostic work-up, not triage. Reading 'needs a diagnostic "
        "work-up' as 'needs a veterinary appointment rather than home monitoring' is the "
        "auditor's inference. The page supports no urgency claim of any kind."
    ),
)

VCA_ANOREXIA_DOGS = Finding(
    id="vca.anorexia_dogs",
    source_name="VCA Animal Hospitals — Anorexia in Dogs",
    url="https://vcahospitals.com/know-your-pet/anorexia-in-dogs",
    species=DOG_ONLY,
    statement=(
        "\"Poor appetite or refusal to eat is strongly associated with illness\"; \"Take "
        "changes in your dog's eating behavior seriously and get your veterinarian involved "
        "early.\" No hour threshold is given."
    ),
    urgency=Urgency.PROMPT_EXAM,
)

VCA_LIMPING_OVER_24H = Finding(
    id="vca.limping_over_24h",
    source_name="VCA Animal Hospitals — First Aid for Limping Dogs",
    url="https://vcahospitals.com/know-your-pet/first-aid-for-limping-dogs",
    species=DOG_ONLY,
    statement="\"If lameness persists for more than 24 hours, seek veterinary care.\"",
    urgency=Urgency.PROMPT_EXAM,
)

VCA_LIMPING_NON_WEIGHT_BEARING = Finding(
    id="vca.non_weight_bearing",
    source_name="VCA Animal Hospitals — First Aid for Limping Dogs",
    url="https://vcahospitals.com/know-your-pet/first-aid-for-limping-dogs",
    species=DOG_ONLY,
    statement=(
        "\"A simple way to determine the severity of the injury is that most dogs will not "
        "walk on a broken leg, torn ligament, or dislocated joint.\""
    ),
    urgency=Urgency.PROMPT_EXAM,
)

VCA_LIMPING_SHORT = Finding(
    id="vca.limping_under_24h",
    source_name="VCA Animal Hospitals — First Aid for Limping Dogs",
    url="https://vcahospitals.com/know-your-pet/first-aid-for-limping-dogs",
    species=DOG_ONLY,
    statement=(
        "The page's threshold — seek care if lameness persists more than 24 hours — implies "
        "that a limp of under a day in an otherwise well dog is watched first."
    ),
    urgency=Urgency.WATCHFUL,
    inference="Complement of a stated threshold; used only when no other sign is reported.",
)

# ---------------------------------------------------------------------------
# VCA Animal Hospitals — First Aid for Limping Cats. Read 2026-08-23.
# The feline counterpart of the page above, and it states the same threshold in
# the same words. Recorded separately anyway: the ledger's species scoping is
# what stopped the canine page being used for cats, and inheriting a reading
# across species by hand is the mistake that scoping exists to prevent.
# ---------------------------------------------------------------------------

VCA_LIMPING_CATS_OVER_24H = Finding(
    id="vca.limping_cats_over_24h",
    source_name="VCA Animal Hospitals — First Aid for Limping Cats",
    url="https://vcahospitals.com/know-your-pet/first-aid-for-limping-cats",
    species=CAT_ONLY,
    statement="\"If lameness persists for more than 24 hours, seek veterinary care.\"",
    urgency=Urgency.PROMPT_EXAM,
    accessed=FELINE_AUDIT,
)

VCA_LIMPING_CATS_NON_WEIGHT_BEARING = Finding(
    id="vca.non_weight_bearing_cats",
    source_name="VCA Animal Hospitals — First Aid for Limping Cats",
    url="https://vcahospitals.com/know-your-pet/first-aid-for-limping-cats",
    species=CAT_ONLY,
    statement=(
        "\"Most cats will not walk on a broken leg, torn ligament, or dislocated joint.\""
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=FELINE_AUDIT,
)

VCA_LIMPING_CATS_SHORT = Finding(
    id="vca.limping_cats_under_24h",
    source_name="VCA Animal Hospitals — First Aid for Limping Cats",
    url="https://vcahospitals.com/know-your-pet/first-aid-for-limping-cats",
    species=CAT_ONLY,
    statement=(
        "The page's threshold — seek care if lameness persists more than 24 hours — implies "
        "that a limp of under a day in an otherwise well cat is watched first."
    ),
    urgency=Urgency.WATCHFUL,
    inference="Complement of a stated threshold; used only when no other sign is reported.",
    accessed=FELINE_AUDIT,
)

# ---------------------------------------------------------------------------
# Merck ophthalmology and toxicology. Read 2026-08-16. Real article pages,
# authored and peer-reviewed by named diplomates.
# ---------------------------------------------------------------------------

MERCK_GLAUCOMA = Finding(
    id="merck.acute_glaucoma",
    source_name="Merck Veterinary Manual — Acute Glaucoma in Small Animals",
    url=(
        "https://www.merckvetmanual.com/emergency-medicine-and-critical-care"
        "/ophthalmic-emergencies-in-small-animals/acute-glaucoma-in-small-animals"
    ),
    species=DOG_AND_CAT,
    statement=(
        "\"Acute glaucoma is considered an ophthalmological emergency.\" Signs: blepharospasm, "
        "episcleral hyperemia, diffuse corneal edema, mydriasis, lack of vision. \"Diagnosis "
        "of glaucoma depends on clinical signs and accurate tonometry.\""
    ),
    urgency=Urgency.EMERGENCY,
)

MERCK_UVEITIS = Finding(
    id="merck.anterior_uveitis",
    source_name="Merck Veterinary Manual — Anterior Uveitis in Small Animals",
    url=(
        "https://www.merckvetmanual.com/emergency-medicine-and-critical-care"
        "/ophthalmic-emergencies-in-small-animals/anterior-uveitis-in-small-animals"
    ),
    species=DOG_AND_CAT,
    statement=(
        "\"A fluorescein stain should always be performed to assess for concurrent corneal "
        "ulceration.\" Anterior uveitis may follow trauma, cataracts, corneal ulceration, "
        "lens instability, intraocular neoplasia or systemic disease."
    ),
    urgency=Urgency.PROMPT_EXAM,
)

MERCK_CORROSIVE_EYE = Finding(
    id="merck.corrosive_ocular_exposure",
    source_name="Merck Veterinary Manual — Toxicoses from Corrosive Agents in Animals",
    url=(
        "https://www.merckvetmanual.com/toxicology/toxicoses-from-household-hazards"
        "/toxicoses-from-corrosive-agents-in-animals"
    ),
    species=ANY_SPECIES,
    statement=(
        "\"Eyes should be flushed for a minimum of 20 minutes, and then the cornea should be "
        "stained with fluorescein to detect corneal injury.\" All species are susceptible."
    ),
    urgency=Urgency.EMERGENCY,
)

MERCK_EYE_STEROIDS = Finding(
    id="merck.ocular_anti_inflammatories",
    source_name="Merck Veterinary Manual — Anti-inflammatory Agents in Animals",
    url=(
        "https://www.merckvetmanual.com/pharmacology/systemic-pharmacotherapeutics-of-the-eye"
        "/anti-inflammatory-agents-in-animals"
    ),
    species=ANY_SPECIES,
    statement=(
        "\"Before use, the cornea should be stained with fluorescein to check for ulcers.\" "
        "\"Corticosteroids are contraindicated both topically and systemically when a corneal "
        "ulcer is present.\""
    ),
    # Supports a safety warning about medicating at home, not a triage level.
    urgency=Urgency.NONE,
)

# ---------------------------------------------------------------------------
# Merck ear disorders. Read 2026-08-16. Real article pages.
# ---------------------------------------------------------------------------

MERCK_OTITIS_EXTERNA = Finding(
    id="merck.otitis_externa",
    source_name="Merck Veterinary Manual — Otitis Externa in Animals",
    url="https://www.merckvetmanual.com/ear-disorders/otitis-externa/otitis-externa-in-animals",
    species=frozenset({DOG, CAT, "rabbit"}),
    statement=(
        "Signs: \"head shaking, aural pruritus, pain, malodor, otic discharge or exudate, "
        "erythema, erosions, ulcerations, and edema.\" \"Diagnosis is based on history, "
        "otoscopic examination, and cytological evaluation.\" \"Treatment depends on the "
        "specific diagnosis.\" The tympanic membrane should be examined when possible. "
        "Foreign bodies are a primary cause. Affects dogs and cats (especially dogs) and can "
        "also affect rabbits."
    ),
    urgency=Urgency.PROMPT_EXAM,
)

MERCK_OTITIS_MEDIA_INTERNA = Finding(
    id="merck.otitis_media_interna",
    source_name="Merck Veterinary Manual — Otitis Media and Interna in Animals",
    url=(
        "https://www.merckvetmanual.com/ear-disorders/otitis-media-and-interna"
        "/otitis-media-and-interna-in-animals"
    ),
    species=frozenset({DOG, CAT, "rabbit", "horse", "ruminant", "pig", "camelid"}),
    statement=(
        "Signs of otitis interna: \"ipsilateral head tilt, turning in tight circles toward the "
        "affected side, leaning or falling toward the affected side, general incoordination, "
        "spontaneous horizontal nystagmus\"; hearing loss and facial nerve paralysis also "
        "occur. \"Diagnosis of otitis media or interna begins with a complete history, a "
        "physical examination ... and, when possible, an otoscopic examination.\" Treatment "
        "\"is most successful when started early in the disease course.\""
    ),
    urgency=Urgency.PROMPT_EXAM,
    negative_finding=(
        "The page does NOT describe these signs as an emergency and gives no same-day or "
        "other timing. Any same-day claim built on this page is an extrapolation."
    ),
)

MERCK_AURICULAR_HEMATOMA = Finding(
    id="merck.auricular_hematoma",
    source_name="Merck Veterinary Manual — Auricular Hematomas in Animals",
    url=(
        "https://www.merckvetmanual.com/ear-disorders/diseases-of-the-pinna"
        "/auricular-hematomas-in-animals"
    ),
    species=frozenset({DOG, CAT, "pig", "horse", "sheep"}),
    statement=(
        "Describes \"small-to-large, fluid-filled swellings\" on the concave pinna caused by "
        "\"trauma from head shaking or ear scratching\", and treatment requiring \"control of "
        "the underlying cause of pruritus\"."
    ),
    urgency=Urgency.PROMPT_EXAM,
    negative_finding=(
        "The page uses no time-critical language and does not call an auricular hematoma an "
        "emergency or urgent."
    ),
)

# ---------------------------------------------------------------------------
# Poison control services. Read 2026-08-16.
# ---------------------------------------------------------------------------

ASPCA_POISON_CONTROL = Finding(
    id="aspca.poison_control_line",
    source_name="ASPCA Animal Poison Control Center",
    url="https://www.aspca.org/pet-care/aspca-poison-control",
    species=ANY_SPECIES,
    statement=(
        "Gives (888) 426-4435, available \"24/7, 365 days a year\", staffed by \"highly "
        "trained veterinary toxicology experts\". A consultation fee may apply. US service."
    ),
    urgency=Urgency.EMERGENCY,
)

PET_POISON_HELPLINE = Finding(
    id="pph.signs_of_poisoning",
    source_name="Pet Poison Helpline — Signs of Poisoning in Dogs and Cats",
    url="https://www.petpoisonhelpline.com/pet-owners/basics/signs-of-poisoning-in-dogs-and-cats/",
    species=DOG_AND_CAT,
    statement=(
        "\"If you think your dog or cat has been poisoned, call your veterinarian or Pet "
        "Poison Helpline® at 855-764-7661 immediately for assistance! When it comes to "
        "poisoning, the sooner you treat your dog or cat, the better the outcome.\" US service."
    ),
    urgency=Urgency.EMERGENCY,
)


# ---------------------------------------------------------------------------
# Merck toxicology — wasp, bee and ant stings. Read 2026-08-18.
# ---------------------------------------------------------------------------

MERCK_STINGS = Finding(
    id="merck.stings",
    source_name="Merck Veterinary Manual - Wasp, Bee, and Ant Stings to Animals",
    url=(
        "https://www.merckvetmanual.com/toxicology"
        "/bites-and-stings-from-spiders-scorpions-and-insects/wasp-bee-and-ant-stings-to-animals"
    ),
    species=DOG_AND_CAT,
    statement=(
        "An ordinary sting causes \"localized pain and swelling\" with \"erythema, edema\"; signs "
        "\"can occur within minutes after the sting\" and \"resolve quickly, within minutes, "
        "unless severe reaction occurs\". A fire ant sting gives a \"wheal and flare reaction, "
        "which typically resolves within an hour\", leaving an \"erythematous pruritic papule\" "
        "that resolves \"within 24 hours in most cases\". Multiple stings can cause "
        "\"prostration, seizures or CNS depression, bloody diarrhea, bloody vomiting, "
        "hyperthermia\"; massive envenomation can cause \"facial paralysis, ataxia, seizures\"; "
        "anaphylaxis is possible and severe anaphylaxis is treated with epinephrine. \"Stings "
        "are most common on the face and in the mouth.\" Author Andras Laszlo Nagy, DVM, MSc, "
        "PhD, DABVT; peer reviewed by Ahna Brutlag, DVM, DABT, DABVT; last modified April 2026."
    ),
    urgency=Urgency.NONE,
    accessed=DERMATOLOGY_AUDIT,
    negative_finding=(
        "The page never says when an owner should seek care. It describes treatments, not "
        "thresholds. It also gives the opposite of an escalation cue for the ordinary case: a "
        "local reaction resolves in minutes to a day, so a skin problem still present after "
        "several days is unlikely to be explained by the sting at all."
    ),
)


# ---------------------------------------------------------------------------
# Merck emergency medicine — trauma. Read 2026-08-18.
#
# Recorded at PROMPT_EXAM, not EMERGENCY, and the reason is worth stating: the
# page describes what trauma does to an animal and never tells anyone how fast
# to act. The emergency framing on the trauma rule comes from the ASPCA page,
# which names severe trauma outright. This one is cited for what it establishes
# — that an attack is trauma, and that an animal can look fine and not be.
# ---------------------------------------------------------------------------

MERCK_TRAUMA = Finding(
    id="merck.trauma",
    source_name="Merck Veterinary Manual - Trauma in Emergency Medicine in Small Animals",
    url=(
        "https://www.merckvetmanual.com/emergency-medicine-and-critical-care"
        "/specific-diagnostics-and-therapy/trauma-in-emergency-medicine-in-small-animals"
    ),
    species=DOG_AND_CAT,
    statement=(
        "Animals attacked by other animals can sustain \"deep, penetrating wounds\" and spinal "
        "injuries, and \"major cervical ... abdominal, and thoracic trauma (even without "
        "penetrating wounds) from the shearing forces sustained during thrashing motions\". "
        "Blunt trauma is \"commonly associated with thoracic and abdominal bleeding, organ "
        "rupture, fractures, and neurological injuries\", and falls \"may cause long bone and "
        "facial bone fractures as well as thoracic and abdominal injuries\". \"A patient that "
        "appears normal and stable on initial examination may have substantial underlying "
        "injury\", and such injuries \"are not apparent for hours or sometimes days after the "
        "initial trauma occurs\". Author Andrew Linklater, DVM, DACVECC; peer "
        "reviewed by Patrick Carney, DVM, PhD, DACVIM; last modified March 2026."
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=DERMATOLOGY_AUDIT,
    negative_finding=(
        "The page does not say a trauma patient must be assessed immediately; it emphasises "
        "close monitoring. The urgency on our trauma rule rests on the ASPCA page, not this one."
    ),
)


# ---------------------------------------------------------------------------
# Merck integumentary system. Read 2026-08-18, for the skin pathway. Real
# article pages in the professional manual, each with a named board-certified
# dermatologist author and a named peer reviewer.
#
# The recurring finding across all four: these pages describe how a skin problem
# is characterised and diagnosed, and NONE of them says how quickly an animal
# should be seen. So they can support "this needs an examination" and cannot
# support any timing claim.
# ---------------------------------------------------------------------------

MERCK_DERM_PROBLEMS = Finding(
    id="merck.dermatological_problems",
    source_name="Merck Veterinary Manual - Dermatological Problems in Animals",
    url=(
        "https://www.merckvetmanual.com/integumentary-system"
        "/integumentary-system-introduction/dermatological-problems-in-animals"
    ),
    species=ANY_SPECIES,
    statement=(
        "Organises skin disease by presentation: pruritus, alopecia, \"scaling and crusting\", "
        "\"nodules or tumors\", odor, otitis, \"erosions and ulcerations\" and \"nonhealing "
        "wounds\". Names the distribution patterns \"focal, multifocal, symmetrical, or "
        "generalized\". Lists among the dermatological history \"presence or absence of "
        "pruritus, evidence of contagion, or nondermatological problems\". States that "
        "\"accurate diagnosis of the cause of alopecia requires a careful history and physical "
        "examination\". Author Karen A. Moriello, DVM, DACVD; peer reviewed by Alejandro "
        "Ramirez, DVM, PhD, DACVPM; last updated May 2025."
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=DERMATOLOGY_AUDIT,
    inference=(
        "The page states what a clinician needs in order to diagnose a skin problem. Reading "
        "that as \"this animal needs to be examined\" is the audit's step: the page addresses "
        "veterinarians and never tells an owner to seek care."
    ),
    negative_finding=(
        "The page gives no urgency, no timing, and no threshold at which a skin problem stops "
        "being watchable at home. Any timing claim built on it is an extrapolation."
    ),
)

MERCK_PRURITUS = Finding(
    id="merck.pruritus",
    source_name="Merck Veterinary Manual - Pruritus in Animals",
    url=(
        "https://www.merckvetmanual.com/integumentary-system"
        "/integumentary-system-introduction/pruritus-in-animals"
    ),
    species=ANY_SPECIES,
    statement=(
        "\"Pruritus (itching) is defined as an unpleasant sensation within the skin that "
        "provokes the desire to scratch. It is the most common dermatological problem in both "
        "small and large animals.\" \"Pruritus is a clinical sign, not a diagnosis or specific "
        "disease.\" \"In general, the most common causes of pruritus are parasites, infections, "
        "allergic skin diseases, and miscellaneous causes (eg, cutaneous neoplasia).\" "
        "\"Diagnosis of pruritus requires a methodical workup performed in a logical sequence "
        "in a compact period of time. A thorough dermatological history and physical "
        "examination should be performed.\" Notes that discomfort such as pain or pruritus can "
        "lead to self-trauma and hair loss. Author Karen A. Moriello, DVM, DACVD; peer reviewed "
        "by Alejandro Ramirez, DVM, PhD, DACVPM; last updated May 2025."
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=DERMATOLOGY_AUDIT,
    inference=(
        "\"Requires a methodical workup\" describes the veterinary investigation, not a "
        "recommendation to the owner about when to book it."
    ),
    negative_finding=(
        "The page does NOT grade pruritus by severity and gives no urgency or timing. It says "
        "nothing about how intensely an animal must be itching before it should be seen, so "
        "the intake form's severity bands are the product's own and rest on no source here."
    ),
)

MERCK_SKIN_DIAGNOSIS = Finding(
    id="merck.skin_diagnosis",
    source_name="Merck Veterinary Manual - Diagnosis of Skin Diseases in Small Animals",
    url=(
        "https://www.merckvetmanual.com/integumentary-system"
        "/integumentary-system-introduction/diagnosis-of-skin-diseases-in-small-animals"
    ),
    species=DOG_AND_CAT,
    statement=(
        "\"A complete physical examination should always be performed to help diagnose a skin "
        "disease\", including \"very close inspection of all the hair and skin under strong "
        "lighting\". \"Many skin diseases look alike, and a definitive diagnosis is made by "
        "including or excluding possible causes and by evaluating responses to treatment.\" The "
        "dermatologic history records the primary sign and its duration, age of onset, "
        "\"presence and severity of pruritus, as indicated by behaviors such as licking, "
        "rubbing, scratching, or chewing\", progression, lesion distribution, seasonality, "
        "previous treatment, bathing, parasite exposure, \"contact with other possibly "
        "contagious animals\", and signs of systemic illness. \"Diseases that begin with "
        "pruritus can lead to self-trauma and subsequent development of secondary skin lesions "
        "(alopecia, seborrhea) or infections (bacterial or yeast pyoderma).\" \"Skin scrapings "
        "are part of the basic database for all skin diseases\" and \"hair trichograms are part "
        "of the basic database for all skin diseases\". \"Many skin diseases are manifestations "
        "of systemic diseases.\" Author Karen A. Moriello, DVM, DACVD; peer reviewed by "
        "Alejandro Ramirez, DVM, PhD, DACVPM; last modified May 2025."
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=DERMATOLOGY_AUDIT,
    inference=(
        "\"Should always be performed\" instructs the clinician diagnosing a skin disease. "
        "Reading it as \"this animal should be booked in\" is still the audit's step, though a "
        "shorter one than on the other dermatology pages."
    ),
    negative_finding=(
        "No urgency, no timeframe, and no statement about when an owner should seek care. The "
        "page also does NOT say that the history and examination select which tests are used - "
        "it describes skin scrapings and trichograms as part of the basic database for ALL skin "
        "diseases, which is the opposite of selective testing."
    ),
)

# Read 2026-08-18 and recorded, but NOT cited by any rule: it is the
# dog-owners version, and the skin rules cover cats too, so citing it would
# widen a dog-only page. Kept here because a reviewer asked what it says.
MERCK_OWNER_SKIN_DIAGNOSIS = Finding(
    id="merck.owner_skin_diagnosis",
    source_name="Merck Veterinary Manual - Diagnosis of Skin Disorders in Dogs (pet-owner version)",
    url=(
        "https://www.merckvetmanual.com/dog-owners/skin-disorders-of-dogs"
        "/diagnosis-of-skin-disorders-in-dogs"
    ),
    species=DOG_ONLY,
    statement=(
        "\"A precise diagnosis of the causes of a skin disease requires a detailed history, "
        "physical examination, and appropriate diagnostic tests.\" The veterinarian \"may order "
        "any of a number of laboratory procedures\", naming \"microscopic analysis of skin "
        "scrapings and hair, cultures of hair or skin swabs, specialized skin tests, blood and "
        "urine tests, and even biopsies\". \"It may take several days before laboratory results "
        "are available\" and \"more than one visit is often required for an accurate "
        "diagnosis\". Author Karen A. Moriello, DVM, DACVD; last updated September 2024; no peer "
        "reviewer named."
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=DERMATOLOGY_AUDIT,
    page_type="pet-owner article",
    negative_finding=(
        "Like the professional version, this page does NOT say on what basis the veterinarian "
        "chooses which tests to run - only that they may order them. It gives no urgency and no "
        "timeframe for seeking care."
    ),
)

MERCK_PYODERMA = Finding(
    id="merck.pyoderma",
    source_name="Merck Veterinary Manual - Pyoderma in Dogs and Cats",
    url="https://www.merckvetmanual.com/integumentary-system/pyoderma/pyoderma-in-dogs-and-cats",
    species=DOG_AND_CAT,
    statement=(
        "\"Pyoderma\" generally refers to bacterial dermatitis and literally means \"pus in the "
        "skin\". Superficial pyoderma in dogs: \"multifocal areas of alopecia, follicular "
        "papules or pustules, epidermal collarettes, crusts and scales\". \"The hallmarks of "
        "deep pyoderma in dogs are pain, crusting, odor, and exudation of blood and pus. "
        "Erythema, swelling, ulcerations, hemorrhagic crusts and bullae, hair loss, and "
        "draining tracts with serohemorrhagic or purulent exudate might also be present.\" "
        "Deep pyoderma is \"less common but more serious because it expands into the dermis, "
        "with a higher risk of bacteremia\". \"Diagnosis of pyoderma is based on the presence "
        "of characteristic lesions, confirmation of the presence of bacteria, and ruling out "
        "other common causes\"; cytology is \"one of the most valuable tools\" and \"treatment "
        "should be based on the results of bacterial culture and susceptibility testing\". "
        "Author Mitzi D. Clark, DVM, DACVD; peer reviewed by Patrick Carney, DVM, PhD, DACVIM; "
        "last modified October 2025."
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=DERMATOLOGY_AUDIT,
    negative_finding=(
        "\"More serious\" and \"higher risk of bacteremia\" describe deep pyoderma's clinical "
        "significance, not how fast the animal must be seen. The page names no emergency, no "
        "same-day language and no time window."
    ),
)

MERCK_DERMATOPHYTOSIS = Finding(
    id="merck.dermatophytosis",
    source_name="Merck Veterinary Manual - Dermatophytosis in Dogs and Cats",
    url=(
        "https://www.merckvetmanual.com/integumentary-system/dermatophytosis"
        "/dermatophytosis-in-dogs-and-cats"
    ),
    species=DOG_AND_CAT,
    statement=(
        "\"Dermatophytosis is a zoonotic disease\" whose lesions in people \"are easily "
        "treated\". \"Transmission is by direct contact with an infected animal, but mere "
        "exposure does not always result in disease.\" Lesions \"can include hair loss, "
        "scaling, crusting erythema, papules, hyperpigmentation, and variable pruritus\". "
        "\"No single test is a gold standard\" and \"typically, multiple tests are used to "
        "confirm infection\" (Wood's lamp, trichogram, fungal culture, PCR). \"Infected small "
        "animals should remain isolated from other pets until there is clear evidence of "
        "clinical cure.\" Author Karen A. Moriello, DVM, DACVD; peer reviewed by Joyce "
        "Carnevale, DVM, DABVP; last updated February 2025."
    ),
    urgency=Urgency.PROMPT_EXAM,
    accessed=DERMATOLOGY_AUDIT,
    inference=(
        "The page addresses a confirmed infection. Treating \"another pet or a person in the "
        "house has developed a skin problem too\" as a reason for this animal to be examined "
        "is the audit's step; the page does not describe that owner-reported situation."
    ),
    negative_finding=(
        "The page describes dermatophytosis as self-limiting in otherwise healthy animals, "
        "resolving in 6-12 weeks. It gives no urgency and nothing here supports treating "
        "contagion as time-critical."
    ),
)


ALL_FINDINGS: tuple[Finding, ...] = (
    *MERCK_LIST,
    ASPCA_TRANSPORT,
    MERCK_HEATSTROKE,
    *ASPCA_LIST,
    CAT_ANOREXIA_24H,
    KITTEN_ANOREXIA_12H,
    CAT_ANOREXIA_UNDER_24H,
    CORNELL_LUTD,
    CORNELL_LUTD,
    ACVS_OBSTRUCTION,
    ACVS_OBSTRUCTION_DOGS,
    MERCK_URETHRAL_OBSTRUCTION,
    CORNELL_GDV,
    MISSOURI_BLOOD,
    MISSOURI_TARRY,
    MISSOURI_VOMITING_OVER_24H,
    MISSOURI_FRAGILE,
    MISSOURI_LETHARGY_WITH_GI,
    MISSOURI_LETHARGY_ALONE,
    MISSOURI_SINGLE_EPISODE,
    CORNELL_DIARRHOEA_RED_FLAGS,
    CORNELL_DIARRHOEA_TWO_DAYS,
    CORNELL_DIARRHOEA_SHORT,
    CORNELL_DIARRHOEA_HOME_CARE,
    CORNELL_FELINE_DIARRHOEA_EXAMINE,
    CORNELL_FELINE_DIARRHOEA_SYSTEMIC,
    CORNELL_HEATSTROKE,
    VCA_EYE_URGENT,
    VCA_EYE_NONSPECIFIC,
    VCA_THIRST,
    VCA_ANOREXIA_DOGS,
    VCA_LIMPING_OVER_24H,
    VCA_LIMPING_NON_WEIGHT_BEARING,
    VCA_LIMPING_SHORT,
    VCA_LIMPING_CATS_OVER_24H,
    VCA_LIMPING_CATS_NON_WEIGHT_BEARING,
    VCA_LIMPING_CATS_SHORT,
    MERCK_GLAUCOMA,
    MERCK_UVEITIS,
    MERCK_CORROSIVE_EYE,
    MERCK_EYE_STEROIDS,
    MERCK_OTITIS_EXTERNA,
    MERCK_OTITIS_MEDIA_INTERNA,
    MERCK_AURICULAR_HEMATOMA,
    ASPCA_POISON_CONTROL,
    PET_POISON_HELPLINE,
    MERCK_STINGS,
    MERCK_TRAUMA,
    MERCK_DERM_PROBLEMS,
    MERCK_PRURITUS,
    MERCK_SKIN_DIAGNOSIS,
    MERCK_OWNER_SKIN_DIAGNOSIS,
    MERCK_PYODERMA,
    MERCK_DERMATOPHYTOSIS,
)

# Species this evidence base can speak to at all. Anything else is unassessable.
SUPPORTED_SPECIES = frozenset({DOG, CAT})

# Answers that mean "the owner did not tell us the species". The intake form's
# "Not sure / another animal" option submits an empty string
# (frontend/src/pages/triage/SymptomCheckPage.tsx), and a free-text pet-species
# field collects the rest of these in practice. None of them names an animal, so
# none of them should stop dog-and-cat evidence applying.
#
# Deliberately written out here rather than imported from
# `app.core.species`: the oracle stays independent of production code. The two
# lists are compared by `test_citation_audit.py`, so drift is caught rather than
# silently agreed with.
UNKNOWN_SPECIES_VALUES = frozenset(
    {
        "",
        "unknown",
        "unsure",
        "not sure",
        "not_sure",
        "notsure",
        "dont know",
        "don't know",
        "other",
        "n/a",
        "na",
        "none",
        "null",
        "-",
        "--",
        "?",
    }
)

# The subset an audit-time regression test exercises directly: values a
# free-text species field plausibly holds that must not disable the rule table.
AMBIGUOUS_UNKNOWN_SPECIES_VALUES = ("unknown", "Unknown", "not sure", "not_sure", "other", "n/a")

# Signs the intake form offers for which NO source in this ledger establishes a
# level on its own. Recorded so coverage gaps are visible rather than implied.
SIGNS_WITHOUT_STANDALONE_EVIDENCE = frozenset(
    {
        "ear_head_shaking_or_scratching",
        "ear_odor",
        "ear_discharge",
        "ear_redness",
        "ear_pain",
        "ear_flap_swelling",
        "ear_head_tilt",
        "ear_balance_problems",
        "ear_rapid_eye_movements",
        "ear_sudden_hearing_loss",
        "ear_facial_droop",
        "ear_bloody_or_pus_discharge",
        "ear_self_injury",
        "ear_foreign_body",
    }
)

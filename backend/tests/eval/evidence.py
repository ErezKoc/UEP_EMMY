"""The evidence ledger — what each source was independently read to say.

Every URL below was fetched and read during the audit on 2026-08-16, separately
from whatever `app/services/triage/sources.py` claims. Each `Finding` records:

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

AUDIT_DATE = date(2026, 8, 16)

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
    accessed: date = AUDIT_DATE
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

ASPCA_LIST = tuple(
    Finding(
        id=f"aspca_emergency.{slug}",
        source_name="ASPCA — Emergency Care for Your Pet",
        url=ASPCA_EMERGENCY_URL,
        species=DOG_AND_CAT,
        statement=(
            "Lists as signs a pet needs emergency care: pale gums, rapid breathing, weak or "
            "rapid pulse, change in body temperature, difficulty standing, apparent paralysis, "
            "loss of consciousness, seizures, excessive bleeding. Names severe trauma from an "
            "accident or fall, choking, heatstroke, an insect sting and household poisoning as "
            f"life-threatening situations — this entry: {label}."
        ),
        urgency=Urgency.EMERGENCY,
    )
    for slug, label in (
        ("pale_gums", "pale gums"),
        ("collapse", "difficulty standing / apparent paralysis / loss of consciousness"),
        ("seizure", "seizures"),
        ("bleeding", "excessive bleeding"),
        ("trauma", "severe trauma caused by an accident or fall"),
        ("choking", "choking"),
        ("sting", "an insect sting"),
        ("poisoning", "household poisoning"),
        ("heatstroke", "heatstroke"),
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
        "veterinary attention."
    ),
    urgency=Urgency.PROMPT_EXAM,
    inference=(
        "Reading a sub-24-hour feline anorexia case as 'needs a vet, not yet an emergency' is "
        "the auditor's inference from the page's own threshold; the page does not state a "
        "level for shorter durations."
    ),
)

# ---------------------------------------------------------------------------
# ACVS — Urinary Obstruction in Male Cats. Read 2026-08-16. Real article page.
# Publisher: American College of Veterinary Surgeons. Credible specialty body.
# ---------------------------------------------------------------------------

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
        "The intake form's shortest duration band is 'today', so any longer band is read as "
        "exceeding 24 hours. A case reported as 'today' cannot distinguish one vomit from "
        "profuse vomiting, so 'today' is not escalated on duration alone."
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


ALL_FINDINGS: tuple[Finding, ...] = (
    *MERCK_LIST,
    MERCK_HEATSTROKE,
    *ASPCA_LIST,
    CAT_ANOREXIA_24H,
    KITTEN_ANOREXIA_12H,
    CAT_ANOREXIA_UNDER_24H,
    ACVS_OBSTRUCTION,
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
    CORNELL_HEATSTROKE,
    VCA_EYE_URGENT,
    VCA_EYE_NONSPECIFIC,
    VCA_THIRST,
    VCA_ANOREXIA_DOGS,
    VCA_LIMPING_OVER_24H,
    VCA_LIMPING_NON_WEIGHT_BEARING,
    VCA_LIMPING_SHORT,
    MERCK_GLAUCOMA,
    MERCK_UVEITIS,
    MERCK_CORROSIVE_EYE,
    MERCK_EYE_STEROIDS,
    MERCK_OTITIS_EXTERNA,
    MERCK_OTITIS_MEDIA_INTERNA,
    MERCK_AURICULAR_HEMATOMA,
    ASPCA_POISON_CONTROL,
    PET_POISON_HELPLINE,
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

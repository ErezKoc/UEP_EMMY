"""The publications behind the triage rules.

Every page listed here was fetched and read on the recorded date. Each source
also records its species scope so dog-only or cat-only evidence cannot be used
to justify advice for another species.
"""

from dataclasses import dataclass
from datetime import date

# The day every page below was retrieved and read.
RETRIEVED = date(2026, 7, 30)

DOG_AND_CAT = frozenset({"dog", "cat"})
DOG_ONLY = frozenset({"dog"})
CAT_ONLY = frozenset({"cat"})

#: Species scope for evidence that explicitly covers every animal. Written as
#: `None` rather than a list so we never have to guess which species exist —
#: the source's own wording decides, and a rule carrying this may only cite
#: pages that make an all-species claim.
ALL_SPECIES: frozenset[str] | None = None


@dataclass(frozen=True)
class Source:
    """A reviewed publication and the species its claims cover.

    `species=None` means the page explicitly addresses animals generally.
    """

    name: str
    url: str
    species: frozenset[str] | None
    accessed: date = RETRIEVED


MERCK_EMERGENCY = Source(
    "Merck Veterinary Manual - What to Do in a Dog or Cat Emergency",
    "https://www.merckvetmanual.com/special-pet-topics/emergencies/what-to-do-in-a-dog-or-cat-emergency",
    DOG_AND_CAT,
)

ASPCA_EMERGENCY = Source(
    "ASPCA - Emergency Care for Your Pet",
    "https://www.aspca.org/pet-care/general-pet-care/emergency-care-your-pet",
    DOG_AND_CAT,
)

CORNELL_ANOREXIA = Source(
    "Cornell Feline Health Center - Anorexia",
    "https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center"
    "/health-information/feline-health-topics/anorexia",
    CAT_ONLY,
)

ACVS_URINARY_OBSTRUCTION = Source(
    "American College of Veterinary Surgeons - Urinary Obstruction in Male Cats",
    "https://www.acvs.org/small-animal/urinary-obstruction-in-male-cats/",
    CAT_ONLY,
)

# Read 2026-08-22, to close the gap recorded as candidate
# `urinary_obstruction_outside_cats`: a dog straining and producing nothing
# matched no rule, because every urinary page we held was about cats. ACVS
# publishes the same article for dogs, and Merck's obstruction page is written
# for both species. Neither was ever unavailable to us; nobody had opened them.
ACVS_URINARY_OBSTRUCTION_DOGS = Source(
    "American College of Veterinary Surgeons - Urinary Obstruction in Dogs",
    "https://www.acvs.org/small-animal/urinary-obstruction-in-dogs/",
    DOG_ONLY,
    date(2026, 8, 22),
)

MERCK_URETHRAL_OBSTRUCTION = Source(
    "Merck Veterinary Manual - Urethral Obstruction in Small Animals",
    "https://www.merckvetmanual.com/urinary-system/urolithiasis-in-small-animals"
    "/urethral-obstruction-in-small-animals",
    DOG_AND_CAT,
    date(2026, 8, 22),
)

CORNELL_LUTD = Source(
    "Cornell Feline Health Center - Feline Lower Urinary Tract Disease",
    "https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center"
    "/health-information/feline-health-topics/feline-lower-urinary-tract-disease",
    CAT_ONLY,
    date(2026, 8, 18),
)

CORNELL_GDV = Source(
    "Cornell Riney Canine Health Center - Gastric dilatation volvulus (GDV) or bloat",
    "https://www.vet.cornell.edu/departments-centers-and-institutes/riney-canine-health-center"
    "/canine-health-topics/gastric-dilatation-volvulus-gdv-or-bloat",
    DOG_ONLY,
)

MISSOURI_VOMITING = Source(
    "University of Missouri Veterinary Health Center - Vomiting and Diarrhea",
    "https://vhc.missouri.edu/small-animal-hospital/emergency-and-critical-care/vomiting-and-diarrhea/",
    DOG_AND_CAT,
)

VCA_THIRST = Source(
    "VCA Animal Hospitals - Testing for Increased Thirst and Urination",
    "https://vcahospitals.com/know-your-pet/testing-for-increased-thirst-and-urination",
    DOG_AND_CAT,
)

CORNELL_HEATSTROKE = Source(
    "Cornell Riney Canine Health Center - Heatstroke: A medical emergency",
    "https://www.vet.cornell.edu/departments-centers-and-institutes/riney-canine-health-center"
    "/canine-health-information/heatstroke-medical-emergency",
    DOG_ONLY,
)

CORNELL_DIARRHOEA = Source(
    "Cornell Riney Canine Health Center - Diarrhea",
    "https://www.vet.cornell.edu/departments-centers-and-institutes/riney-canine-health-center"
    "/canine-health-topics/diarrhea",
    DOG_ONLY,
)

# Read 2026-08-23, for the same gap as the limping page above: the diarrhoea
# rule rested on Cornell's CANINE centre, so a cat with loose stool matched
# nothing. Cornell's Feline Health Center covers it separately, and does NOT
# say the same thing — it pairs the duration with systemic signs, and states
# that an affected animal should be examined as soon as signs are noticed. The
# rules below follow the feline page's wording rather than mirroring the dog
# rule, because the two pages genuinely differ.
CORNELL_FELINE_DIARRHOEA = Source(
    "Cornell Feline Health Center - Diarrhea",
    "https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center"
    "/health-information/feline-health-topics/diarrhea",
    CAT_ONLY,
    date(2026, 8, 23),
)

VCA_EYE_ISSUES = Source(
    "VCA Animal Hospitals - Urgent Care for Eye Issues",
    "https://vcahospitals.com/urgent-care/health-concerns/eye-issues",
    DOG_AND_CAT,
)

MERCK_ANTERIOR_UVEITIS = Source(
    "Merck Veterinary Manual - Anterior Uveitis in Small Animals",
    "https://www.merckvetmanual.com/emergency-medicine-and-critical-care/ophthalmic-emergencies-in-small-animals/anterior-uveitis-in-small-animals",
    DOG_AND_CAT,
)

MERCK_ACUTE_GLAUCOMA = Source(
    "Merck Veterinary Manual - Acute Glaucoma in Small Animals",
    "https://www.merckvetmanual.com/emergency-medicine-and-critical-care/ophthalmic-emergencies-in-small-animals/acute-glaucoma-in-small-animals",
    DOG_AND_CAT,
)

MERCK_EYE_ANTI_INFLAMMATORY = Source(
    "Merck Veterinary Manual - Anti-inflammatory Agents in Animals",
    "https://www.merckvetmanual.com/pharmacology/systemic-pharmacotherapeutics-of-the-eye/anti-inflammatory-agents-in-animals",
    None,
)

MERCK_CORROSIVE_EYE_EXPOSURE = Source(
    "Merck Veterinary Manual - Toxicoses from Corrosive Agents in Animals",
    "https://www.merckvetmanual.com/toxicology/toxicoses-from-household-hazards/toxicoses-from-corrosive-agents-in-animals",
    None,
)

MERCK_OTITIS_EXTERNA = Source(
    "Merck Veterinary Manual - Otitis Externa in Animals",
    "https://www.merckvetmanual.com/ear-disorders/otitis-externa/otitis-externa-in-animals",
    DOG_AND_CAT,
    date(2026, 7, 31),
)

MERCK_OTITIS_MEDIA_INTERNA = Source(
    "Merck Veterinary Manual - Otitis Media and Interna in Animals",
    "https://www.merckvetmanual.com/ear-disorders/otitis-media-and-interna/otitis-media-and-interna-in-animals",
    DOG_AND_CAT,
    date(2026, 7, 31),
)

MERCK_AURICULAR_HEMATOMA = Source(
    "Merck Veterinary Manual - Auricular Hematomas in Animals",
    "https://www.merckvetmanual.com/ear-disorders/diseases-of-the-pinna/auricular-hematomas-in-animals",
    DOG_AND_CAT,
    date(2026, 7, 31),
)

VCA_ANOREXIA_DOGS = Source(
    "VCA Animal Hospitals - Anorexia in Dogs",
    "https://vcahospitals.com/know-your-pet/anorexia-in-dogs",
    DOG_ONLY,
)

VCA_LIMPING = Source(
    "VCA Animal Hospitals - First Aid for Limping Dogs",
    "https://vcahospitals.com/know-your-pet/first-aid-for-limping-dogs",
    DOG_ONLY,
)

# Read 2026-08-23. The cat half of the page above, and the reason a limping cat
# used to be told "we can't assess this safely" while an identically limping dog
# got an amber result: every lameness page we held was VCA's canine one, and its
# species scope — correctly — kept it off cats. VCA publishes the feline article
# with the same 24-hour threshold in the same words.
VCA_LIMPING_CATS = Source(
    "VCA Animal Hospitals - First Aid for Limping Cats",
    "https://vcahospitals.com/know-your-pet/first-aid-for-limping-cats",
    CAT_ONLY,
    date(2026, 8, 23),
)

ASPCA_POISON_CONTROL = Source(
    "ASPCA Animal Poison Control Center",
    "https://www.aspca.org/pet-care/aspca-poison-control",
    # The page addresses animal poisoning generally, naming horses alongside pets.
    None,
    date(2026, 8, 7),
)

PET_POISON_HELPLINE = Source(
    "Pet Poison Helpline - Signs of Poisoning in Dogs and Cats",
    "https://www.petpoisonhelpline.com/pet-owners/basics/signs-of-poisoning-in-dogs-and-cats/",
    DOG_AND_CAT,
    date(2026, 8, 7),
)

# Dermatology. Read 2026-08-18. All four are professional-manual articles with a
# named board-certified dermatologist author and a named peer reviewer, and none
# of them states how quickly an animal should be seen — so they support "this
# needs examining" and no timing claim at all.

MERCK_DERM_PROBLEMS = Source(
    "Merck Veterinary Manual - Dermatological Problems in Animals",
    "https://www.merckvetmanual.com/integumentary-system/integumentary-system-introduction"
    "/dermatological-problems-in-animals",
    # The page organises skin disease for animals generally, not dogs and cats.
    None,
    date(2026, 8, 18),
)

MERCK_PRURITUS = Source(
    "Merck Veterinary Manual - Pruritus in Animals",
    "https://www.merckvetmanual.com/integumentary-system/integumentary-system-introduction"
    "/pruritus-in-animals",
    None,
    date(2026, 8, 18),
)

MERCK_STINGS = Source(
    "Merck Veterinary Manual - Wasp, Bee, and Ant Stings to Animals",
    "https://www.merckvetmanual.com/toxicology/bites-and-stings-from-spiders-scorpions-and-insects"
    "/wasp-bee-and-ant-stings-to-animals",
    DOG_AND_CAT,
    date(2026, 8, 18),
)

MERCK_TRAUMA = Source(
    "Merck Veterinary Manual - Trauma in Emergency Medicine in Small Animals",
    "https://www.merckvetmanual.com/emergency-medicine-and-critical-care"
    "/specific-diagnostics-and-therapy/trauma-in-emergency-medicine-in-small-animals",
    DOG_AND_CAT,
    date(2026, 8, 18),
)

MERCK_SKIN_DIAGNOSIS = Source(
    "Merck Veterinary Manual - Diagnosis of Skin Diseases in Small Animals",
    "https://www.merckvetmanual.com/integumentary-system/integumentary-system-introduction"
    "/diagnosis-of-skin-diseases-in-small-animals",
    DOG_AND_CAT,
    date(2026, 8, 18),
)

MERCK_PYODERMA = Source(
    "Merck Veterinary Manual - Pyoderma in Dogs and Cats",
    "https://www.merckvetmanual.com/integumentary-system/pyoderma/pyoderma-in-dogs-and-cats",
    DOG_AND_CAT,
    date(2026, 8, 18),
)

MERCK_DERMATOPHYTOSIS = Source(
    "Merck Veterinary Manual - Dermatophytosis in Dogs and Cats",
    "https://www.merckvetmanual.com/integumentary-system/dermatophytosis"
    "/dermatophytosis-in-dogs-and-cats",
    DOG_AND_CAT,
    date(2026, 8, 18),
)

ALL_SOURCES = (
    MERCK_EMERGENCY,
    ASPCA_EMERGENCY,
    ASPCA_POISON_CONTROL,
    PET_POISON_HELPLINE,
    CORNELL_ANOREXIA,
    ACVS_URINARY_OBSTRUCTION,
    ACVS_URINARY_OBSTRUCTION_DOGS,
    MERCK_URETHRAL_OBSTRUCTION,
    CORNELL_LUTD,
    CORNELL_GDV,
    MISSOURI_VOMITING,
    VCA_THIRST,
    CORNELL_HEATSTROKE,
    CORNELL_DIARRHOEA,
    CORNELL_FELINE_DIARRHOEA,
    VCA_EYE_ISSUES,
    MERCK_ANTERIOR_UVEITIS,
    MERCK_ACUTE_GLAUCOMA,
    MERCK_EYE_ANTI_INFLAMMATORY,
    MERCK_CORROSIVE_EYE_EXPOSURE,
    MERCK_OTITIS_EXTERNA,
    MERCK_OTITIS_MEDIA_INTERNA,
    MERCK_AURICULAR_HEMATOMA,
    VCA_ANOREXIA_DOGS,
    VCA_LIMPING,
    VCA_LIMPING_CATS,
    MERCK_STINGS,
    MERCK_TRAUMA,
    MERCK_DERM_PROBLEMS,
    MERCK_PRURITUS,
    MERCK_SKIN_DIAGNOSIS,
    MERCK_PYODERMA,
    MERCK_DERMATOPHYTOSIS,
)

"""Warning an owner when an analysis contradicts their pet's profile.

Buddy is the case this exists for: a five-year-old Labrador whose analyses came
back as a cat, as a Beagle, and as a puppy — three flat contradictions of a
profile sitting one page away, none of which the app said a word about.

The rule the whole module is written to is that neither side is presumed right.
The profile is typed by a person who may have guessed a rescue's breed; the
model's real-world accuracy has never been measured. Every assertion below
about wording is an assertion that we describe a disagreement rather than
declare a winner.
"""

from datetime import date, timedelta

import pytest

from app.models.animal import AgeCategory, Animal
from app.services.profile_match import breeds_agree, find_conflicts

TODAY = date(2026, 8, 24)
#: Five years old on the nose, as the complaint describes him.
BUDDYS_BIRTHDAY = TODAY - timedelta(days=int(365.25 * 5))


def buddy(**overrides) -> Animal:
    fields = dict(
        name="Buddy",
        species="dog",
        breed="Labrador Retriever",
        birth_date=BUDDYS_BIRTHDAY,
        age_category=AgeCategory.ADULT,
    )
    fields.update(overrides)
    return Animal(**fields)


def result(**overrides) -> dict:
    payload = {
        "model_version": "test-1",
        "species": "dog",
        "species_confidence": 0.93,
        "breed_candidates": [
            {"breed": "Labrador Retriever", "confidence": 0.81},
            {"breed": "Golden Retriever", "confidence": 0.12},
        ],
        "age_estimate": {
            "category": "adult",
            "min_years": 3.0,
            "max_years": 7.0,
            "confidence": 0.7,
        },
        "characteristics": [],
    }
    payload.update(overrides)
    return payload


def fields(conflicts) -> list[str]:
    return [item.field for item in conflicts]


# --------------------------------------------------------------- agreement


def test_a_profile_the_analysis_agrees_with_raises_nothing():
    assert find_conflicts(buddy(), result(), today=TODAY) == []


def test_no_pet_linked_means_nothing_to_contradict():
    """An analysis run before the animal was added has no other side."""
    assert find_conflicts(None, result(), today=TODAY) == []


# ----------------------------------------------------------------- species


def test_a_dog_reported_as_a_cat_is_flagged():
    conflicts = find_conflicts(
        buddy(), result(species="cat", species_confidence=0.91), today=TODAY
    )

    species = [item for item in conflicts if item.field == "species"]
    assert len(species) == 1
    assert species[0].severity == "high"
    assert species[0].profile_says == "dog"
    assert species[0].analysis_says == "cat"


def test_the_species_warning_says_why_it_matters():
    """Not "these differ" but what the difference does.

    Species is the one field other features read: the symptom checker scopes
    its rules by it, so a pet filed under the wrong species is being given
    guidance written for a different animal.
    """
    conflicts = find_conflicts(
        buddy(), result(species="cat", species_confidence=0.91), today=TODAY
    )

    message = conflicts[0].message
    assert "symptom checker" in message
    # And it must not pronounce a winner.
    assert "wrong" not in message.replace("the wrong one", "")


def test_species_is_compared_case_and_space_insensitively():
    """A pet saved as " Dog " has not changed species."""
    assert find_conflicts(buddy(species=" Dog "), result(), today=TODAY) == []


def test_species_is_not_filtered_by_confidence():
    """There is nothing a confidence floor could usefully filter here.

    The classifier chooses between two species, so whichever it names carries
    at least half the probability - a threshold under 0.5 could never fire, and
    one above it would be silencing the model at its most confident. A barely
    won coin flip that contradicts the profile is still two records
    disagreeing, and the panel says so without claiming the model is right.
    """
    conflicts = find_conflicts(
        buddy(), result(species="cat", species_confidence=0.51), today=TODAY
    )

    assert "species" in fields(conflicts)


# ------------------------------------------------------------------- breed


@pytest.mark.parametrize(
    "profile, candidate, expected",
    [
        ("Labrador Retriever", "Labrador Retriever", True),
        ("Labrador Retriever", "labrador retriever", True),
        # The abbreviation people actually type.
        ("Lab", "Labrador Retriever", True),
        ("Labrador", "Labrador Retriever", True),
        # Sharing only the word that names the group is not sharing a breed.
        ("Labrador Retriever", "Golden Retriever", False),
        ("Yorkshire Terrier", "Boston Terrier", False),
        ("Labrador Retriever", "Beagle", False),
        # An owner who wrote only the group has not claimed enough to contradict.
        ("Retriever", "Golden Retriever", True),
        ("", "Beagle", False),
    ],
)
def test_breed_names_are_matched_on_the_distinguishing_word(profile, candidate, expected):
    assert breeds_agree(profile, candidate) is expected


def test_a_labrador_reported_as_a_beagle_is_flagged():
    conflicts = find_conflicts(
        buddy(),
        result(breed_candidates=[{"breed": "Beagle", "confidence": 0.77}]),
        today=TODAY,
    )

    breed = [item for item in conflicts if item.field == "breed"]
    assert len(breed) == 1
    assert breed[0].profile_says == "Labrador Retriever"
    assert breed[0].analysis_says == "Beagle"


def test_a_breed_disagreement_is_ranked_below_a_species_one():
    """Breed is the field this app is least able to be right about and the one
    that changes the least. Ranking it beside a species mismatch would make the
    serious warning look routine."""
    conflicts = find_conflicts(
        buddy(),
        result(
            species="cat",
            species_confidence=0.91,
            breed_candidates=[{"breed": "Beagle", "confidence": 0.77}],
        ),
        today=TODAY,
    )

    assert fields(conflicts)[0] == "species"
    assert [item.severity for item in conflicts][0] == "high"
    assert next(item for item in conflicts if item.field == "breed").severity == "low"


def test_the_profile_breed_lower_down_the_shortlist_is_still_agreement():
    """The model offers a shortlist precisely because it is unsure between
    them. "Your Labrador is second" is not a contradiction worth interrupting
    somebody for."""
    conflicts = find_conflicts(
        buddy(),
        result(
            breed_candidates=[
                {"breed": "Beagle", "confidence": 0.55},
                {"breed": "Labrador Retriever", "confidence": 0.40},
            ]
        ),
        today=TODAY,
    )

    assert "breed" not in fields(conflicts)


def test_a_pet_with_no_breed_recorded_cannot_be_contradicted():
    conflicts = find_conflicts(
        buddy(breed=None),
        result(breed_candidates=[{"breed": "Beagle", "confidence": 0.9}]),
        today=TODAY,
    )

    assert "breed" not in fields(conflicts)


def test_a_very_weak_breed_guess_is_not_a_contradiction():
    conflicts = find_conflicts(
        buddy(),
        result(breed_candidates=[{"breed": "Beagle", "confidence": 0.20}]),
        today=TODAY,
    )

    assert "breed" not in fields(conflicts)


# --------------------------------------------------------------------- age


def test_a_five_year_old_estimated_as_a_puppy_is_flagged():
    """The complaint, exactly."""
    conflicts = find_conflicts(
        buddy(),
        result(
            age_estimate={
                "category": "baby",
                "min_years": 0.0,
                "max_years": 1.0,
                "confidence": 0.8,
            }
        ),
        today=TODAY,
    )

    age = [item for item in conflicts if item.field == "age"]
    assert len(age) == 1
    assert age[0].severity == "high"
    assert "5 years old" in age[0].profile_says
    assert "0.0–1.0 years" in age[0].analysis_says


def test_an_unsure_age_estimate_still_counts_when_the_birth_date_misses_it():
    """The year range IS the model's uncertainty, so it does not get to plead
    uncertainty twice.

    An unsure estimate widens to "8 to 15 years". A documented five-year-old
    falling outside even that is a miss the unsureness has already been given
    its chance to explain - and unlike breed, the profile's side of this
    comparison is a recorded date rather than somebody's guess.
    """
    conflicts = find_conflicts(
        buddy(),
        result(
            age_estimate={
                "category": "senior",
                "min_years": 8.0,
                "max_years": 15.0,
                "confidence": 0.35,
            }
        ),
        today=TODAY,
    )

    assert "age" in fields(conflicts)


def test_a_band_comparison_without_a_birth_date_does_take_a_confidence_floor():
    """No range to lean on here - two band names either match or they do not -
    so an unsure guess is all the filter there is."""
    conflicts = find_conflicts(
        buddy(birth_date=None, age_category=AgeCategory.SENIOR),
        result(
            age_estimate={
                "category": "baby",
                "min_years": 0.0,
                "max_years": 1.0,
                "confidence": 0.20,
            }
        ),
        today=TODAY,
    )

    assert "age" not in fields(conflicts)


def test_a_birth_date_inside_the_estimated_range_is_no_conflict():
    assert "age" not in fields(find_conflicts(buddy(), result(), today=TODAY))


def test_a_month_either_side_of_the_boundary_is_rounding_not_disagreement():
    """A dog three weeks past its first birthday does not contradict "up to a
    year". Flagging that trains people to dismiss the panel."""
    just_over_one = TODAY - timedelta(days=380)
    conflicts = find_conflicts(
        buddy(birth_date=just_over_one),
        result(
            age_estimate={
                "category": "baby",
                "min_years": 0.0,
                "max_years": 1.0,
                "confidence": 0.8,
            }
        ),
        today=TODAY,
    )

    assert "age" not in fields(conflicts)


def test_a_year_outside_the_range_is_low_and_several_years_is_high():
    def gap_of(years: float) -> str:
        birth = TODAY - timedelta(days=int(365.25 * years))
        conflicts = find_conflicts(
            buddy(birth_date=birth),
            result(
                age_estimate={
                    "category": "adult",
                    "min_years": 3.0,
                    "max_years": 7.0,
                    "confidence": 0.8,
                }
            ),
            today=TODAY,
        )
        age = [item for item in conflicts if item.field == "age"]
        return age[0].severity if age else "none"

    assert gap_of(8.0) == "low"
    assert gap_of(12.0) == "high"


def test_without_a_birth_date_neighbouring_bands_are_left_alone():
    """"Adult" and "senior" meet somewhere, and exactly where is a judgement no
    source here settles."""
    conflicts = find_conflicts(
        buddy(birth_date=None, age_category=AgeCategory.ADULT),
        result(
            age_estimate={
                "category": "senior",
                "min_years": 8.0,
                "max_years": 15.0,
                "confidence": 0.8,
            }
        ),
        today=TODAY,
    )

    assert "age" not in fields(conflicts)


def test_without_a_birth_date_distant_bands_are_flagged():
    conflicts = find_conflicts(
        buddy(birth_date=None, age_category=AgeCategory.SENIOR),
        result(
            age_estimate={
                "category": "baby",
                "min_years": 0.0,
                "max_years": 1.0,
                "confidence": 0.8,
            }
        ),
        today=TODAY,
    )

    age = [item for item in conflicts if item.field == "age"]
    assert len(age) == 1 and age[0].severity == "high"


def test_an_unknown_age_on_the_profile_cannot_be_contradicted():
    conflicts = find_conflicts(
        buddy(birth_date=None, age_category=AgeCategory.UNKNOWN),
        result(
            age_estimate={
                "category": "baby",
                "min_years": 0.0,
                "max_years": 1.0,
                "confidence": 0.8,
            }
        ),
        today=TODAY,
    )

    assert "age" not in fields(conflicts)


# ------------------------------------------------------------- corrections


def test_correcting_the_analysis_settles_the_disagreement():
    """A warning that survives the fix is one people learn to click past."""
    wrong = result(species="cat", species_confidence=0.91)

    assert "species" in fields(find_conflicts(buddy(), wrong, today=TODAY))
    assert "species" not in fields(
        find_conflicts(buddy(), wrong, {"species": "dog"}, today=TODAY)
    )


def test_a_correction_that_still_disagrees_is_still_flagged():
    """Two things the OWNER wrote contradicting each other is a different
    problem from the model contradicting them, and the flag says which."""
    conflicts = find_conflicts(
        buddy(), result(), {"breed": "Beagle"}, today=TODAY
    )

    breed = [item for item in conflicts if item.field == "breed"]
    assert len(breed) == 1
    assert breed[0].analysis_says == "Beagle"
    assert breed[0].from_correction is True


def test_a_correction_counts_however_unsure_the_model_was():
    """The confidence floor exists to filter out the model shrugging. A person
    stating something is not shrugging."""
    conflicts = find_conflicts(
        buddy(),
        result(species="cat", species_confidence=0.05),
        {"species": "cat"},
        today=TODAY,
    )

    assert "species" in fields(conflicts)


# -------------------------------------------------------- all three at once


def test_buddys_worst_case_reports_all_three_in_order():
    """The complaint verbatim: conflicting breed, age, and species."""
    conflicts = find_conflicts(
        buddy(),
        result(
            species="cat",
            species_confidence=0.91,
            breed_candidates=[{"breed": "Maine Coon", "confidence": 0.72}],
            age_estimate={
                "category": "baby",
                "min_years": 0.0,
                "max_years": 1.0,
                "confidence": 0.83,
            },
        ),
        today=TODAY,
    )

    assert sorted(fields(conflicts)) == ["age", "breed", "species"]
    # Both of the ones that change what the app does come before the one that
    # does not.
    assert fields(conflicts)[-1] == "breed"
    assert all(f"Buddy" in item.message for item in conflicts)

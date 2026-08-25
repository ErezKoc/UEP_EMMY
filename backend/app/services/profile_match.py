"""Where an analysis and the pet's own profile disagree.

The app holds two accounts of what an animal is: what the owner wrote down, and
what the model saw in a photograph. Until now they were shown side by side on
different pages and never compared, so an analysis could come back "cat" for a
dog, "Beagle" for a Labrador and "baby" for a five-year-old, and each one was
just a number on a card. The owner had to notice.

The framing throughout is DISAGREEMENT, not error, and that is the whole design.
This module cannot know which side is wrong. The profile is typed by a person
who may have guessed the breed of a rescue; the model is a classifier whose
real-world accuracy, as the results page says in so many words, nobody has
measured. Naming one of them as correct would be inventing a fact. So a conflict
says what each side claims, how strongly, and offers both ways out - fix the
analysis, or fix the profile.

Computed on demand, never stored. A stored conflict is a stale one the moment
the owner edits the profile or corrects the analysis, and a warning that will
not go away after you have fixed the thing it complains about teaches people to
ignore warnings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from app.core.species import normalise_species
from app.models.animal import AgeCategory, Animal

Severity = Literal["high", "low"]
Field = Literal["species", "breed", "age"]

#: Below this, a BREED guess is not disagreeing with the profile - it is
#: admitting it does not know.
#:
#: The bands on the results page call 0.65 a "good match" and anything under
#: 0.45 a "very weak match". Warning an owner that a very weak match disagrees
#: with them is telling them that something which said "I am not sure" is not
#: sure, and every one of those costs attention the species mismatch needs.
#:
#: Applied to breed only, and the other two fields are worth saying why:
#:
#: * Species is a two-way split, so the winning class is always at least 0.5
#:   and this threshold could never bind. It is not applied there rather than
#:   applied uselessly - a filter that cannot fire reads like protection that
#:   does not exist.
#: * Age is not filtered by confidence at all, because it ships a YEAR RANGE
#:   and the range is already the model's uncertainty. An unsure estimate says
#:   "8 to 15 years"; a documented five-year-old falling outside even that is a
#:   miss the unsureness has already been given the chance to explain.
MIN_BREED_CONFIDENCE_TO_DISAGREE = 0.45

#: How the age bands sit next to each other, for deciding whether two of them
#: are a real disagreement or a boundary case.
_AGE_ORDER = [AgeCategory.BABY, AgeCategory.YOUNG, AgeCategory.ADULT, AgeCategory.SENIOR]

#: Breed words that name a GROUP rather than a breed.
#:
#: Without this, "Golden Retriever" and "Labrador Retriever" share a token and
#: would be taken for the same dog. The distinguishing word is the one that has
#: to match.
_GENERIC_BREED_WORDS = frozenset(
    {
        "retriever",
        "terrier",
        "shepherd",
        "spaniel",
        "hound",
        "setter",
        "pointer",
        "sheepdog",
        "shorthair",
        "longhair",
        "haired",
        "hair",
        "short",
        "long",
        "dog",
        "cat",
        "mix",
        "mixed",
        "cross",
        "crossbreed",
        "crossbred",
        "breed",
        "type",
        "standard",
        "miniature",
        "toy",
        "giant",
        "domestic",
    }
)


@dataclass(frozen=True)
class ProfileConflict:
    """One thing the profile and the analysis do not agree about."""

    field: Field
    severity: Severity
    #: What the pet's profile says, in words an owner will recognise.
    profile_says: str
    #: What the analysis says, after any correction the owner has made.
    analysis_says: str
    #: One sentence naming the disagreement. Never asserts which is right.
    message: str
    #: Whether `analysis_says` came from the owner's own correction rather than
    #: the model. It changes what the sentence can honestly claim: two things
    #: the OWNER wrote disagreeing with each other is a different problem from
    #: the model disagreeing with them.
    from_correction: bool = False


def _tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.casefold()) if token]


def _token_matches(left: str, right: str) -> bool:
    """Same word, allowing one to be an abbreviation of the other.

    "lab" and "labrador" are the same dog. Prefix matching from three
    characters catches the abbreviations people actually type, and errs towards
    calling two breeds the same - which is the safe direction here, because the
    cost of a wrong match is a warning we do not raise, and the cost of a wrong
    mismatch is telling somebody their profile is wrong when it is not.
    """
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 3 and longer.startswith(shorter)


def breeds_agree(profile_breed: str | None, candidate: str | None) -> bool:
    """Do these two names plausibly describe the same breed?

    Compares the DISTINCTIVE words - "Labrador Retriever" against "Golden
    Retriever" disagree, because the only word they share names the group both
    belong to. When one of the names is nothing but group words ("Retriever",
    "Mixed breed"), it is compared on those instead: an owner who wrote only
    "Retriever" has not claimed a breed precise enough to contradict.
    """
    if not profile_breed or not candidate:
        return False

    left, right = _tokens(profile_breed), _tokens(candidate)
    if not left or not right:
        return False

    left_key = [token for token in left if token not in _GENERIC_BREED_WORDS]
    right_key = [token for token in right if token not in _GENERIC_BREED_WORDS]

    # The fallback has to drop BOTH sides back to their full names, not just
    # the one that ran out of distinctive words. Comparing bare "Retriever"
    # against the distinctive half of "Golden Retriever" leaves "retriever"
    # facing "golden" - two names for the same dog, reported as a contradiction.
    if not left_key or not right_key:
        left_key, right_key = left, right

    return any(
        _token_matches(one, other) for one in left_key for other in right_key
    )


def _age_years(animal: Animal, today: date) -> float | None:
    """The pet's age from its birth date, or None if it has none recorded."""
    if animal.birth_date is None:
        return None
    return (today - animal.birth_date).days / 365.25


def _describe_years(years: float) -> str:
    if years < 1:
        months = max(1, round(years * 12))
        return f"{months} month{'s' if months != 1 else ''} old"
    rounded = round(years, 1)
    whole = int(rounded)
    if rounded == whole:
        return f"{whole} year{'s' if whole != 1 else ''} old"
    return f"{rounded} years old"


def _effective(result: dict[str, Any], correction: dict[str, Any] | None, key: str) -> Any:
    """The analysis's current answer for one field.

    A correction wins over the model, because the correction is the owner
    telling us the model was wrong and the interface already shows their
    version. Comparing the model's superseded answer would raise a warning
    about a disagreement that has been settled.
    """
    if correction and correction.get(key):
        return correction[key]
    return None


def find_conflicts(
    animal: Animal | None,
    result: dict[str, Any] | None,
    correction: dict[str, Any] | None = None,
    *,
    today: date | None = None,
) -> list[ProfileConflict]:
    """Everything this analysis and this pet's profile disagree about.

    Returns an empty list when there is nothing to compare against - an
    analysis with no pet linked has no profile to contradict, and one whose pet
    was deleted has lost the other half of the comparison.
    """
    if animal is None or not result:
        return []

    today = today or date.today()
    conflicts: list[ProfileConflict] = []

    # ----------------------------------------------------------- species
    corrected_species = _effective(result, correction, "species")
    model_species = corrected_species or result.get("species")
    profile_species = animal.species
    if normalise_species(profile_species) and normalise_species(model_species):
        # No confidence floor here. The classifier chooses between two species,
        # so whichever it names carries at least half the probability and any
        # threshold under 0.5 would be decoration. If it ever grows a third
        # class, this is where the check belongs.
        if normalise_species(profile_species) != normalise_species(model_species):
            conflicts.append(
                ProfileConflict(
                    field="species",
                    # Always high. Species is the one field other features
                    # read: the symptom checker scopes its rules by it, so
                    # a pet filed under the wrong species gets guidance
                    # written for a different animal.
                    severity="high",
                    profile_says=str(profile_species),
                    analysis_says=str(model_species),
                    from_correction=bool(corrected_species),
                    message=(
                        f"{animal.name}'s profile says {profile_species}, but this "
                        f"analysis says {model_species}. The symptom checker uses the "
                        f"species on the profile, so if the profile is the wrong one it "
                        f"is answering for a different animal."
                    ),
                )
            )

    # ------------------------------------------------------------- breed
    corrected_breed = _effective(result, correction, "breed")
    candidates = result.get("breed_candidates") or []
    if animal.breed and (corrected_breed or candidates):
        if corrected_breed:
            agrees = breeds_agree(animal.breed, corrected_breed)
            said, strength = corrected_breed, None
        else:
            # Compared against EVERY candidate, not only the top one. The model
            # offers a shortlist precisely because it is unsure between them,
            # and "your Labrador is second on the list" is agreement, not a
            # contradiction worth interrupting somebody for.
            agrees = any(
                breeds_agree(animal.breed, item.get("breed")) for item in candidates
            )
            top = max(candidates, key=lambda item: item.get("confidence") or 0)
            said = str(top.get("breed") or "")
            strength = float(top.get("confidence") or 0)

        if not agrees and said:
            if corrected_breed or (strength or 0) >= MIN_BREED_CONFIDENCE_TO_DISAGREE:
                conflicts.append(
                    ProfileConflict(
                        field="breed",
                        # Low, and deliberately so. Breed is the field this app
                        # is least able to be right about and the one that
                        # changes the least: nothing else reads it, and a
                        # mixed-breed rescue will disagree with any classifier
                        # forever. Ranking it beside a species mismatch would
                        # make the serious warning look routine.
                        severity="low",
                        profile_says=animal.breed,
                        analysis_says=said,
                        from_correction=bool(corrected_breed),
                        message=(
                            f"{animal.name}'s profile says {animal.breed}, and this analysis "
                            f"did not put that among its suggestions - its closest was "
                            f"{said}. Mixed breeds and unusual coats often read this way, so "
                            f"this is worth a look rather than a worry."
                        ),
                    )
                )

    # --------------------------------------------------------------- age
    conflict = _age_conflict(animal, result, correction, today)
    if conflict is not None:
        conflicts.append(conflict)

    # The one that changes what other features do goes first, whatever order
    # the checks happen to run in.
    conflicts.sort(key=lambda item: 0 if item.severity == "high" else 1)
    return conflicts


def _age_conflict(
    animal: Animal,
    result: dict[str, Any],
    correction: dict[str, Any] | None,
    today: date,
) -> ProfileConflict | None:
    """Does the estimated age contradict the age on the profile?

    A recorded birth date is checked against the estimate's YEAR RANGE rather
    than its band, because it is a fact and the range is what the model
    actually claimed. Falling back to comparing bands is for pets with no birth
    date, and there a neighbouring band is not a disagreement - "adult" and
    "senior" meet somewhere, and exactly where is a judgement no source here
    settles.
    """
    estimate = result.get("age_estimate") or {}
    corrected_age = _effective(result, correction, "age_category")
    if not estimate and not corrected_age:
        return None

    said_band = corrected_age or estimate.get("category")
    if not said_band:
        return None
    try:
        said = AgeCategory(said_band)
    except ValueError:
        return None

    years = _age_years(animal, today)
    if years is not None and not corrected_age:
        low = estimate.get("min_years")
        high = estimate.get("max_years")
        if low is None or high is None:
            return None
        if low <= years <= high:
            return None
        # A month either side of the boundary is the rounding, not a
        # disagreement - a dog three weeks past its first birthday is not a
        # contradiction of "up to 1 year".
        margin = 1 / 12
        if years < float(low) - margin:
            gap = float(low) - years
        elif years > float(high) + margin:
            gap = years - float(high)
        else:
            return None
        return ProfileConflict(
            field="age",
            # A year out is a boundary quarrel; several years out means one of
            # the two records is about a different animal, or the birth date is
            # wrong - and a wrong birth date quietly changes what the symptom
            # checker does for the very young and the very old.
            severity="high" if gap >= 2 else "low",
            profile_says=f"{_describe_years(years)} (born {animal.birth_date:%d %b %Y})",
            analysis_says=f"{said.value} — about {low}–{high} years",
            message=(
                f"{animal.name}'s profile gives a birth date making them "
                f"{_describe_years(years)}, but this analysis estimated {low}–{high} years. "
                f"One of the two is about a different animal, or the birth date needs a fix."
            ),
        )

    # No birth date: compare the bands, and let neighbours be.
    #
    # This path DOES take a confidence floor, unlike the one above. There is no
    # year range here to absorb the model's uncertainty - two band names either
    # match or they do not - so an unsure guess is all the filter there is.
    if not corrected_age and float(estimate.get("confidence") or 0) < MIN_BREED_CONFIDENCE_TO_DISAGREE:
        return None

    profile_band = animal.age_category
    if profile_band in (None, AgeCategory.UNKNOWN) or said is AgeCategory.UNKNOWN:
        return None
    if profile_band == said:
        return None
    try:
        distance = abs(_AGE_ORDER.index(profile_band) - _AGE_ORDER.index(said))
    except ValueError:
        return None
    if distance < 2:
        return None
    return ProfileConflict(
        field="age",
        severity="high",
        profile_says=profile_band.value,
        analysis_says=said.value,
        from_correction=bool(corrected_age),
        message=(
            f"{animal.name}'s profile says {profile_band.value}, but this analysis says "
            f"{said.value}. Those are not neighbouring stages, so they are unlikely to be "
            f"the same animal at the same time."
        ),
    )

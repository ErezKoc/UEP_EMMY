"""Declarative conditions a rule can test.

Rules are data, not code: a condition both evaluates an intake and describes
itself in plain language, so `python -m app.services.triage.report` can print
the entire clinical logic as English sentences for a veterinarian to review
without reading any Python.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.core.species import normalise_species
from app.models.animal import AgeCategory
from app.schemas.triage import (
    BodyArea,
    Concern,
    Duration,
    RedFlag,
    SymptomIntake,
    TimeSinceEating,
    Trend,
)


@runtime_checkable
class Condition(Protocol):
    def matches(self, intake: SymptomIntake) -> bool: ...

    def describe(self) -> str: ...


def _phrase(value: str) -> str:
    return value.replace("_", " ")


@dataclass(frozen=True)
class HasRedFlag:
    flag: RedFlag

    def matches(self, intake: SymptomIntake) -> bool:
        return self.flag in intake.red_flags

    def describe(self) -> str:
        return f"the owner reported {_phrase(self.flag.value)}"


@dataclass(frozen=True)
class ConcernIs:
    concern: Concern

    def matches(self, intake: SymptomIntake) -> bool:
        return intake.concern is self.concern

    def describe(self) -> str:
        return f"the concern is {_phrase(self.concern.value)}"


@dataclass(frozen=True)
class BodyAreaIn:
    areas: tuple[BodyArea, ...]

    def matches(self, intake: SymptomIntake) -> bool:
        return intake.body_area in self.areas

    def describe(self) -> str:
        return "the affected area is " + " or ".join(_phrase(area.value) for area in self.areas)


_DURATION_LABELS: dict[Duration, str] = {
    Duration.TODAY: "started today",
    Duration.DAYS_2_7: "lasted 2–7 days",
    Duration.WEEKS_1_4: "lasted 1–4 weeks",
    Duration.OVER_MONTH: "lasted over a month",
}


@dataclass(frozen=True)
class DurationIn:
    durations: tuple[Duration, ...]

    def matches(self, intake: SymptomIntake) -> bool:
        return intake.duration in self.durations

    def describe(self) -> str:
        return "it has " + " or ".join(_DURATION_LABELS[d] for d in self.durations)


@dataclass(frozen=True)
class TrendIs:
    trend: Trend

    def matches(self, intake: SymptomIntake) -> bool:
        return intake.trend is self.trend

    def describe(self) -> str:
        return f"the problem is {self.trend.value}"


@dataclass(frozen=True)
class NotEatingFor:
    """Time since the animal last ate, for the Cornell feline thresholds."""

    buckets: tuple[TimeSinceEating, ...]

    def matches(self, intake: SymptomIntake) -> bool:
        return intake.time_since_eating in self.buckets

    def describe(self) -> str:
        labels = {
            TimeSinceEating.UNDER_12H: "under 12 hours",
            TimeSinceEating.H12_TO_24H: "12–24 hours",
            TimeSinceEating.OVER_24H: "more than 24 hours",
        }
        return "it has not eaten for " + " or ".join(labels[b] for b in self.buckets)


@dataclass(frozen=True)
class CannotBearWeight:
    def matches(self, intake: SymptomIntake) -> bool:
        return intake.weight_bearing is False

    def describe(self) -> str:
        return "the animal will not put weight on the limb"


@dataclass(frozen=True)
class SpeciesIs:
    species: str

    def matches(self, intake: SymptomIntake) -> bool:
        # Uses the same normalisation as `Rule.matches`. When these two
        # disagreed, a species of " cat " passed the rule's species scope and
        # failed here, so every SpeciesIs-gated rule — all of them emergencies —
        # silently stopped firing for that pet.
        return normalise_species(intake.species) == normalise_species(self.species)

    def describe(self) -> str:
        return f"the animal is a {self.species}"


_AGE_LABELS: dict[AgeCategory, str] = {
    AgeCategory.BABY: "a puppy or kitten",
    AgeCategory.YOUNG: "young",
    AgeCategory.ADULT: "an adult",
    AgeCategory.SENIOR: "a senior",
}


@dataclass(frozen=True)
class AgeIn:
    categories: tuple[AgeCategory, ...]

    def matches(self, intake: SymptomIntake) -> bool:
        return intake.age_category in self.categories

    def describe(self) -> str:
        return "the animal is " + " or ".join(_AGE_LABELS.get(c, c.value) for c in self.categories)


@dataclass(frozen=True)
class IsFragilePatient:
    """Very young, very old, or already chronically ill.

    Missouri treats these animals as needing attention sooner than an otherwise
    healthy adult with the same signs.
    """

    def matches(self, intake: SymptomIntake) -> bool:
        return (
            intake.has_chronic_illness is True
            or intake.age_category in (AgeCategory.BABY, AgeCategory.SENIOR)
        )

    def describe(self) -> str:
        return "the animal is very young, elderly, or has a chronic illness"


@dataclass(frozen=True)
class All:
    """Every sub-condition must hold."""

    conditions: tuple[Condition, ...]

    def matches(self, intake: SymptomIntake) -> bool:
        return all(condition.matches(intake) for condition in self.conditions)

    def describe(self) -> str:
        return " and ".join(condition.describe() for condition in self.conditions)


@dataclass(frozen=True)
class Any_:
    """At least one sub-condition must hold."""

    conditions: tuple[Condition, ...]

    def matches(self, intake: SymptomIntake) -> bool:
        return any(condition.matches(intake) for condition in self.conditions)

    def describe(self) -> str:
        return "(" + " or ".join(condition.describe() for condition in self.conditions) + ")"

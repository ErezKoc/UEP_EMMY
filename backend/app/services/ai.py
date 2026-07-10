"""Image-analysis abstraction.

`ImageAnalysisService` defines the contract; `MockImageAnalysisService` is the
MVP implementation. A future `RekognitionAnalysisService` (AWS Rekognition or
a SageMaker endpoint) implements the same `analyze` signature and returns the
same `AnalysisResult` schema, then gets swapped in via `get_analysis_service`.
"""

import hashlib
from abc import ABC, abstractmethod
from functools import lru_cache

from app.models.animal import AgeCategory
from app.schemas.analysis import AgeEstimate, AnalysisResult, BreedCandidate

# Species profiles the mock can "detect", with breed pools and per-life-stage
# age windows (in years) used to fabricate plausible estimates.
_SPECIES_PROFILES: list[dict] = [
    {
        "species": "dog",
        "breeds": [
            ("Labrador Retriever", ["short coat", "floppy ears", "athletic build"]),
            ("German Shepherd", ["erect ears", "double coat", "sloped back"]),
            ("Golden Retriever", ["long golden coat", "feathered tail", "broad head"]),
            ("French Bulldog", ["bat ears", "compact build", "brachycephalic muzzle"]),
            ("Border Collie", ["medium coat", "alert expression", "agile frame"]),
        ],
        "age_windows": {
            AgeCategory.BABY: (0.0, 1.0),
            AgeCategory.YOUNG: (1.0, 3.0),
            AgeCategory.ADULT: (3.0, 8.0),
            AgeCategory.SENIOR: (8.0, 14.0),
        },
    },
    {
        "species": "cat",
        "breeds": [
            ("Domestic Shorthair", ["short coat", "lean build", "almond eyes"]),
            ("Maine Coon", ["long shaggy coat", "tufted ears", "large frame"]),
            ("Siamese", ["colorpoint coat", "blue eyes", "slender body"]),
            ("British Shorthair", ["dense plush coat", "round face", "stocky build"]),
            ("Bengal", ["spotted rosette coat", "muscular build", "wild markings"]),
        ],
        "age_windows": {
            AgeCategory.BABY: (0.0, 0.5),
            AgeCategory.YOUNG: (0.5, 2.0),
            AgeCategory.ADULT: (2.0, 10.0),
            AgeCategory.SENIOR: (10.0, 16.0),
        },
    },
    {
        "species": "rabbit",
        "breeds": [
            ("Holland Lop", ["lopped ears", "compact body", "rounded head"]),
            ("Netherland Dwarf", ["tiny frame", "short ears", "round face"]),
            ("Flemish Giant", ["very large frame", "long ears", "dense coat"]),
        ],
        "age_windows": {
            AgeCategory.BABY: (0.0, 0.3),
            AgeCategory.YOUNG: (0.3, 1.0),
            AgeCategory.ADULT: (1.0, 6.0),
            AgeCategory.SENIOR: (6.0, 10.0),
        },
    },
]

_AGE_ORDER = [AgeCategory.BABY, AgeCategory.YOUNG, AgeCategory.ADULT, AgeCategory.SENIOR]


class ImageAnalysisService(ABC):
    @abstractmethod
    def analyze(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        """Analyze a pet image and return structured species/breed/age estimates."""


class MockImageAnalysisService(ImageAnalysisService):
    """Deterministic mock: the same image always yields the same result.

    All "predictions" are derived from the SHA-256 digest of the image bytes,
    which makes demos reproducible and unit tests stable, while still varying
    realistically between different images.
    """

    MODEL_VERSION = "mock-vision-0.3.0"

    def analyze(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        digest = hashlib.sha256(image_bytes).digest()

        profile = _SPECIES_PROFILES[digest[0] % len(_SPECIES_PROFILES)]
        species_confidence = self._confidence(digest[1], low=0.82, high=0.99)

        breed_candidates, characteristics = self._pick_breeds(profile, digest)
        age_estimate = self._estimate_age(profile, digest)

        return AnalysisResult(
            model_version=self.MODEL_VERSION,
            species=profile["species"],
            species_confidence=species_confidence,
            breed_candidates=breed_candidates,
            age_estimate=age_estimate,
            characteristics=characteristics,
        )

    @staticmethod
    def _confidence(byte_value: int, low: float, high: float) -> float:
        return round(low + (byte_value / 255) * (high - low), 4)

    def _pick_breeds(
        self, profile: dict, digest: bytes
    ) -> tuple[list[BreedCandidate], list[str]]:
        breeds = profile["breeds"]
        primary_index = digest[2] % len(breeds)
        secondary_index = (primary_index + 1 + digest[3] % (len(breeds) - 1)) % len(breeds)

        primary_confidence = self._confidence(digest[4], low=0.55, high=0.93)
        secondary_confidence = round(
            min(primary_confidence - 0.1, self._confidence(digest[5], low=0.05, high=0.35)), 4
        )

        primary_breed, primary_traits = breeds[primary_index]
        secondary_breed, _ = breeds[secondary_index]

        candidates = [
            BreedCandidate(breed=primary_breed, confidence=primary_confidence),
            BreedCandidate(breed=secondary_breed, confidence=max(secondary_confidence, 0.05)),
        ]
        return candidates, primary_traits

    def _estimate_age(self, profile: dict, digest: bytes) -> AgeEstimate:
        category = _AGE_ORDER[digest[6] % len(_AGE_ORDER)]
        min_years, max_years = profile["age_windows"][category]
        return AgeEstimate(
            category=category,
            min_years=min_years,
            max_years=max_years,
            confidence=self._confidence(digest[7], low=0.60, high=0.90),
        )


@lru_cache
def get_analysis_service() -> ImageAnalysisService:
    return MockImageAnalysisService()

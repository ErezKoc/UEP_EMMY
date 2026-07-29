"""Image-analysis abstraction.

`ImageAnalysisService` defines the contract; `MockImageAnalysisService` is the
MVP implementation. A future `RekognitionAnalysisService` (AWS Rekognition or
a SageMaker endpoint) implements the same `analyze` signature and returns the
same `AnalysisResult` schema, then gets swapped in via `get_analysis_service`.
"""

import hashlib
import io
import os
import logging
from abc import ABC, abstractmethod
from functools import lru_cache

try:
    import numpy as np
    import onnxruntime as ort
    from PIL import Image
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

from app.models.animal import AgeCategory
from app.schemas.analysis import AgeEstimate, AnalysisResult, BreedCandidate

logger = logging.getLogger(__name__)

BREED_MAP = [
    "Abyssinian", "American Bulldog", "American Pit Bull Terrier", 
    "Basset Hound", "Beagle", "Bengal", "Birman", "Bombay", "Boxer", 
    "British Shorthair", "Chihuahua", "Egyptian Mau", 
    "English Cocker Spaniel", "English Setter", "German Shorthaired", 
    "Great Pyrenees", "Havanese", "Japanese Chin", "Keeshond", 
    "Leonberger", "Maine Coon", "Miniature Pinscher", "Newfoundland", 
    "Persian", "Pomeranian", "Pug", "Ragdoll", "Russian Blue", 
    "Saint Bernard", "Samoyed", "Scottish Terrier", "Shiba Inu", 
    "Siamese", "Sphynx", "Staffordshire Bull Terrier", 
    "Wheaten Terrier", "Yorkshire Terrier"
]

AGE_MAP = [
    "Puppy/Kitten", 
    "Adult", 
    "Senior"
]

# We determine cat vs dog in the mock simply by checking if the breed is known to be a cat
_CAT_BREEDS = {"Abyssinian", "Bengal", "Birman", "Bombay", "British Shorthair", "Egyptian Mau", "Maine Coon", "Persian", "Ragdoll", "Russian Blue", "Siamese", "Sphynx"}

class ImageAnalysisService(ABC):
    @abstractmethod
    def analyze(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        """Analyze a pet image and return structured species/breed/age estimates."""


class ONNXImageAnalysisService(ImageAnalysisService):
    """Real implementation that uses ONNX models for breed and age classification."""

    MODEL_VERSION = "onnx-custom-1.0.0"

    def __init__(self, breed_model_path: str, age_model_path: str):
        if not ONNX_AVAILABLE:
            raise RuntimeError("Required packages (onnxruntime, Pillow, numpy) are not installed.")
        
        self.breed_session = ort.InferenceSession(breed_model_path)
        self.age_session = ort.InferenceSession(age_model_path)
        
        # We assume a standard image classification input shape: [1, 3, 224, 224]
        self.input_shape = (224, 224)

    def _preprocess_image(self, image_bytes: bytes) -> "np.ndarray":
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize(self.input_shape, Image.Resampling.BILINEAR)
        img_arr = np.array(img).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_arr = (img_arr - mean) / std
        img_arr = np.transpose(img_arr, (2, 0, 1))
        img_arr = np.expand_dims(img_arr, axis=0)
        return img_arr

    def _softmax(self, x: "np.ndarray") -> "np.ndarray":
        e_x = np.exp(x - np.max(x, axis=1, keepdims=True))
        return e_x / e_x.sum(axis=1, keepdims=True)

    def analyze(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        input_tensor = self._preprocess_image(image_bytes)
        
        # --- Breed Inference ---
        breed_input_name = self.breed_session.get_inputs()[0].name
        breed_logits = self.breed_session.run(None, {breed_input_name: input_tensor})[0]
        breed_probs = self._softmax(breed_logits)[0]
        
        top_2_idx = np.argsort(breed_probs)[-2:][::-1]
        primary_idx, secondary_idx = top_2_idx[0], top_2_idx[1]
        
        breed_candidates = [
            BreedCandidate(breed=BREED_MAP[primary_idx], confidence=float(breed_probs[primary_idx])),
            BreedCandidate(breed=BREED_MAP[secondary_idx], confidence=float(breed_probs[secondary_idx])),
        ]
        
        # --- Age Inference ---
        age_input_name = self.age_session.get_inputs()[0].name
        age_logits = self.age_session.run(None, {age_input_name: input_tensor})[0]
        age_probs = self._softmax(age_logits)[0]
        
        top_age_idx = int(np.argmax(age_probs))
        age_label = AGE_MAP[top_age_idx]
        age_confidence = float(age_probs[top_age_idx])
        
        if age_label == "Puppy/Kitten":
            category = AgeCategory.BABY
            min_years, max_years = 0.0, 1.0
        elif age_label == "Adult":
            category = AgeCategory.ADULT
            min_years, max_years = 1.0, 8.0
        else: # "Senior"
            category = AgeCategory.SENIOR
            min_years, max_years = 8.0, 15.0

        primary_breed_name = BREED_MAP[primary_idx]
        cat_prob = float(sum(breed_probs[i] for i, b in enumerate(BREED_MAP) if b in _CAT_BREEDS))
        dog_prob = float(1.0 - cat_prob)
        if cat_prob > dog_prob:
            species = "cat"
            species_confidence = round(cat_prob, 4)
        else:
            species = "dog"
            species_confidence = round(dog_prob, 4)

        return AnalysisResult(
            model_version=self.MODEL_VERSION,
            species=species,
            species_confidence=species_confidence,
            breed_candidates=breed_candidates,
            age_estimate=AgeEstimate(
                category=category,
                min_years=min_years,
                max_years=max_years,
                confidence=round(age_confidence, 4)
            ),
            characteristics=[]
        )


class MockImageAnalysisService(ImageAnalysisService):
    """Deterministic mock updated to use the new BREED_MAP and AGE_MAP.

    It still uses the SHA-256 digest to randomly (but deterministically) 
    pick outputs, but now it selects exclusively from the new label sets!
    """

    MODEL_VERSION = "mock-vision-0.4.0"

    def analyze(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        digest = hashlib.sha256(image_bytes).digest()

        # Deterministically pick a primary and secondary breed from the new map
        primary_idx = digest[0] % len(BREED_MAP)
        secondary_idx = (primary_idx + 1 + digest[1] % (len(BREED_MAP) - 1)) % len(BREED_MAP)

        primary_breed = BREED_MAP[primary_idx]
        secondary_breed = BREED_MAP[secondary_idx]

        primary_confidence = self._confidence(digest[2], low=0.55, high=0.93)
        secondary_confidence = round(
            min(primary_confidence - 0.1, self._confidence(digest[3], low=0.05, high=0.35)), 4
        )

        breed_candidates = [
            BreedCandidate(breed=primary_breed, confidence=primary_confidence),
            BreedCandidate(breed=secondary_breed, confidence=max(secondary_confidence, 0.05)),
        ]

        # Determine species based on the breed
        species = "cat" if primary_breed in _CAT_BREEDS else "dog"
        species_confidence = self._confidence(digest[4], low=0.82, high=0.99)

        # Deterministically pick an age from the new map
        age_idx = digest[5] % len(AGE_MAP)
        age_label = AGE_MAP[age_idx]

        if age_label == "Puppy/Kitten":
            category = AgeCategory.BABY
            min_years, max_years = 0.0, 1.0
        elif age_label == "Adult":
            category = AgeCategory.ADULT
            min_years, max_years = 1.0, 8.0
        else:
            category = AgeCategory.SENIOR
            min_years, max_years = 8.0, 15.0

        age_confidence = self._confidence(digest[6], low=0.60, high=0.90)
        age_estimate = AgeEstimate(
            category=category,
            min_years=min_years,
            max_years=max_years,
            confidence=age_confidence,
        )

        return AnalysisResult(
            model_version=self.MODEL_VERSION,
            species=species,
            species_confidence=species_confidence,
            breed_candidates=breed_candidates,
            age_estimate=age_estimate,
            characteristics=[],
        )

    @staticmethod
    def _confidence(byte_value: int, low: float, high: float) -> float:
        return round(low + (byte_value / 255) * (high - low), 4)


@lru_cache
def get_analysis_service() -> ImageAnalysisService:
    breed_model_path = os.path.join(os.path.dirname(__file__), "..", "..", "pet_breed_model.onnx")
    age_model_path = os.path.join(os.path.dirname(__file__), "..", "..", "pet_age_model.onnx")

    if os.path.exists(breed_model_path) and os.path.exists(age_model_path):
        try:
            service = ONNXImageAnalysisService(breed_model_path, age_model_path)
            logger.info("ONNX models loaded — using ONNXImageAnalysisService.")
            return service
        except Exception as e:
            logger.warning(f"Failed to load ONNX models, falling back to mock. Error: {e}")

    logger.info("ONNX models not found — using MockImageAnalysisService.")
    return MockImageAnalysisService()

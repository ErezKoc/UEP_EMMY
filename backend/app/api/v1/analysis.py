import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import AIAnalysisLog, Animal
from app.schemas import AnalysisResponse, AnalysisResult
from app.services.ai import ImageAnalysisService, get_analysis_service
from app.services.storage import StorageService, get_storage_service

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/upload", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_analyze(
    file: UploadFile = File(...),
    animal_id: uuid.UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
    analyzer: ImageAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    """Accept a pet image, store it, run AI analysis, and persist the log."""
    settings = get_settings()

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type {file.content_type!r}. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}.",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    if len(image_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {settings.max_upload_mb} MB upload limit.",
        )

    if animal_id is not None and db.get(Animal, animal_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Animal {animal_id} not found."
        )

    key = storage.build_key("uploads", file.filename or "image")
    stored = storage.put_object(key, image_bytes, file.content_type)

    result: AnalysisResult = analyzer.analyze(image_bytes, file.filename or "image")

    log = AIAnalysisLog(
        animal_id=animal_id,
        image_key=stored.key,
        image_url=stored.url,
        model_version=result.model_version,
        species=result.species,
        species_confidence=result.species_confidence,
        result=result.model_dump(mode="json"),
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return AnalysisResponse(
        analysis_id=log.id,
        animal_id=log.animal_id,
        image_url=log.image_url,
        created_at=log.created_at,
        result=result,
    )

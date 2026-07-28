import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_optional_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AIAnalysisLog, Animal, User
from app.schemas import AnalysisHistoryItem, AnalysisResponse, AnalysisResult
from app.services.ai import ImageAnalysisService, get_analysis_service
from app.services.storage import StorageService, get_storage_service

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/upload", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_analyze(
    file: UploadFile = File(...),
    animal_id: uuid.UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
    storage: StorageService = Depends(get_storage_service),
    analyzer: ImageAnalysisService = Depends(get_analysis_service),
) -> AnalysisResponse:
    """Accept a pet image, store it, run AI analysis, and persist the log.

    Signed-in uploads are attributed to the user (and appear in their history);
    anonymous uploads still work for the public dashboard demo. Linking to a
    pet requires being signed in as that pet's owner.
    """
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

    if animal_id is not None:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sign in to link an analysis to one of your pets.",
            )
        animal = db.get(Animal, animal_id)
        # Someone else's pet is a 404 (not 403) so pet ids are not revealed.
        if animal is None or animal.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Pet {animal_id} not found."
            )

    key = storage.build_key("uploads", file.filename or "image")
    stored = storage.put_object(key, image_bytes, file.content_type)

    result: AnalysisResult = analyzer.analyze(image_bytes, file.filename or "image")

    log = AIAnalysisLog(
        user_id=current_user.id if current_user else None,
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


@router.get("", response_model=list[AnalysisHistoryItem])
def list_analyses(
    animal_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AIAnalysisLog]:
    """The signed-in user's past analyses, newest first, optionally per pet."""
    statement = (
        select(AIAnalysisLog)
        .options(selectinload(AIAnalysisLog.animal))
        .where(AIAnalysisLog.user_id == current_user.id)
        .order_by(AIAnalysisLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if animal_id is not None:
        statement = statement.where(AIAnalysisLog.animal_id == animal_id)
    return list(db.scalars(statement).all())

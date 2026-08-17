import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_optional_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import AIAnalysisLog, Animal, User
from app.schemas import AnalysisDetail, AnalysisHistoryItem, AnalysisResponse, AnalysisResult
from app.schemas.triage import SymptomIntake, TriageAssessment
from app.services.ai import ImageAnalysisService, get_analysis_service
from app.services.storage import StorageService, get_storage_service
from app.services.triage import TriageEngine, get_triage_engine

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/upload", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_analyze(
    file: UploadFile = File(...),
    animal_id: uuid.UUID | None = Form(default=None),
    # The symptom answers, as a JSON string, because this is a multipart request.
    intake: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
    storage: StorageService = Depends(get_storage_service),
    analyzer: ImageAnalysisService = Depends(get_analysis_service),
    triage_engine: TriageEngine = Depends(get_triage_engine),
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

    animal: Animal | None = None
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

    # Parse answers early, then add a trusted species before the rules run.
    parsed_intake: SymptomIntake | None = None
    if intake:
        try:
            parsed_intake = SymptomIntake.model_validate_json(intake)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Could not read the symptom answers: {error}",
            ) from error

    key = storage.build_key("uploads", file.filename or "image")
    # Writing the file and running the model both block; on the event loop they
    # would stall every other request for the duration of the analysis.
    stored = await run_in_threadpool(storage.put_object, key, image_bytes, file.content_type)

    result: AnalysisResult = await run_in_threadpool(
        analyzer.analyze, image_bytes, file.filename or "image"
    )

    assessment: TriageAssessment | None = None
    if parsed_intake is not None:
        parsed_intake = parsed_intake.model_copy(
            update={
                "species": animal.species if animal is not None else result.species,
                "age_category": (
                    animal.age_category if animal is not None else result.age_estimate.category
                ),
            }
        )
        assessment = triage_engine.assess(parsed_intake)

    log = AIAnalysisLog(
        user_id=current_user.id if current_user else None,
        animal_id=animal_id,
        image_key=stored.key,
        image_url=stored.url,
        model_version=result.model_version,
        species=result.species,
        species_confidence=result.species_confidence,
        result=result.model_dump(mode="json"),
        intake=parsed_intake.model_dump(mode="json") if parsed_intake else None,
        triage=assessment.model_dump(mode="json") if assessment else None,
        triage_level=assessment.level.value if assessment else None,
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
        triage=assessment,
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


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(
    analysis_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIAnalysisLog:
    """Return one complete analysis belonging to the signed-in user."""
    statement = (
        select(AIAnalysisLog)
        .options(selectinload(AIAnalysisLog.animal))
        .where(
            AIAnalysisLog.id == analysis_id,
            AIAnalysisLog.user_id == current_user.id,
        )
    )
    analysis = db.scalars(statement).first()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis {analysis_id} not found.",
        )
    return analysis

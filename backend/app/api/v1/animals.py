import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Animal, User
from app.schemas import AnimalCreate, AnimalRead, AnimalUpdate
from app.services.storage import StorageService, get_storage_service

router = APIRouter()

_PHOTO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _get_owned_animal(db: Session, animal_id: uuid.UUID, owner: User) -> Animal:
    """Load a pet belonging to `owner`; 404 otherwise.

    Someone else's pet is also a 404 (not 403) so the API does not reveal
    which ids exist.
    """
    animal = db.get(Animal, animal_id)
    if animal is None or animal.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Pet {animal_id} not found."
        )
    return animal


@router.get("", response_model=list[AnimalRead])
def list_animals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Animal]:
    """Return the signed-in user's pets, oldest first."""
    statement = (
        select(Animal).where(Animal.owner_id == current_user.id).order_by(Animal.created_at)
    )
    return list(db.scalars(statement).all())


@router.post("", response_model=AnimalRead, status_code=status.HTTP_201_CREATED)
def create_animal(
    payload: AnimalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Animal:
    animal = Animal(**payload.model_dump(), owner_id=current_user.id)
    db.add(animal)
    db.commit()
    db.refresh(animal)
    return animal


@router.get("/{animal_id}", response_model=AnimalRead)
def get_animal(
    animal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Animal:
    return _get_owned_animal(db, animal_id, current_user)


@router.patch("/{animal_id}", response_model=AnimalRead)
def update_animal(
    animal_id: uuid.UUID,
    payload: AnimalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Animal:
    animal = _get_owned_animal(db, animal_id, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(animal, field, value)
    db.commit()
    db.refresh(animal)
    return animal


@router.delete("/{animal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_animal(
    animal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    animal = _get_owned_animal(db, animal_id, current_user)
    db.delete(animal)
    db.commit()


@router.post("/{animal_id}/photo", response_model=AnimalRead)
async def upload_photo(
    animal_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: StorageService = Depends(get_storage_service),
) -> Animal:
    animal = _get_owned_animal(db, animal_id, current_user)

    settings = get_settings()
    if file.content_type not in _PHOTO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image type {file.content_type!r}. "
            f"Allowed: {', '.join(sorted(_PHOTO_CONTENT_TYPES))}.",
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

    key = storage.build_key("pets", file.filename or "photo")
    stored = storage.put_object(key, image_bytes, file.content_type)
    animal.photo_url = stored.url
    animal.photo_position_x = 50
    animal.photo_position_y = 50
    animal.photo_zoom = 1.0
    db.commit()
    db.refresh(animal)
    return animal

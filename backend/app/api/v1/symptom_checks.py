"""Saved symptom checks.

The stateless preview lives at `POST /v1/triage` and stores nothing, which is
what an anonymous visitor gets. These endpoints are the signed-in equivalent:
the same assessment, kept so the owner can look back at it and show it to a vet.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Animal, SymptomCheck, User
from app.schemas.symptom_check import SymptomCheckCreate, SymptomCheckRead
from app.schemas.triage import SymptomIntake
from app.services.triage import TriageEngine, get_triage_engine

router = APIRouter()


@router.post("", response_model=SymptomCheckRead, status_code=status.HTTP_201_CREATED)
def create_symptom_check(
    payload: SymptomCheckCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    engine: TriageEngine = Depends(get_triage_engine),
) -> SymptomCheck:
    """Assess the reported symptoms and save the result to the owner's history."""
    animal: Animal | None = None
    if payload.animal_id is not None:
        animal = db.get(Animal, payload.animal_id)
        # Someone else's pet is a 404 (not 403) so pet ids are not revealed.
        if animal is None or animal.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Pet {payload.animal_id} not found."
            )

    intake = SymptomIntake.model_validate(payload.model_dump(exclude={"animal_id"}))

    # A saved pet is the better authority on its own species and age than
    # anything the owner re-types, so it wins when one is linked.
    if animal is not None:
        intake = intake.model_copy(
            update={"species": animal.species, "age_category": animal.age_category}
        )

    assessment = engine.assess(intake)

    check = SymptomCheck(
        user_id=current_user.id,
        animal_id=animal.id if animal is not None else None,
        intake=intake.model_dump(mode="json"),
        triage=assessment.model_dump(mode="json"),
        triage_level=assessment.level.value,
        species=intake.species,
        age_category=intake.age_category,
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


@router.get("", response_model=list[SymptomCheckRead])
def list_symptom_checks(
    animal_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SymptomCheck]:
    """The signed-in user's saved checks, newest first, optionally per pet."""
    statement = (
        select(SymptomCheck)
        .options(selectinload(SymptomCheck.animal))
        .where(SymptomCheck.user_id == current_user.id)
        .order_by(SymptomCheck.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if animal_id is not None:
        statement = statement.where(SymptomCheck.animal_id == animal_id)
    return list(db.scalars(statement).all())


@router.get("/{check_id}", response_model=SymptomCheckRead)
def get_symptom_check(
    check_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SymptomCheck:
    """Return one saved check belonging to the signed-in user."""
    statement = (
        select(SymptomCheck)
        .options(selectinload(SymptomCheck.animal))
        .where(SymptomCheck.id == check_id, SymptomCheck.user_id == current_user.id)
    )
    check = db.scalars(statement).first()
    if check is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Symptom check {check_id} not found."
        )
    return check


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_symptom_check(
    check_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a saved check. Health records are personal — owners can drop them."""
    check = db.get(SymptomCheck, check_id)
    if check is None or check.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Symptom check {check_id} not found."
        )
    db.delete(check)
    db.commit()

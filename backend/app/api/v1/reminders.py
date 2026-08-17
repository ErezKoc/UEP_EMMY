import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Animal, Reminder, User
from app.schemas.reminder import ReminderCreate, ReminderRead, ReminderUpdate

router = APIRouter()


def _owned_animal(db: Session, animal_id: uuid.UUID, user: User) -> Animal:
    animal = db.get(Animal, animal_id)
    if animal is None or animal.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Pet not found.")
    return animal


def _owned_reminder(db: Session, reminder_id: uuid.UUID, user: User) -> Reminder:
    reminder = db.scalar(
        select(Reminder).options(joinedload(Reminder.animal)).where(Reminder.id == reminder_id)
    )
    if reminder is None or reminder.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return reminder


@router.get("", response_model=list[ReminderRead])
def list_reminders(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    animal_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Reminder]:
    statement = select(Reminder).options(joinedload(Reminder.animal)).where(
        Reminder.owner_id == current_user.id
    )
    if start:
        statement = statement.where(Reminder.due_date >= start)
    if end:
        statement = statement.where(Reminder.due_date <= end)
    if animal_id:
        statement = statement.where(Reminder.animal_id == animal_id)
    return list(db.scalars(statement.order_by(Reminder.due_date, Reminder.created_at)).all())


@router.post("", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(
    payload: ReminderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Reminder:
    _owned_animal(db, payload.animal_id, current_user)
    reminder = Reminder(**payload.model_dump(), owner_id=current_user.id)
    db.add(reminder)
    db.commit()
    return _owned_reminder(db, reminder.id, current_user)


@router.patch("/{reminder_id}", response_model=ReminderRead)
def update_reminder(
    reminder_id: uuid.UUID,
    payload: ReminderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Reminder:
    reminder = _owned_reminder(db, reminder_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("animal_id") is not None:
        _owned_animal(db, changes["animal_id"], current_user)
    for field, value in changes.items():
        setattr(reminder, field, value)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    reminder = _owned_reminder(db, reminder_id, current_user)
    db.delete(reminder)
    db.commit()

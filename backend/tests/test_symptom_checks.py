import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.symptom_checks import (
    create_symptom_check,
    delete_symptom_check,
    get_symptom_check,
    list_symptom_checks,
)
from app.db.base import Base
from app.models import AgeCategory, Animal, SymptomCheck, User
from app.schemas.symptom_check import SymptomCheckCreate
from app.services.triage import TriageEngine


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def owner(session):
    user = User(email="owner@example.com", display_name="Owner")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def cat(session, owner):
    animal = Animal(
        name="Mittens",
        species="cat",
        age_category=AgeCategory.SENIOR,
        owner_id=owner.id,
    )
    session.add(animal)
    session.commit()
    return animal


def make_payload(**overrides) -> SymptomCheckCreate:
    base = {
        "concern": "digestion",
        "red_flags": ["not_eating"],
        "time_since_eating": "over_24h",
        "duration": "days_2_7",
        "trend": "worsening",
    }
    return SymptomCheckCreate(**{**base, **overrides})


def engine_for_tests() -> TriageEngine:
    return TriageEngine(require_verified=False)


def test_check_is_saved_with_its_verdict(session, owner):
    check = create_symptom_check(
        payload=make_payload(species="cat"),
        db=session,
        current_user=owner,
        engine=engine_for_tests(),
    )

    assert check.id is not None
    assert check.user_id == owner.id
    assert check.animal_id is None
    assert check.triage_level == check.triage["level"]
    # The answers are kept alongside the verdict so the row stays self-explaining.
    assert check.intake["concern"] == "digestion"
    assert session.get(SymptomCheck, check.id) is not None


def test_linked_pet_overrides_manually_entered_species(session, owner, cat):
    """The pet record is the better authority on its own species and age."""
    check = create_symptom_check(
        payload=make_payload(animal_id=cat.id, species="dog", age_category=AgeCategory.BABY),
        db=session,
        current_user=owner,
        engine=engine_for_tests(),
    )

    assert check.animal_id == cat.id
    assert check.species == "cat"
    assert check.age_category == AgeCategory.SENIOR
    assert check.intake["species"] == "cat"
    # The cat-specific anorexia rule can only fire once the species is right.
    assert any(rule["rule_id"] == "cat_not_eating_24h" for rule in check.triage["fired_rules"])


def test_another_owners_pet_is_not_found(session, owner, cat):
    intruder = User(email="intruder@example.com", display_name="Intruder")
    session.add(intruder)
    session.commit()

    with pytest.raises(HTTPException) as error:
        create_symptom_check(
            payload=make_payload(animal_id=cat.id),
            db=session,
            current_user=intruder,
            engine=engine_for_tests(),
        )
    assert error.value.status_code == 404


def test_history_is_scoped_to_the_owner_and_filterable_by_pet(session, owner, cat):
    create_symptom_check(
        payload=make_payload(animal_id=cat.id),
        db=session,
        current_user=owner,
        engine=engine_for_tests(),
    )
    create_symptom_check(
        payload=make_payload(), db=session, current_user=owner, engine=engine_for_tests()
    )

    stranger = User(email="stranger@example.com", display_name="Stranger")
    session.add(stranger)
    session.commit()
    create_symptom_check(
        payload=make_payload(), db=session, current_user=stranger, engine=engine_for_tests()
    )

    mine = list_symptom_checks(animal_id=None, limit=50, offset=0, db=session, current_user=owner)
    assert len(mine) == 2

    for_cat = list_symptom_checks(
        animal_id=cat.id, limit=50, offset=0, db=session, current_user=owner
    )
    assert [check.animal_id for check in for_cat] == [cat.id]

    theirs = list_symptom_checks(
        animal_id=None, limit=50, offset=0, db=session, current_user=stranger
    )
    assert len(theirs) == 1


def test_reading_someone_elses_check_is_not_found(session, owner):
    check = create_symptom_check(
        payload=make_payload(), db=session, current_user=owner, engine=engine_for_tests()
    )
    stranger = User(email="stranger@example.com", display_name="Stranger")
    session.add(stranger)
    session.commit()

    assert get_symptom_check(check.id, db=session, current_user=owner).id == check.id

    with pytest.raises(HTTPException) as error:
        get_symptom_check(check.id, db=session, current_user=stranger)
    assert error.value.status_code == 404


def test_owner_can_delete_a_check_but_a_stranger_cannot(session, owner):
    check = create_symptom_check(
        payload=make_payload(), db=session, current_user=owner, engine=engine_for_tests()
    )
    stranger = User(email="stranger@example.com", display_name="Stranger")
    session.add(stranger)
    session.commit()

    with pytest.raises(HTTPException) as error:
        delete_symptom_check(check.id, db=session, current_user=stranger)
    assert error.value.status_code == 404
    assert session.get(SymptomCheck, check.id) is not None

    delete_symptom_check(check.id, db=session, current_user=owner)
    assert session.get(SymptomCheck, check.id) is None

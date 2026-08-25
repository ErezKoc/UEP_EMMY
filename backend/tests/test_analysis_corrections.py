"""Correcting, relinking and deleting a stored AI result.

The invariant worth guarding: a correction must never rewrite what the model
actually predicted. A record of a prediction that has been edited to be right is
not a record of anything, and the audit trail is the only reason to keep these
rows at all.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.analysis import delete_analysis, get_analysis, update_analysis
from app.db.base import Base
from app.models import AgeCategory, AIAnalysisLog, Animal, User
from app.schemas.analysis import AnalysisCorrection, AnalysisUpdate

MODEL_RESULT = {
    "model_version": "mock-1.4.0",
    "species": "dog",
    "species_confidence": 0.91,
    "breed_candidates": [{"breed": "Beagle", "confidence": 0.62}],
    "age_estimate": {
        "category": "adult",
        "min_years": 2.0,
        "max_years": 5.0,
        "confidence": 0.55,
    },
    "characteristics": ["floppy ears"],
}


class _FakeStorage:
    """Records what was deleted, and can be told to fail like a real one."""

    def __init__(self, explode: bool = False) -> None:
        self.deleted: list[str] = []
        self.explode = explode

    def delete_object(self, key: str) -> None:
        if self.explode:
            raise OSError("storage is down")
        self.deleted.append(key)


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
def buddy(session, owner):
    animal = Animal(
        name="Buddy", species="dog", age_category=AgeCategory.ADULT, owner_id=owner.id
    )
    session.add(animal)
    session.commit()
    return animal


@pytest.fixture
def mittens(session, owner):
    animal = Animal(
        name="Mittens", species="cat", age_category=AgeCategory.SENIOR, owner_id=owner.id
    )
    session.add(animal)
    session.commit()
    return animal


@pytest.fixture
def analysis(session, owner, buddy):
    log = AIAnalysisLog(
        user_id=owner.id,
        animal_id=buddy.id,
        image_key="uploads/buddy.jpg",
        image_url="/media/uploads/buddy.jpg",
        model_version="mock-1.4.0",
        species="dog",
        species_confidence=0.91,
        result=MODEL_RESULT,
    )
    session.add(log)
    session.commit()
    return log


def stored(session, analysis_id) -> AIAnalysisLog:
    """The row as it was actually saved.

    `update_analysis` returns the response schema now that it also carries the
    profile conflicts, so the endpoint's return value is no longer the ORM
    object. These tests are about what reaches the database, so they ask the
    database.
    """
    session.expire_all()
    return session.get(AIAnalysisLog, analysis_id)


# ---------------------------------------------------------------- correcting


def test_a_correction_never_rewrites_what_the_model_said(session, owner, analysis):
    """The point of the whole design."""
    updated = update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(breed="Basset Hound")),
        db=session,
        current_user=owner,
    )

    assert updated.correction is not None and updated.correction.breed == "Basset Hound"
    row = stored(session, analysis.id)
    assert row.correction == {"breed": "Basset Hound"}
    # Untouched, in every field.
    assert row.result == MODEL_RESULT
    assert row.result["breed_candidates"][0]["breed"] == "Beagle"
    assert row.species == "dog"
    assert row.corrected_at is not None


def test_corrections_accumulate_rather_than_replacing_each_other(session, owner, analysis):
    """Fixing the breed today must not drop the species fixed last week."""
    update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(species="cat")),
        db=session,
        current_user=owner,
    )
    updated = update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(breed="Maine Coon")),
        db=session,
        current_user=owner,
    )

    assert stored(session, analysis.id).correction == {"species": "cat", "breed": "Maine Coon"}


def test_one_field_can_be_handed_back_to_the_model(session, owner, analysis):
    update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(species="cat", breed="Maine Coon")),
        db=session,
        current_user=owner,
    )
    updated = update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(breed=None)),
        db=session,
        current_user=owner,
    )

    assert stored(session, analysis.id).correction == {"species": "cat"}


def test_withdrawing_the_whole_correction_clears_the_timestamp_too(session, owner, analysis):
    update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(species="cat")),
        db=session,
        current_user=owner,
    )
    updated = update_analysis(
        analysis.id, AnalysisUpdate(correction=None), db=session, current_user=owner
    )

    assert updated.correction is None
    assert updated.corrected_at is None


def test_a_note_on_its_own_is_not_a_correction(session, owner, analysis):
    """Nothing has been corrected, so the record must not claim it has."""
    updated = update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(note="Looks about right to me.")),
        db=session,
        current_user=owner,
    )

    assert updated.correction is None
    assert updated.corrected_at is None


def test_the_age_category_is_stored_as_its_value_not_the_enum(session, owner, analysis):
    """It round-trips through JSON, so it has to survive as a string."""
    updated = update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(age_category=AgeCategory.SENIOR)),
        db=session,
        current_user=owner,
    )

    assert stored(session, analysis.id).correction == {"age_category": "senior"}


# ----------------------------------------------------------------- relinking


def test_an_analysis_can_be_moved_to_another_pet(session, owner, analysis, mittens):
    updated = update_analysis(
        analysis.id, AnalysisUpdate(animal_id=mittens.id), db=session, current_user=owner
    )

    assert stored(session, analysis.id).animal_id == mittens.id


def test_an_analysis_can_be_unlinked(session, owner, analysis):
    updated = update_analysis(
        analysis.id, AnalysisUpdate(animal_id=None), db=session, current_user=owner
    )

    assert stored(session, analysis.id).animal_id is None


def test_omitting_the_link_leaves_it_alone(session, owner, analysis, buddy):
    """The distinction a plain default cannot express.

    `animal_id=None` means unlink; not sending it at all means "I am only here
    to correct the breed". Both arrive as None on the model.
    """
    updated = update_analysis(
        analysis.id,
        AnalysisUpdate(correction=AnalysisCorrection(breed="Basset Hound")),
        db=session,
        current_user=owner,
    )

    assert stored(session, analysis.id).animal_id == buddy.id


def test_it_cannot_be_relinked_to_someone_elses_pet(session, owner, analysis):
    stranger = User(email="stranger@example.com", display_name="Stranger")
    session.add(stranger)
    session.flush()
    theirs = Animal(
        name="Rex", species="dog", age_category=AgeCategory.ADULT, owner_id=stranger.id
    )
    session.add(theirs)
    session.commit()

    with pytest.raises(HTTPException) as raised:
        update_analysis(
            analysis.id, AnalysisUpdate(animal_id=theirs.id), db=session, current_user=owner
        )
    assert raised.value.status_code == 404


# ------------------------------------------------------------------ deleting


def test_deleting_removes_the_row_and_the_photograph(session, owner, analysis):
    """"Delete my result" that leaves the photo on the server has not deleted it."""
    storage = _FakeStorage()
    analysis_id = analysis.id

    delete_analysis(analysis_id, db=session, current_user=owner, storage=storage)

    assert session.get(AIAnalysisLog, analysis_id) is None
    assert storage.deleted == ["uploads/buddy.jpg"]


def test_a_storage_failure_does_not_block_the_delete(session, owner, analysis):
    """An orphaned file beats being unable to remove your own data."""
    analysis_id = analysis.id

    delete_analysis(
        analysis_id, db=session, current_user=owner, storage=_FakeStorage(explode=True)
    )

    assert session.get(AIAnalysisLog, analysis_id) is None


def test_deleting_does_not_take_the_pet_with_it(session, owner, analysis, buddy):
    delete_analysis(analysis.id, db=session, current_user=owner, storage=_FakeStorage())

    assert session.get(Animal, buddy.id) is not None


# ----------------------------------------------------------------- ownership


def test_another_account_can_neither_edit_nor_delete_nor_read_it(session, analysis):
    stranger = User(email="nosy@example.com", display_name="Nosy")
    session.add(stranger)
    session.commit()

    for call in (
        lambda: get_analysis(analysis.id, db=session, current_user=stranger),
        lambda: update_analysis(
            analysis.id,
            AnalysisUpdate(correction=AnalysisCorrection(breed="Poodle")),
            db=session,
            current_user=stranger,
        ),
        lambda: delete_analysis(
            analysis.id, db=session, current_user=stranger, storage=_FakeStorage()
        ),
    ):
        with pytest.raises(HTTPException) as raised:
            call()
        assert raised.value.status_code == 404


def test_an_anonymous_upload_belongs_to_nobody(session, owner):
    """`user_id` is null for a dashboard-demo upload; it is not the owner's to edit."""
    orphan = AIAnalysisLog(
        user_id=None,
        image_key="uploads/anon.jpg",
        image_url="/media/uploads/anon.jpg",
        model_version="mock-1.4.0",
        species="dog",
        species_confidence=0.5,
        result=MODEL_RESULT,
    )
    session.add(orphan)
    session.commit()

    with pytest.raises(HTTPException) as raised:
        delete_analysis(orphan.id, db=session, current_user=owner, storage=_FakeStorage())
    assert raised.value.status_code == 404


def test_an_unknown_id_is_a_404_not_a_crash(session, owner):
    with pytest.raises(HTTPException) as raised:
        update_analysis(
            uuid.uuid4(),
            AnalysisUpdate(correction=AnalysisCorrection(breed="Poodle")),
            db=session,
            current_user=owner,
        )
    assert raised.value.status_code == 404

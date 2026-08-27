import datetime
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Animal, Reminder, User, UserRole
from app.schemas.assistant import AssistantActionType
from app.services.assistant import AssistantService


@pytest.fixture
def assistant_service() -> AssistantService:
    return AssistantService()


@pytest.fixture
def test_user(db: Session) -> User:
    user = User(
        email=f"assistant_test_{datetime.datetime.now().timestamp()}@uepemmy.com",
        display_name="Test Owner",
        role=UserRole.OWNER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_parse_single_intent(assistant_service: AssistantService):
    res = assistant_service.parse_intent("take me to my pets", [])
    assert len(res["actions"]) == 1
    assert res["actions"][0]["action_type"] == AssistantActionType.NAVIGATE.value
    assert res["actions"][0]["nav_target"] == "/pets"


def test_parse_multi_intent_pet_and_reminder(assistant_service: AssistantService):
    command = "add a dog named Max and set a checkup reminder for him tomorrow at 2pm"
    res = assistant_service.parse_intent(command, [])

    actions = res["actions"]
    assert len(actions) == 2

    # First action: create pet
    assert actions[0]["action_type"] == AssistantActionType.CREATE_PET.value
    assert actions[0]["params"]["name"] == "Max"
    assert actions[0]["params"]["species"] == "dog"

    # Second action: create reminder linked to Max
    assert actions[1]["action_type"] == AssistantActionType.CREATE_REMINDER.value
    assert actions[1]["params"]["pet_name"] == "Max"
    assert actions[1]["params"]["category"] == "checkup"
    assert actions[1]["params"]["time_str"] == "14:00"


def test_parse_multi_intent_three_actions(assistant_service: AssistantService):
    command = "register cat Luna, schedule a vaccination on Friday, and open my calendar"
    res = assistant_service.parse_intent(command, [])

    actions = res["actions"]
    assert len(actions) == 3

    assert actions[0]["action_type"] == AssistantActionType.CREATE_PET.value
    assert actions[0]["params"]["name"] == "Luna"
    assert actions[0]["params"]["species"] == "cat"

    assert actions[1]["action_type"] == AssistantActionType.CREATE_REMINDER.value
    assert actions[1]["params"]["category"] == "vaccine"

    assert actions[2]["action_type"] == AssistantActionType.NAVIGATE.value
    assert actions[2]["nav_target"] == "/calendar"


def test_execute_multi_action_db(assistant_service: AssistantService, db: Session, test_user: User):
    command = "add a dog named Rocky and set a vaccine reminder for him tomorrow at 10am"
    res = assistant_service.parse_intent(command, [])
    actions = res["actions"]
    assert len(actions) == 2

    results, combined_text = assistant_service.execute_actions(db, test_user, actions)

    assert len(results) == 2
    assert results[0] is not None
    assert results[1] is not None
    assert "Rocky" in combined_text
    assert "Scheduled" in combined_text

    # Verify pet in DB
    pet = db.scalar(select(Animal).where(Animal.owner_id == test_user.id, Animal.name == "Rocky"))
    assert pet is not None
    assert pet.species == "dog"

    # Verify reminder in DB linked to newly created pet
    rem = db.scalar(select(Reminder).where(Reminder.owner_id == test_user.id, Reminder.animal_id == pet.id))
    assert rem is not None
    assert "Vaccine" in rem.title

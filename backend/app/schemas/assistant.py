import enum
from typing import Any
from pydantic import BaseModel, Field


class AssistantActionType(str, enum.Enum):
    CREATE_REMINDER = "create_reminder"
    DELETE_REMINDER = "delete_reminder"
    CREATE_PET = "create_pet"
    DELETE_PET = "delete_pet"
    UPDATE_PET = "update_pet"
    NAVIGATE = "navigate"
    CREATE_POST = "create_post"
    SEARCH_VETS = "search_vets"
    SUBMIT_VERIFICATION = "submit_verification"
    QUERY_PETS = "query_pets"
    GENERAL_REPLY = "general_reply"


class AssistantAction(BaseModel):
    action_type: AssistantActionType = Field(default=AssistantActionType.GENERAL_REPLY)
    summary: str = Field(description="Human-readable description of what action is being taken.")
    params: dict[str, Any] = Field(default_factory=dict, description="Extracted action parameters.")
    nav_target: str | None = Field(default=None, description="Frontend route to navigate to, if any.")
    execution_result: dict[str, Any] | None = Field(default=None, description="Result of auto-executed backend mutations for this action, if applicable.")


class AssistantProcessResponse(BaseModel):
    transcript: str = Field(description="Transcribed input query or user text.")
    response_text: str = Field(description="Spoken and displayed response from Emmy Assistant.")
    actions: list[AssistantAction] = Field(default_factory=list, description="List of all actions parsed and executed.")
    action: AssistantAction = Field(description="Primary or first action for backwards compatibility.")
    execution_result: dict[str, Any] | None = Field(default=None, description="Result of auto-executed backend mutations, if applicable.")

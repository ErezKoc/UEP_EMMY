from typing import Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Animal, User
from app.schemas.assistant import AssistantAction, AssistantProcessResponse
from app.services.assistant import AssistantService

router = APIRouter()
assistant_service = AssistantService()


@router.post("/process", response_model=AssistantProcessResponse)
async def process_assistant_command(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssistantProcessResponse:
    """Process voice audio or typed text command, parse intent, and auto-execute actions."""
    transcript = ""

    if text and text.strip():
        transcript = text.strip()

    if not transcript and file is not None:
        audio_bytes = await file.read()
        if audio_bytes:
            transcript = assistant_service.transcribe_audio(audio_bytes, file.filename or "speech.webm")

    if not transcript:
        return AssistantProcessResponse(
            transcript="",
            response_text="I couldn't hear any speech in that recording. Please try speaking again or type your command below!",
            action=AssistantAction(
                action_type="general_reply",
                summary="Unclear speech audio",
                params={},
                nav_target=None,
            ),
            execution_result=None,
        )

    # Fetch user's pets for intent context
    user_pets_db = list(db.scalars(select(Animal).where(Animal.owner_id == current_user.id)).all())
    user_pets_list = [{"id": str(p.id), "name": p.name, "species": p.species} for p in user_pets_db]

    # Parse intent via Ollama / fallback
    intent = assistant_service.parse_intent(transcript, user_pets_list)
    raw_actions = intent.get("actions") or [intent]

    # Execute backend mutations for all actions
    execution_results, response_text = assistant_service.execute_actions(db, current_user, raw_actions)

    actions: list[AssistantAction] = []
    for i, act in enumerate(raw_actions):
        res = execution_results[i] if i < len(execution_results) else None
        actions.append(
            AssistantAction(
                action_type=act.get("action_type", "general_reply"),
                summary=act.get("summary", "Processed command"),
                params=act.get("params", {}),
                nav_target=act.get("nav_target"),
                execution_result=res,
            )
        )

    primary_action = actions[0] if actions else AssistantAction(
        action_type="general_reply",
        summary="Processed command",
        params={},
        nav_target=None,
    )
    primary_result = execution_results[0] if execution_results else None

    return AssistantProcessResponse(
        transcript=transcript,
        response_text=response_text,
        actions=actions,
        action=primary_action,
        execution_result=primary_result,
    )


@router.post("/transcribe")
async def transcribe_speech(
    file: UploadFile = File(...),
) -> dict[str, str]:
    """Transcribe speech audio file to text."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")
    transcript = assistant_service.transcribe_audio(audio_bytes, file.filename or "speech.webm")
    return {"transcript": transcript}

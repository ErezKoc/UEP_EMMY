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

    if file is not None:
        audio_bytes = await file.read()
        if audio_bytes:
            transcript = assistant_service.transcribe_audio(audio_bytes, file.filename or "speech.webm")

    if not transcript and text:
        transcript = text.strip()

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

    # Execute backend mutation if needed
    execution_result, response_text = assistant_service.execute_action(db, current_user, intent)

    action = AssistantAction(
        action_type=intent.get("action_type", "general_reply"),
        summary=intent.get("summary", "Processed command"),
        params=intent.get("params", {}),
        nav_target=intent.get("nav_target"),
    )

    return AssistantProcessResponse(
        transcript=transcript,
        response_text=response_text,
        action=action,
        execution_result=execution_result,
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

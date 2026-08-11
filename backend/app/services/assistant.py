import datetime
import json
import logging
import os
import re
import tempfile
from typing import Any
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Animal, Recurrence, Reminder, ReminderType, User
from app.schemas.assistant import AssistantAction, AssistantActionType, AssistantProcessResponse

logger = logging.getLogger(__name__)

# Lazy whisper loader
_WHISPER_MODEL = None


def _get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    try:
        import whisper
        settings = get_settings()
        logger.info(f"Loading Whisper model '{settings.whisper_model_size}'...")
        _WHISPER_MODEL = whisper.load_model(settings.whisper_model_size)
        return _WHISPER_MODEL
    except Exception as e:
        logger.warning(f"Could not load Whisper model: {e}")
        return None


class AssistantService:
    def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """Transcribe audio bytes using Whisper if available."""
        model = _get_whisper_model()
        if not model:
            logger.warning("Whisper model unavailable. Returning empty transcription.")
            return ""

        ext = os.path.splitext(filename)[1] or ".webm"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            result = model.transcribe(tmp_path)
            return result.get("text", "").strip()
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return ""
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def parse_intent(self, text: str, user_pets: list[dict[str, Any]]) -> dict[str, Any]:
        """Determine intent via Ollama, falling back to NLP pattern matching."""
        settings = get_settings()
        text_clean = text.strip()
        if not text_clean:
            return {
                "action_type": AssistantActionType.GENERAL_REPLY.value,
                "summary": "No speech detected",
                "params": {},
                "nav_target": None,
                "response_text": "I didn't hear anything. How can I help you?",
            }

        # Try Ollama first
        try:
            pets_info = ", ".join(f"{p['name']} ({p['species']})" for p in user_pets) or "None"
            prompt = (
                f"User request: '{text_clean}'\n"
                f"User pets: {pets_info}\n"
                "Return a JSON object classifying this user command into an in-app software action.\n"
                "Allowed action_type values:\n"
                "- 'create_reminder': params { 'title': str, 'date_str': str (e.g. '2026-01-06'), 'time_str': str (e.g. '12:30'), 'pet_name': str or null, 'category': 'checkup'|'vaccination'|'other', 'notes': str or null }, nav_target: '/calendar'\n"
                "- 'create_pet': params { 'name': str, 'species': 'dog'|'cat'|'other', 'breed': str or null }, nav_target: '/pets'\n"
                "- 'navigate': nav_target: '/pets'|'/calendar'|'/community'|'/vets'|'/analyze'|'/dashboard'|'/profile'|'/settings'\n"
                "- 'create_post': params { 'title': str, 'content': str }, nav_target: '/community/new'\n"
                "- 'search_vets': params { 'query': str }, nav_target: '/vets'\n"
                "- 'general_reply': response_text for questions or conversation.\n\n"
                "Schema:\n"
                "{\n"
                '  "action_type": "...",\n'
                '  "summary": "...",\n'
                '  "params": { ... },\n'
                '  "nav_target": "/route" or null,\n'
                '  "response_text": "Spoken reply for user"\n'
                "}"
            )
            response = requests.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=4.0,
            )
            if response.status_code == 200:
                body = response.json()
                raw_response = body.get("response", "")
                data = json.loads(raw_response)
                if "action_type" in data and "response_text" in data:
                    return data
        except Exception as e:
            logger.info(f"Ollama call failed or timed out ({e}). Using fast NLP fallback parser.")

        # Fallback to pattern matcher
        return self._fallback_intent_parser(text_clean, user_pets)

    def _fallback_intent_parser(self, text: str, user_pets: list[dict[str, Any]]) -> dict[str, Any]:
        t = text.lower()

        # 1. Calendar / Reminder creation
        if any(w in t for w in ["calendar", "event", "reminder", "schedule", "remind me", "appointment"]):
            # Extract date (e.g. "jan 6", "january 6", "6th jan", "tomorrow")
            date_val = self._extract_date(t)
            time_val = self._extract_time(t) or "12:00"

            # Determine title & pet
            matched_pet = None
            for pet in user_pets:
                if pet["name"].lower() in t:
                    matched_pet = pet["name"]
                    break

            category = "vaccine" if "vaccin" in t else ("checkup" if "checkup" in t or "vet" in t else "other")
            title = f"{category.capitalize()} appointment" if matched_pet is None else f"{category.capitalize()} for {matched_pet}"

            # Clean up title if "create event for X"
            match_for = re.search(r"(?:for|named|about)\s+([a-zA-Z0-9\s]+?)(?:\s+at|\s+on|\s+jan|\s+feb|\s+mar|\s+apr|\s+may|\s+jun|\s+jul|\s+aug|\s+sep|\s+oct|\s+nov|\s+dec|$)", t)
            if match_for and len(match_for.group(1).strip()) > 2:
                title = match_for.group(1).strip().capitalize()

            return {
                "action_type": AssistantActionType.CREATE_REMINDER.value,
                "summary": f"Create calendar event '{title}' for {date_val} at {time_val}",
                "params": {
                    "title": title,
                    "date_str": date_val,
                    "time_str": time_val,
                    "pet_name": matched_pet,
                    "category": category,
                },
                "nav_target": "/calendar",
                "response_text": f"Got it! Scheduled '{title}' for {date_val} at {time_val}.",
            }

        # 2. Register Pet
        if any(w in t for w in ["add pet", "create pet", "new pet", "register pet", "add a dog", "add a cat"]):
            name_match = re.search(r"(?:named|called|name)\s+([a-zA-Z]+)", t)
            name = name_match.group(1).capitalize() if name_match else "New Pet"
            species = "cat" if "cat" in t or "kitten" in t else ("dog" if "dog" in t or "puppy" in t else "other")
            return {
                "action_type": AssistantActionType.CREATE_PET.value,
                "summary": f"Register new {species} named '{name}'",
                "params": {"name": name, "species": species},
                "nav_target": "/pets",
                "response_text": f"Added {species} named '{name}' to your pets profile!",
            }

        # 3. Navigation
        if any(w in t for w in ["take me to", "open", "go to", "show", "navigate"]):
            if "pet" in t:
                return {"action_type": "navigate", "summary": "Open pets page", "params": {}, "nav_target": "/pets", "response_text": "Opening your pets dashboard."}
            if "calendar" in t or "reminder" in t or "schedule" in t:
                return {"action_type": "navigate", "summary": "Open calendar", "params": {}, "nav_target": "/calendar", "response_text": "Opening your calendar."}
            if "community" in t or "feed" in t or "forum" in t:
                return {"action_type": "navigate", "summary": "Open community", "params": {}, "nav_target": "/community", "response_text": "Navigating to the community."}
            if "vet" in t or "doctor" in t:
                return {"action_type": "navigate", "summary": "Open vets directory", "params": {}, "nav_target": "/vets", "response_text": "Showing veterinarian directory."}
            if "analyze" in t or "photo" in t or "ai" in t or "scan" in t:
                return {"action_type": "navigate", "summary": "Open AI analyzer", "params": {}, "nav_target": "/analyze", "response_text": "Opening pet photo analyzer."}
            if "profile" in t:
                return {"action_type": "navigate", "summary": "Open profile", "params": {}, "nav_target": "/profile", "response_text": "Opening your profile."}
            if "setting" in t:
                return {"action_type": "navigate", "summary": "Open settings", "params": {}, "nav_target": "/settings", "response_text": "Opening settings."}

        # 4. Create post
        if "post" in t or "share" in t:
            return {
                "action_type": AssistantActionType.CREATE_POST.value,
                "summary": "Create community post",
                "params": {"title": text.capitalize(), "content": f"Shared via Emmy Voice Assistant: {text}"},
                "nav_target": "/community/new",
                "response_text": "Opening post composer for your community post.",
            }

        # 5. Search vets
        if "find" in t and "vet" in t:
            return {
                "action_type": AssistantActionType.SEARCH_VETS.value,
                "summary": "Search veterinarians",
                "params": {"query": text},
                "nav_target": "/vets",
                "response_text": "Searching veterinarian directory.",
            }

        # General reply
        return {
            "action_type": AssistantActionType.GENERAL_REPLY.value,
            "summary": "Conversational reply",
            "params": {},
            "nav_target": None,
            "response_text": f"I heard: '{text}'. You can ask me to create calendar events, add pets, or navigate the app!",
        }

    def _extract_date(self, text: str) -> str:
        months = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12
        }

        # Check month + day e.g. "jan 6", "january 6", "6 jan"
        pattern = r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+(\d{1,2})"
        match = re.search(pattern, text)
        if match:
            m_str, d_str = match.group(1), match.group(2)
            month = months[m_str]
            day = int(d_str)
            year = datetime.date.today().year
            # If date has passed this year, set for next year
            d_obj = datetime.date(year, month, day)
            if d_obj < datetime.date.today():
                d_obj = datetime.date(year + 1, month, day)
            return d_obj.isoformat()

        if "tomorrow" in text:
            return (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        # Default to today
        return datetime.date.today().isoformat()

    def _extract_time(self, text: str) -> str:
        # e.g. "12.30", "12:30", "2 pm", "14:00"
        match = re.search(r"(\d{1,2})[:\.](\d{2})", text)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            return f"{h:02d}:{m:02d}"

        match_h = re.search(r"(\d{1,2})\s*(pm|am)", text)
        if match_h:
            h = int(match_h.group(1))
            ampm = match_h.group(2)
            if ampm == "pm" and h < 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
            return f"{h:02d}:00"

        return "12:00"

    def execute_action(
        self, db: Session, current_user: User, intent: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """Execute backend mutations if the action requires server-side DB creation."""
        action_type = intent.get("action_type")
        params = intent.get("params", {})
        nav_target = intent.get("nav_target")
        response_text = intent.get("response_text", "Action completed.")

        if action_type == AssistantActionType.CREATE_REMINDER.value:
            title = params.get("title") or "Calendar Reminder"
            date_str = params.get("date_str")
            pet_name = params.get("pet_name")

            # Resolve animal
            pets = list(db.scalars(select(Animal).where(Animal.owner_id == current_user.id)).all())
            target_animal = None
            if pet_name:
                for p in pets:
                    if p.name.lower() == pet_name.lower():
                        target_animal = p
                        break
            if target_animal is None and pets:
                target_animal = pets[0]

            # If user has no pet yet, create a default pet so reminder creation succeeds
            if target_animal is None:
                target_animal = Animal(
                    name="My Pet",
                    species="dog",
                    owner_id=current_user.id,
                )
                db.add(target_animal)
                db.flush()

            try:
                d_obj = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
            except ValueError:
                d_obj = datetime.date.today()

            rem_type = ReminderType.VACCINE if params.get("category") == "vaccine" else (
                ReminderType.CHECKUP if params.get("category") == "checkup" else ReminderType.OTHER
            )

            reminder = Reminder(
                title=title,
                reminder_type=rem_type,
                due_date=d_obj,
                recurrence=Recurrence.NONE,
                notes=params.get("notes") or "Created via Emmy Voice Assistant",
                animal_id=target_animal.id,
                owner_id=current_user.id,
            )
            db.add(reminder)
            db.commit()
            db.refresh(reminder)

            return {
                "id": str(reminder.id),
                "title": reminder.title,
                "due_date": reminder.due_date.isoformat(),
                "animal_name": target_animal.name,
            }, f"Scheduled reminder '{title}' for {target_animal.name} on {d_obj.strftime('%b %d, %Y')}!"

        if action_type == AssistantActionType.CREATE_PET.value:
            name = params.get("name") or "New Pet"
            species = params.get("species") or "dog"
            breed = params.get("breed")

            animal = Animal(
                name=name,
                species=species,
                breed=breed,
                owner_id=current_user.id,
            )
            db.add(animal)
            db.commit()
            db.refresh(animal)

            return {
                "id": str(animal.id),
                "name": animal.name,
                "species": animal.species,
            }, f"Successfully added {animal.name} to your pet profiles!"

        return None, response_text

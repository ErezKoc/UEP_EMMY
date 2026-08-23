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
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_in:
            tmp_in.write(audio_bytes)
            in_path = tmp_in.name

        wav_path = in_path + ".wav"

        try:
            # Convert audio format to 16kHz mono PCM WAV via ffmpeg
            import subprocess
            cmd = ["ffmpeg", "-y", "-i", in_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            target_path = wav_path if (res.returncode == 0 and os.path.exists(wav_path)) else in_path

            result = model.transcribe(target_path)
            text = result.get("text", "").strip()
            logger.info(f"Whisper transcribed audio ({filename}): '{text}'")
            return text
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}", exc_info=True)
            return ""
        finally:
            for p in [in_path, wav_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    def parse_intent(self, text: str, user_pets: list[dict[str, Any]]) -> dict[str, Any]:
        """Zero-shot semantic intent parsing via Ollama, falling back to a general vector-concept matcher."""
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

        # Try Ollama zero-shot classification first
        try:
            pets_info = ", ".join(f"{p['name']} ({p['species']})" for p in user_pets) or "None"
            prompt = (
                "You are an intelligent zero-shot intent classifier for the UEP EMMY platform.\n"
                f"User request: '{text_clean}'\n"
                f"User pets: {pets_info}\n\n"
                "Classify the user's intent into ONE software action based purely on semantic meaning, regardless of how it is phrased.\n\n"
                "Available Actions:\n"
                "1. 'create_reminder': Schedule an event, reminder, appointment, checkup, or vaccination.\n"
                "   params: { 'title': str, 'date_str': str ('YYYY-MM-DD'), 'time_str': str ('HH:MM'), 'pet_name': str or null, 'category': 'checkup'|'vaccination'|'other' }, nav_target: '/calendar'\n"
                "2. 'delete_reminder': Delete or cancel an event or reminder.\n"
                "   params: { 'title': str or null, 'pet_name': str or null }, nav_target: '/calendar'\n"
                "3. 'create_pet': Register or add a new pet.\n"
                "   params: { 'name': str, 'species': 'dog'|'cat'|'other', 'breed': str or null }, nav_target: '/pets'\n"
                "4. 'delete_pet': Delete or remove an existing pet.\n"
                "   params: { 'name': str }, nav_target: '/pets'\n"
                "5. 'update_pet': Update or edit pet details (name, breed, species).\n"
                "   params: { 'name': str, 'breed': str or null, 'species': str or null }, nav_target: '/pets'\n"
                "6. 'navigate': View, visit, open, or switch to any page/section.\n"
                "   nav_target: '/pets' | '/calendar' | '/community' | '/vets' | '/analyze' | '/dashboard' | '/profile' | '/settings'\n"
                "7. 'create_post': Write or publish a post in the community.\n"
                "   params: { 'title': str, 'content': str }, nav_target: '/community/new'\n"
                "8. 'search_vets': Search or locate a vet, doctor, or clinic.\n"
                "   params: { 'query': str }, nav_target: '/vets'\n"
                "9. 'submit_verification': Submit veterinarian license or credentials for review.\n"
                "   nav_target: '/profile'\n"
                "10. 'general_reply': Conversational response for general questions or statements.\n\n"
                "Return ONLY a JSON object:\n"
                "{\n"
                '  "action_type": "...",\n'
                '  "summary": "...",\n'
                '  "params": { ... },\n'
                '  "nav_target": "/route" or null,\n'
                '  "response_text": "Friendly spoken response"\n'
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
                raw_response = body.get("response", "").strip()
                json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    if "action_type" in data and "response_text" in data:
                        logger.info(f"Ollama zero-shot parsed intent: {data['action_type']}")
                        return data
        except Exception as e:
            logger.info(f"Ollama unavailable or timed out ({e}). Using generalized vector-concept NLP parser.")

        # Fallback to generalized semantic vector-concept matcher
        return self._semantic_concept_fallback(text_clean, user_pets)

    def _semantic_concept_fallback(self, text: str, user_pets: list[dict[str, Any]]) -> dict[str, Any]:
        """Generalized semantic vector-concept matcher.

        Tokenizes user input and measures semantic concept overlap against software action vectors.
        """
        t = text.lower()
        tokens = set(re.findall(r"\w+", t))

        REMINDER_CONCEPTS = {"remind", "reminder", "schedule", "event", "calendar", "appointment", "checkup", "vaccine", "vaccination", "book", "meeting"}
        PET_CONCEPTS = {"pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "kitten", "animal", "animals"}
        DELETE_CONCEPTS = {"delete", "remove", "erase", "drop", "cancel", "clear", "discard"}
        CREATE_CONCEPTS = {"add", "create", "register", "new", "got"}
        UPDATE_CONCEPTS = {"update", "change", "edit", "modify", "rename"}
        POST_CREATE_CONCEPTS = {"write", "publish", "post", "share", "question", "forum"}
        VET_SEARCH_CONCEPTS = {"search", "find", "locate", "look", "where"}

        # 1. Check for Pet Deletion Intent
        if (tokens & DELETE_CONCEPTS) and (tokens & PET_CONCEPTS):
            matched_name = None
            for pet in user_pets:
                if pet["name"].lower() in tokens or pet["name"].lower() in t:
                    matched_name = pet["name"]
                    break

            name_target = matched_name or (re.search(r"(?:pet|dog|cat|named|called)\s+([a-zA-Z]+)", t).group(1).capitalize() if re.search(r"(?:pet|dog|cat|named|called)\s+([a-zA-Z]+)", t) else "Pet")
            return {
                "action_type": AssistantActionType.DELETE_PET.value,
                "summary": f"Delete pet '{name_target}'",
                "params": {"name": name_target},
                "nav_target": "/pets",
                "response_text": f"Deleting pet '{name_target}' from your account.",
            }

        # 2. Check for Reminder Deletion Intent
        if (tokens & DELETE_CONCEPTS) and (tokens & REMINDER_CONCEPTS):
            return {
                "action_type": AssistantActionType.DELETE_REMINDER.value,
                "summary": "Delete calendar reminder",
                "params": {"title": text},
                "nav_target": "/calendar",
                "response_text": "Removing calendar reminder.",
            }

        # 3. Check for Pet Update Intent
        if (tokens & UPDATE_CONCEPTS) and (tokens & PET_CONCEPTS):
            matched_name = None
            for pet in user_pets:
                if pet["name"].lower() in tokens or pet["name"].lower() in t:
                    matched_name = pet["name"]
                    break
            name_target = matched_name or "Pet"
            return {
                "action_type": AssistantActionType.UPDATE_PET.value,
                "summary": f"Update pet '{name_target}'",
                "params": {"name": name_target},
                "nav_target": "/pets",
                "response_text": f"Updating pet details for '{name_target}'.",
            }

        # 4. Check for Reminder Creation Intent
        if (tokens & REMINDER_CONCEPTS) and (tokens & {"create", "add", "schedule", "set", "book", "remind", "new", "appointment", "event", "checkup", "vaccine"}):
            date_val = self._extract_date(t)
            time_val = self._extract_time(t)

            matched_pet = None
            for pet in user_pets:
                if pet["name"].lower() in tokens:
                    matched_pet = pet["name"]
                    break

            category = "vaccine" if "vaccine" in t or "vaccination" in t else ("checkup" if "checkup" in t or "vet" in t or "doctor" in t else "other")
            title = f"{category.capitalize()} Appointment" if matched_pet is None else f"{category.capitalize()} for {matched_pet}"

            match_for = re.search(r"(?:for|named|about|to)\s+([a-zA-Z0-9\s]+?)(?:\s+at|\s+on|\s+jan|\s+feb|\s+mar|\s+apr|\s+may|\s+jun|\s+jul|\s+aug|\s+sep|\s+oct|\s+nov|\s+dec|\s+today|\s+tomorrow|$)", t)
            if match_for:
                extracted = match_for.group(1).strip()
                if len(extracted) > 2 and extracted not in ["a", "the", "me", "my pet", "calendar", "event", "reminder"]:
                    title = extracted.capitalize()

            formatted_date = datetime.date.fromisoformat(date_val).strftime("%d %b %Y")
            return {
                "action_type": AssistantActionType.CREATE_REMINDER.value,
                "summary": f"Create calendar event '{title}' for {formatted_date} at {time_val}",
                "params": {
                    "title": title,
                    "date_str": date_val,
                    "time_str": time_val,
                    "pet_name": matched_pet,
                    "category": category,
                },
                "nav_target": "/calendar",
                "response_text": f"Created calendar event '{title}' for {formatted_date} at {time_val}.",
            }

        # 5. Check for Pet Creation Intent
        if (tokens & CREATE_CONCEPTS) and (tokens & PET_CONCEPTS):
            name_match = re.search(r"(?:named|called|name|is)\s+([a-zA-Z]+)", t)
            name = name_match.group(1).capitalize() if name_match else "New Pet"
            species = "cat" if (tokens & {"cat", "kitten", "feline"}) else ("dog" if (tokens & {"dog", "puppy", "canine"}) else "other")
            return {
                "action_type": AssistantActionType.CREATE_PET.value,
                "summary": f"Register new {species} named '{name}'",
                "params": {"name": name, "species": species},
                "nav_target": "/pets",
                "response_text": f"Added new {species} named '{name}' to your pet profile!",
            }

        # 6. Check for Post Creation Intent
        if (tokens & POST_CREATE_CONCEPTS) and (tokens & {"post", "community", "thought", "question", "story"}):
            return {
                "action_type": AssistantActionType.CREATE_POST.value,
                "summary": "Create community post",
                "params": {"title": text.capitalize(), "content": f"Shared via Emmy Voice Assistant: {text}"},
                "nav_target": "/community/new",
                "response_text": "Opening post composer for your community post.",
            }

        # 7. Check for Vet Search Intent
        if (tokens & VET_SEARCH_CONCEPTS) and (tokens & {"vet", "vets", "doctor", "doctors", "clinic", "clinics"}):
            return {
                "action_type": AssistantActionType.SEARCH_VETS.value,
                "summary": "Search veterinarians",
                "params": {"query": text},
                "nav_target": "/vets",
                "response_text": "Searching veterinarian directory.",
            }

        # 8. Check for Vet Verification Intent
        if tokens & {"verify", "verification", "license", "credential", "diploma"}:
            return {
                "action_type": AssistantActionType.SUBMIT_VERIFICATION.value,
                "summary": "Submit vet verification",
                "params": {},
                "nav_target": "/profile",
                "response_text": "Opening your profile page to submit veterinarian license verification documents.",
            }

        # 9. Zero-Shot Concept Vector Distance for Page Navigation
        ROUTE_VECTOR_MAP = [
            (
                "/pets",
                {"pet", "pets", "animal", "animals", "dog", "dogs", "cat", "cats", "puppy", "kitten", "profile"},
                "Open My Pets",
                "Opening your pets page.",
            ),
            (
                "/calendar",
                {"calendar", "schedule", "event", "events", "reminder", "reminders", "agenda", "appointment", "date", "dates"},
                "Open Calendar",
                "Opening your calendar.",
            ),
            (
                "/community",
                {"community", "feed", "forum", "discussion", "discussions", "post", "posts", "social", "wall", "chat", "talk"},
                "Open Community",
                "Navigating to the community feed.",
            ),
            (
                "/vets",
                {"vet", "vets", "doctor", "doctors", "veterinarian", "veterinarians", "clinic", "clinics", "directory", "hospital", "expert", "experts"},
                "Open Vets Directory",
                "Showing the veterinarian directory.",
            ),
            (
                "/analyze",
                {"analyze", "analysis", "photo", "scan", "scanner", "camera", "image", "picture", "ai", "breed", "species", "detect", "detector"},
                "Open AI Analyzer",
                "Opening pet photo analyzer.",
            ),
            (
                "/profile",
                {"profile", "account", "user", "bio", "details", "info", "personal"},
                "Open Profile",
                "Opening your profile.",
            ),
            (
                "/settings",
                {"settings", "setting", "options", "preferences", "config", "configuration", "password"},
                "Open Settings",
                "Opening settings.",
            ),
            (
                "/dashboard",
                {"dashboard", "home", "main", "overview", "landing", "hub"},
                "Open Dashboard",
                "Opening dashboard.",
            ),
        ]

        best_route = None
        highest_overlap = 0

        for route, concept_set, summary, response_txt in ROUTE_VECTOR_MAP:
            overlap = len(tokens & concept_set)
            if overlap > highest_overlap:
                highest_overlap = overlap
                best_route = (route, summary, response_txt)

        if best_route and highest_overlap > 0:
            route, summary, response_txt = best_route
            return {
                "action_type": AssistantActionType.NAVIGATE.value,
                "summary": summary,
                "params": {},
                "nav_target": route,
                "response_text": response_txt,
            }

        # Fallback General Reply
        return {
            "action_type": AssistantActionType.GENERAL_REPLY.value,
            "summary": "Conversational reply",
            "params": {},
            "nav_target": None,
            "response_text": f"I understood: '{text}'. You can ask me to navigate, create or delete pets and reminders!",
        }

    def _extract_date(self, text: str) -> str:
        months = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
            "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12
        }

        word_numbers = {
            "first": "1", "1st": "1", "second": "2", "2nd": "2", "third": "3", "3rd": "3",
            "fourth": "4", "4th": "4", "fifth": "5", "5th": "5", "sixth": "6", "6th": "6",
            "seventh": "7", "7th": "7", "eighth": "8", "8th": "8", "ninth": "9", "9th": "9",
            "tenth": "10", "10th": "10", "eleventh": "11", "11th": "11", "twelfth": "12", "12th": "12"
        }

        t_mod = text.lower()
        for word, num in word_numbers.items():
            t_mod = re.sub(rf"\b{word}\b", num, t_mod)

        pattern1 = r"(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)\s+(\d{1,2})(?:st|nd|rd|th)?"
        match1 = re.search(pattern1, t_mod)
        if match1:
            m_str, d_str = match1.group(1), match1.group(2)
            month = months[m_str]
            day = int(d_str)
            year = datetime.date.today().year
            d_obj = datetime.date(year, month, day)
            if d_obj < datetime.date.today():
                d_obj = datetime.date(year + 1, month, day)
            return d_obj.isoformat()

        pattern2 = r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|september|oct|october|nov|november|dec|december)"
        match2 = re.search(pattern2, t_mod)
        if match2:
            d_str, m_str = match2.group(1), match2.group(2)
            month = months[m_str]
            day = int(d_str)
            year = datetime.date.today().year
            d_obj = datetime.date(year, month, day)
            if d_obj < datetime.date.today():
                d_obj = datetime.date(year + 1, month, day)
            return d_obj.isoformat()

        if "tomorrow" in text.lower():
            return (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        return datetime.date.today().isoformat()

    def _extract_time(self, text: str) -> str:
        t_low = text.lower()
        match = re.search(r"(\d{1,2})[:\.\s](\d{2})", t_low)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}"

        match_h = re.search(r"(\d{1,2})\s*(pm|am)", t_low)
        if match_h:
            h = int(match_h.group(1))
            ampm = match_h.group(2)
            if ampm == "pm" and h < 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
            return f"{h:02d}:00"

        match_at = re.search(r"\bat\s+(\d{1,2})\b", t_low)
        if match_at:
            h = int(match_at.group(1))
            if 1 <= h <= 12 and "pm" in t_low:
                h = h + 12 if h < 12 else h
            return f"{h:02d}:00"

        return "12:30"

    def execute_action(
        self, db: Session, current_user: User, intent: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """Execute backend mutations if the action requires server-side DB creation or deletion."""
        action_type = intent.get("action_type")
        params = intent.get("params", {})
        response_text = intent.get("response_text", "Action completed.")

        # --- CREATE REMINDER ---
        if action_type == AssistantActionType.CREATE_REMINDER.value:
            title = params.get("title") or "Calendar Reminder"
            date_str = params.get("date_str")
            pet_name = params.get("pet_name")

            pets = list(db.scalars(select(Animal).where(Animal.owner_id == current_user.id)).all())
            target_animal = None
            if pet_name:
                for p in pets:
                    if p.name.lower() == pet_name.lower():
                        target_animal = p
                        break
            if target_animal is None and pets:
                target_animal = pets[0]

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
            }, f"Scheduled reminder '{title}' for {target_animal.name} on {d_obj.strftime('%d %b %Y')}!"

        # --- DELETE REMINDER ---
        if action_type == AssistantActionType.DELETE_REMINDER.value:
            user_reminders = list(db.scalars(select(Reminder).where(Reminder.owner_id == current_user.id)).all())
            if not user_reminders:
                return None, "You have no calendar reminders to delete."

            # Delete requested reminder or most recent
            target = user_reminders[-1]
            title_search = params.get("title", "").lower()
            for r in user_reminders:
                if title_search and r.title.lower() in title_search:
                    target = r
                    break

            deleted_title = target.title
            db.delete(target)
            db.commit()
            return {"id": str(target.id)}, f"Deleted calendar reminder '{deleted_title}'."

        # --- CREATE PET ---
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

        # --- DELETE PET ---
        if action_type == AssistantActionType.DELETE_PET.value:
            pets = list(db.scalars(select(Animal).where(Animal.owner_id == current_user.id)).all())
            if not pets:
                return None, "You have no pet profiles to delete."

            pet_name = (params.get("name") or "").lower()
            target_pet = None
            for p in pets:
                if pet_name and (pet_name in p.name.lower() or p.name.lower() in pet_name):
                    target_pet = p
                    break

            if target_pet is None and len(pets) == 1:
                target_pet = pets[0]

            if target_pet is None:
                return None, f"Could not find pet '{params.get('name')}' to delete. Your pets are: {', '.join(p.name for p in pets)}."

            deleted_name = target_pet.name
            db.delete(target_pet)
            db.commit()
            return {"id": str(target_pet.id)}, f"Successfully deleted pet '{deleted_name}' from your account."

        # --- UPDATE PET ---
        if action_type == AssistantActionType.UPDATE_PET.value:
            pets = list(db.scalars(select(Animal).where(Animal.owner_id == current_user.id)).all())
            if not pets:
                return None, "You have no pet profiles to update."

            target_pet = pets[0]
            pet_name = (params.get("name") or "").lower()
            for p in pets:
                if pet_name and p.name.lower() in pet_name:
                    target_pet = p
                    break

            if params.get("breed"):
                target_pet.breed = params.get("breed")
            if params.get("species"):
                target_pet.species = params.get("species")

            db.commit()
            db.refresh(target_pet)
            return {"id": str(target_pet.id)}, f"Updated details for pet '{target_pet.name}'."

        return None, response_text

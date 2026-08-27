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


ROUTE_CATALOG: list[dict[str, Any]] = [
    {
        "path": "/symptom-check",
        "name": "Symptom Checker",
        "summary": "Open Symptom Checker",
        "response_text": "Opening the pet symptom checker and clinical triage advisor.",
        "keywords": {
            "symptom", "symptoms", "check", "checker", "triage", "sick", "ill",
            "illness", "unwell", "vomit", "vomiting", "diarrhea", "lethargic",
            "cough", "coughing", "limp", "limping", "emergency", "advisor", "advice",
            "clinical", "diagnose", "diagnosis", "healthcheck", "fever", "pain"
        },
        "phrases": [
            "symptom checker", "symptom check", "check symptoms", "pet symptoms",
            "clinical triage", "triage advisor", "symptom triage", "sick pet",
            "my pet is sick", "check my pet", "health check"
        ],
    },
    {
        "path": "/symptom-check/history",
        "name": "Symptom Check History",
        "summary": "Open Symptom History",
        "response_text": "Opening your past symptom check and triage history.",
        "keywords": {
            "symptom", "symptoms", "triage", "history", "past", "records", "previous", "logs"
        },
        "phrases": [
            "symptom history", "triage history", "past symptoms", "previous symptom checks",
            "past triage", "symptom logs", "symptom check history"
        ],
    },
    {
        "path": "/new-owner-guide",
        "name": "New Pet Owner Guide",
        "summary": "Open New Owner Guide",
        "response_text": "Opening the new pet owner handbook and care guide.",
        "keywords": {
            "guide", "handbook", "owner", "owners", "tips", "care", "starter",
            "beginner", "newbie", "puppycare", "kittencare", "manual", "basics",
            "instructions", "advice", "onboarding"
        },
        "phrases": [
            "new owner guide", "owner guide", "pet guide", "puppy guide", "kitten guide",
            "pet handbook", "owner handbook", "care guide", "care tips", "beginner guide",
            "new pet guide", "how to care for pet"
        ],
    },
    {
        "path": "/appointments",
        "name": "Appointments",
        "summary": "Open Appointments",
        "response_text": "Opening your veterinary appointments and booking requests.",
        "keywords": {
            "appointment", "appointments", "booking", "bookings", "consultation",
            "consultations", "clinic", "schedule", "vetvisit", "scheduled", "reservation"
        },
        "phrases": [
            "my appointments", "vet appointments", "booking requests", "consultations",
            "scheduled appointments", "view appointments", "open appointments", "appointment bookings"
        ],
    },
    {
        "path": "/pets",
        "name": "My Pets",
        "summary": "Open My Pets",
        "response_text": "Opening your pet profiles.",
        "keywords": {
            "pet", "pets", "animal", "animals", "dog", "dogs", "cat", "cats",
            "puppy", "puppies", "kitten", "kittens", "profile", "profiles"
        },
        "phrases": [
            "my pets", "pet profiles", "pet list", "all pets", "view pets",
            "show pets", "open pets", "manage pets"
        ],
    },
    {
        "path": "/calendar",
        "name": "Calendar & Reminders",
        "summary": "Open Calendar",
        "response_text": "Opening your calendar and reminder schedule.",
        "keywords": {
            "calendar", "schedule", "event", "events", "reminder", "reminders",
            "agenda", "timeline", "dates", "upcoming", "due"
        },
        "phrases": [
            "my calendar", "view calendar", "open calendar", "reminders list",
            "upcoming events", "reminder schedule", "view schedule"
        ],
    },
    {
        "path": "/analyze",
        "name": "AI Pet Photo Analyzer",
        "summary": "Open AI Photo Analyzer",
        "response_text": "Opening the AI pet photo and skin analysis tool.",
        "keywords": {
            "analyze", "analysis", "photo", "scanner", "camera", "image",
            "picture", "skin", "lesion", "rash", "detect", "scan", "classifier"
        },
        "phrases": [
            "analyze photo", "photo analyzer", "ai analyzer", "scan photo",
            "skin analysis", "pet scanner", "upload photo", "take photo", "analyze image"
        ],
    },
    {
        "path": "/analysis/history",
        "name": "Analysis History",
        "summary": "Open Analysis History",
        "response_text": "Opening your past AI photo analysis scan history.",
        "keywords": {
            "analysis", "analyses", "scans", "history", "past", "photos",
            "records", "previous", "logs"
        },
        "phrases": [
            "analysis history", "scan history", "past analyses", "past scans",
            "photo history", "previous analyses", "ai history"
        ],
    },
    {
        "path": "/community",
        "name": "Community Feed",
        "summary": "Open Community",
        "response_text": "Navigating to the pet owner and vet community feed.",
        "keywords": {
            "community", "feed", "forum", "discussion", "discussions", "post",
            "posts", "social", "wall", "stories", "questions", "answers"
        },
        "phrases": [
            "community feed", "open community", "view discussions", "forum",
            "community forum", "social feed", "pet community"
        ],
    },
    {
        "path": "/community/new",
        "name": "Write Community Post",
        "summary": "Open Post Composer",
        "response_text": "Opening post composer for your community post.",
        "keywords": {
            "write", "create", "publish", "share", "ask", "post", "question", "story"
        },
        "phrases": [
            "create post", "new post", "write post", "ask question", "share post",
            "post composer", "publish post"
        ],
    },
    {
        "path": "/vets",
        "name": "Veterinarian Directory",
        "summary": "Open Vets Directory",
        "response_text": "Showing the veterinarian and clinic directory.",
        "keywords": {
            "vet", "vets", "doctor", "doctors", "veterinarian", "veterinarians",
            "clinic", "clinics", "hospital", "hospitals", "directory", "locate",
            "search", "near", "nearby"
        },
        "phrases": [
            "find vets", "vet directory", "find a doctor", "clinics near me",
            "veterinarian directory", "search vets", "locate clinics", "vet list"
        ],
    },
    {
        "path": "/profile",
        "name": "My Profile",
        "summary": "Open Profile",
        "response_text": "Opening your profile and account settings.",
        "keywords": {
            "profile", "account", "user", "bio", "details", "info", "personal",
            "verification", "license", "credentials", "avatar"
        },
        "phrases": [
            "my profile", "user profile", "account details", "edit profile",
            "vet verification", "license verification", "view profile"
        ],
    },
    {
        "path": "/settings",
        "name": "Settings",
        "summary": "Open Settings",
        "response_text": "Opening application preferences and settings.",
        "keywords": {
            "settings", "setting", "options", "preferences", "config", "configuration",
            "password", "security", "darkmode", "notifications"
        },
        "phrases": [
            "settings page", "app settings", "user preferences", "change password",
            "open settings", "configure app"
        ],
    },
    {
        "path": "/dashboard",
        "name": "Dashboard",
        "summary": "Open Dashboard",
        "response_text": "Opening your main dashboard overview.",
        "keywords": {
            "dashboard", "home", "main", "overview", "landing", "hub", "summary"
        },
        "phrases": [
            "my dashboard", "home page", "main page", "overview", "go home",
            "open dashboard", "return home"
        ],
    },
    {
        "path": "/admin/verifications",
        "name": "Admin Vet Verification Queue",
        "summary": "Open Verification Queue",
        "response_text": "Opening the admin veterinarian license verification queue.",
        "keywords": {
            "admin", "verification", "verifications", "queue", "licenses", "pending", "review"
        },
        "phrases": [
            "admin verifications", "verification queue", "review licenses",
            "pending vets", "admin queue"
        ],
    },
    {
        "path": "/admin/reports",
        "name": "Admin Moderation Queue",
        "summary": "Open Moderation Reports",
        "response_text": "Opening the admin community report and moderation queue.",
        "keywords": {
            "admin", "report", "reports", "moderation", "queue", "flagged", "reported"
        },
        "phrases": [
            "admin reports", "report queue", "moderation queue", "flagged posts",
            "reported comments"
        ],
    },
]


def _match_route_entry(text: str, tokens: set[str]) -> tuple[str, str, str] | None:
    """Semantic route matching using phrase weighting and keyword token overlap."""
    t_low = text.lower().strip()
    best_entry = None
    best_score = 0

    for entry in ROUTE_CATALOG:
        score = 0
        # Exact phrase matches receive high priority
        for phrase in entry.get("phrases", []):
            if phrase in t_low:
                score += 10 + len(phrase.split()) * 2

        # Token overlap
        overlap = len(tokens & entry["keywords"])
        score += overlap * 2

        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry and best_score >= 2:
        return best_entry["path"], best_entry["summary"], best_entry["response_text"]
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
            tmp_in.flush()
            in_path = tmp_in.name

        wav_path = in_path + ".wav"

        try:
            # Convert audio format to 16kHz mono PCM WAV via ffmpeg
            import subprocess
            cmd = ["ffmpeg", "-y", "-i", in_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            target_path = wav_path if (res.returncode == 0 and os.path.exists(wav_path)) else in_path

            result = model.transcribe(target_path, fp16=False, language="en")
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
        """Zero-shot semantic intent parsing via Ollama, falling back to a general vector-concept matcher.

        Supports single or multiple actions in a single command.
        """
        settings = get_settings()
        text_clean = text.strip()
        if not text_clean:
            empty_action = {
                "action_type": AssistantActionType.GENERAL_REPLY.value,
                "summary": "No speech detected",
                "params": {},
                "nav_target": None,
            }
            return {
                **empty_action,
                "actions": [empty_action],
                "response_text": "I didn't hear anything. How can I help you?",
            }

        # Try Ollama zero-shot multi-action classification first
        try:
            pets_info = ", ".join(f"{p['name']} ({p['species']})" for p in user_pets) or "None"
            nav_routes_desc = ", ".join(f"'{entry['path']}' ({entry['name']})" for entry in ROUTE_CATALOG)
            prompt = (
                "You are an intelligent zero-shot intent classifier for the UEP EMMY platform.\n"
                f"User request: '{text_clean}'\n"
                f"User pets: {pets_info}\n\n"
                "The user may ask for ONE or MULTIPLE software actions in a single command (e.g. 'Add a dog named Max and create a reminder for his checkup tomorrow').\n"
                "Extract all requested software actions in execution order.\n\n"
                "Available Actions:\n"
                "1. 'create_reminder': Schedule an event, reminder, appointment, checkup, or vaccination.\n"
                "   params: { 'title': str, 'date_str': str ('YYYY-MM-DD'), 'time_str': str ('HH:MM'), 'pet_name': str or null, 'category': 'checkup'|'vaccine'|'other' }, nav_target: '/calendar'\n"
                "2. 'delete_reminder': Delete or cancel an event or reminder.\n"
                "   params: { 'title': str or null, 'pet_name': str or null }, nav_target: '/calendar'\n"
                "3. 'create_pet': Register or add a new pet.\n"
                "   params: { 'name': str, 'species': 'dog'|'cat'|'other', 'breed': str or null }, nav_target: '/pets'\n"
                "4. 'delete_pet': Delete or remove an existing pet.\n"
                "   params: { 'name': str }, nav_target: '/pets'\n"
                "5. 'update_pet': Update or edit pet details (name, breed, species).\n"
                "   params: { 'name': str, 'breed': str or null, 'species': str or null }, nav_target: '/pets'\n"
                "6. 'navigate': View, visit, open, or switch to any page/section.\n"
                f"   Available nav_targets: {nav_routes_desc}\n"
                "7. 'create_post': Write or publish a post in the community.\n"
                "   params: { 'title': str, 'content': str }, nav_target: '/community/new'\n"
                "8. 'search_vets': Search or locate a vet, doctor, or clinic.\n"
                "   params: { 'query': str }, nav_target: '/vets'\n"
                "9. 'submit_verification': Submit veterinarian license or credentials for review.\n"
                "   nav_target: '/profile'\n"
                "10. 'general_reply': Conversational response for general questions or statements.\n\n"
                "Return ONLY a JSON object:\n"
                "{\n"
                '  "actions": [\n'
                '    {\n'
                '      "action_type": "...",\n'
                '      "summary": "...",\n'
                '      "params": { ... },\n'
                '      "nav_target": "/route" or null\n'
                '    }\n'
                '  ],\n'
                '  "response_text": "Friendly spoken response summarizing all actions"\n'
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
                    actions = []
                    if "actions" in data and isinstance(data["actions"], list) and data["actions"]:
                        actions = data["actions"]
                    elif "action_type" in data:
                        actions = [data]

                    if actions:
                        primary = actions[0]
                        nav_target = None
                        for act in reversed(actions):
                            if act.get("nav_target"):
                                nav_target = act.get("nav_target")
                                break
                        resp_text = data.get("response_text") or primary.get("summary") or "Processing commands."
                        logger.info(f"Ollama multi-action parsed: {[a.get('action_type') for a in actions]}")
                        return {
                            "actions": actions,
                            "action_type": primary.get("action_type", "general_reply"),
                            "summary": primary.get("summary", "Processed command"),
                            "params": primary.get("params", {}),
                            "nav_target": nav_target,
                            "response_text": resp_text,
                        }
        except Exception as e:
            logger.info(f"Ollama unavailable or timed out ({e}). Using generalized vector-concept NLP parser.")

        # Fallback to generalized semantic vector-concept matcher
        return self._semantic_concept_fallback(text_clean, user_pets)

    def _semantic_concept_fallback(self, text: str, user_pets: list[dict[str, Any]]) -> dict[str, Any]:
        """Compound semantic concept matcher.

        Splits compound requests into sub-clauses and parses multiple actions,
        propagating newly created pet context into subsequent tasks.
        """
        # Split on conjunctions, commas, semicolons, and clause boundaries
        raw_clauses = re.split(
            r"\b(?:and\s+then|and\s+also|and\s+after\s+that|after\s+that|and|then|also|as\s+well\s+as)\b|[,;]|\.\s+",
            text,
            flags=re.IGNORECASE,
        )

        cleaned_clauses = [c.strip() for c in raw_clauses if c.strip()]
        if not cleaned_clauses:
            cleaned_clauses = [text.strip()]

        actions: list[dict[str, Any]] = []
        context_pet_names: list[str] = []

        for clause in cleaned_clauses:
            action = self._parse_single_clause(clause, user_pets, context_pet_names)
            if action:
                # Avoid duplicate identical actions
                if not any(a["action_type"] == action["action_type"] and a["params"] == action["params"] for a in actions):
                    actions.append(action)
                    if action["action_type"] == AssistantActionType.CREATE_PET.value and action["params"].get("name"):
                        context_pet_names.append(action["params"]["name"])

        # If no actions found from clause splitting, run over full text
        if not actions:
            action = self._parse_single_clause(text, user_pets, context_pet_names)
            if action:
                actions.append(action)

        if not actions:
            actions = [{
                "action_type": AssistantActionType.GENERAL_REPLY.value,
                "summary": "Conversational reply",
                "params": {},
                "nav_target": None,
                "response_text": f"I understood: '{text}'. You can ask me to navigate, create or delete pets and reminders!",
            }]

        primary = actions[0]
        nav_target = None
        for act in reversed(actions):
            if act.get("nav_target"):
                nav_target = act.get("nav_target")
                break

        # Generate combined response summary text
        if len(actions) > 1:
            summaries = [a.get("response_text") or a.get("summary") for a in actions]
            combined_response = ". ".join(s.rstrip(".!") for s in summaries if s) + "!"
        else:
            combined_response = primary.get("response_text") or primary.get("summary", "Action processed.")

        return {
            "actions": actions,
            "action_type": primary.get("action_type", "general_reply"),
            "summary": primary.get("summary", "Processed command"),
            "params": primary.get("params", {}),
            "nav_target": nav_target,
            "response_text": combined_response,
        }

    def _parse_single_clause(
        self, clause: str, user_pets: list[dict[str, Any]], context_pet_names: list[str]
    ) -> dict[str, Any] | None:
        """Extract a single software action from a text clause."""
        t = clause.lower().strip()
        if not t:
            return None

        tokens = set(re.findall(r"\w+", t))

        REMINDER_CONCEPTS = {"remind", "reminder", "schedule", "event", "calendar", "appointment", "checkup", "vaccine", "vaccination", "book", "meeting", "vet"}
        PET_CONCEPTS = {"pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "kitten", "animal", "animals"}
        DELETE_CONCEPTS = {"delete", "remove", "erase", "drop", "cancel", "clear", "discard"}
        CREATE_CONCEPTS = {"add", "create", "register", "new", "got", "have"}
        UPDATE_CONCEPTS = {"update", "change", "edit", "modify", "rename"}
        POST_CREATE_CONCEPTS = {"write", "publish", "post", "share", "question", "forum"}
        VET_SEARCH_CONCEPTS = {"search", "find", "locate", "look", "where"}

        NAV_TRIGGERS = {"open", "navigate", "go", "take", "show", "visit", "switch", "view"}
        MUTATION_VERBS = {"create", "add", "register", "schedule", "book", "set", "delete", "remove", "erase", "cancel", "update", "change", "write", "post"}

        # 1. Check for Navigation Intent when triggered by nav verbs without mutation verbs
        if (tokens & NAV_TRIGGERS) and not (tokens & MUTATION_VERBS):
            matched = _match_route_entry(clause, tokens)
            if matched:
                route, summary, response_txt = matched
                return {
                    "action_type": AssistantActionType.NAVIGATE.value,
                    "summary": summary,
                    "params": {},
                    "nav_target": route,
                    "response_text": response_txt,
                }

        # 2. Check for Pet Deletion Intent
        if (tokens & DELETE_CONCEPTS) and (tokens & PET_CONCEPTS):
            matched_name = None
            for p in user_pets:
                if p["name"].lower() in tokens or p["name"].lower() in t:
                    matched_name = p["name"]
                    break
            for c_name in context_pet_names:
                if c_name.lower() in tokens or c_name.lower() in t:
                    matched_name = c_name
                    break

            name_target = matched_name or (
                re.search(r"(?:pet|dog|cat|named|called)\s+([a-zA-Z]+)", t).group(1).capitalize()
                if re.search(r"(?:pet|dog|cat|named|called)\s+([a-zA-Z]+)", t)
                else "Pet"
            )
            return {
                "action_type": AssistantActionType.DELETE_PET.value,
                "summary": f"Delete pet '{name_target}'",
                "params": {"name": name_target},
                "nav_target": "/pets",
                "response_text": f"Deleting pet '{name_target}' from your account.",
            }

        # 3. Check for Pet Creation Intent
        if (tokens & CREATE_CONCEPTS) and (tokens & PET_CONCEPTS or "named" in tokens or "called" in tokens) and not (tokens & {"reminder", "reminders", "event", "events", "appointment", "appointments", "checkup", "vaccine", "vaccination"}):
            name_match = re.search(r"(?:named|called|name\s+is)\s+([a-zA-Z]+)", t, re.I)
            if not name_match:
                name_match = re.search(
                    r"(?:add|create|register|got|have)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?(?:cat|dog|pet|puppy|kitten|feline|canine)\s+(?:named\s+|called\s+)?([a-zA-Z]+)",
                    t,
                    re.I,
                )
            name = name_match.group(1).capitalize() if name_match else "New Pet"
            species = "cat" if (tokens & {"cat", "kitten", "feline"}) else ("dog" if (tokens & {"dog", "puppy", "canine"}) else "other")
            return {
                "action_type": AssistantActionType.CREATE_PET.value,
                "summary": f"Register new {species} named '{name}'",
                "params": {"name": name, "species": species},
                "nav_target": "/pets",
                "response_text": f"Added new {species} named '{name}' to your pet profiles",
            }

        # 4. Check for Reminder Deletion Intent
        if (tokens & DELETE_CONCEPTS) and (tokens & REMINDER_CONCEPTS):
            return {
                "action_type": AssistantActionType.DELETE_REMINDER.value,
                "summary": "Delete calendar reminder",
                "params": {"title": clause},
                "nav_target": "/calendar",
                "response_text": "Removing calendar reminder.",
            }

        # 5. Check for Reminder Creation Intent
        REMINDER_CREATION_TRIGGERS = {"create", "add", "schedule", "set", "book", "remind", "appointment", "event", "checkup", "vaccine", "vaccination"}
        if (tokens & REMINDER_CREATION_TRIGGERS) and (tokens & {"reminder", "reminders", "schedule", "event", "events", "appointment", "appointments", "checkup", "checkups", "vaccine", "vaccines", "vaccination", "vaccinations", "calendar", "remind", "book"} or "at" in tokens or "tomorrow" in tokens or "today" in tokens):
            date_val = self._extract_date(t)
            time_val = self._extract_time(t)

            matched_pet = None
            # Check existing user pets
            for pet in user_pets:
                if pet["name"].lower() in tokens:
                    matched_pet = pet["name"]
                    break
            # Check newly created pets in this compound utterance
            if not matched_pet:
                for c_name in context_pet_names:
                    if c_name.lower() in tokens or any(pronoun in tokens for pronoun in ["him", "her", "his", "hers", "its", "it", "them"]):
                        matched_pet = c_name
                        break

            category = (
                "vaccine"
                if "vaccine" in t or "vaccination" in t
                else ("checkup" if "checkup" in t or "vet" in t or "doctor" in t else "other")
            )
            title = (
                f"{category.capitalize()} Appointment"
                if matched_pet is None
                else f"{category.capitalize()} for {matched_pet}"
            )

            match_for = re.search(
                r"(?:for|named|about|to)\s+([a-zA-Z0-9\s]+?)(?:\s+at|\s+on|\s+jan|\s+feb|\s+mar|\s+apr|\s+may|\s+jun|\s+jul|\s+aug|\s+sep|\s+oct|\s+nov|\s+dec|\s+today|\s+tomorrow|$)",
                t,
            )
            if match_for:
                extracted = match_for.group(1).strip()
                if len(extracted) > 2 and extracted not in [
                    "a", "the", "me", "my pet", "calendar", "event", "reminder", "him", "her", "it", "them"
                ]:
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
                "response_text": f"Created calendar event '{title}' for {formatted_date} at {time_val}",
            }

        # 5. Check for Pet Update Intent
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

        # 6. Check for Post Creation Intent
        if (tokens & POST_CREATE_CONCEPTS) and (tokens & {"post", "community", "thought", "question", "story"}):
            return {
                "action_type": AssistantActionType.CREATE_POST.value,
                "summary": "Create community post",
                "params": {"title": clause.capitalize(), "content": f"Shared via Emmy Voice Assistant: {clause}"},
                "nav_target": "/community/new",
                "response_text": "Opening post composer for your community post.",
            }

        # 7. Check for Vet Search Intent
        if (tokens & VET_SEARCH_CONCEPTS) and (tokens & {"vet", "vets", "doctor", "doctors", "clinic", "clinics"}):
            return {
                "action_type": AssistantActionType.SEARCH_VETS.value,
                "summary": "Search veterinarians",
                "params": {"query": clause},
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

        # 9. Semantic Concept Route Matching for Page Navigation
        matched = _match_route_entry(clause, tokens)
        if matched:
            route, summary, response_txt = matched
            return {
                "action_type": AssistantActionType.NAVIGATE.value,
                "summary": summary,
                "params": {},
                "nav_target": route,
                "response_text": response_txt,
            }

        return None

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

        # Check for weekday references (e.g. 'on Friday', 'next Monday')
        weekdays = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1, "tues": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6,
        }
        for wd, target_idx in weekdays.items():
            if re.search(rf"\b(?:on\s+|next\s+|this\s+)?{wd}\b", t_mod):
                today = datetime.date.today()
                today_idx = today.weekday()
                days_ahead = target_idx - today_idx
                if days_ahead <= 0:
                    days_ahead += 7
                return (today + datetime.timedelta(days=days_ahead)).isoformat()

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

    def execute_actions(
        self, db: Session, current_user: User, actions: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any] | None], str]:
        """Execute a list of backend actions sequentially within the DB transaction."""
        results: list[dict[str, Any] | None] = []
        messages: list[str] = []
        created_pets_map: dict[str, Animal] = {}

        for intent in actions:
            action_type = intent.get("action_type")
            params = intent.get("params", {})
            resp_txt = intent.get("response_text", "")

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
                db.flush()
                db.refresh(animal)

                created_pets_map[name.lower()] = animal

                results.append({
                    "id": str(animal.id),
                    "name": animal.name,
                    "species": animal.species,
                })
                messages.append(f"Added {animal.name} ({animal.species}) to your pet profiles")

            # --- CREATE REMINDER ---
            elif action_type == AssistantActionType.CREATE_REMINDER.value:
                title = params.get("title") or "Calendar Reminder"
                date_str = params.get("date_str")
                pet_name = params.get("pet_name")

                pets = list(db.scalars(select(Animal).where(Animal.owner_id == current_user.id)).all())
                target_animal = None

                # First check newly created pets in this compound execution
                if pet_name and pet_name.lower() in created_pets_map:
                    target_animal = created_pets_map[pet_name.lower()]
                elif pet_name:
                    for p in pets:
                        if p.name.lower() == pet_name.lower():
                            target_animal = p
                            break

                # If no pet specified, check if a pet was just created in this compound request
                if target_animal is None and created_pets_map:
                    target_animal = list(created_pets_map.values())[-1]
                elif target_animal is None and pets:
                    target_animal = pets[0]

                if target_animal is None:
                    target_animal = Animal(
                        name="My Pet",
                        species="dog",
                        owner_id=current_user.id,
                    )
                    db.add(target_animal)
                    db.flush()
                    db.refresh(target_animal)
                    created_pets_map[target_animal.name.lower()] = target_animal

                try:
                    d_obj = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
                except ValueError:
                    d_obj = datetime.date.today()

                rem_type = (
                    ReminderType.VACCINE
                    if params.get("category") == "vaccine"
                    else (
                        ReminderType.CHECKUP
                        if params.get("category") == "checkup"
                        else ReminderType.OTHER
                    )
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
                db.flush()
                db.refresh(reminder)

                results.append({
                    "id": str(reminder.id),
                    "title": reminder.title,
                    "due_date": reminder.due_date.isoformat(),
                    "animal_name": target_animal.name,
                })
                messages.append(f"Scheduled '{title}' for {target_animal.name} on {d_obj.strftime('%d %b %Y')}")

            # --- DELETE REMINDER ---
            elif action_type == AssistantActionType.DELETE_REMINDER.value:
                user_reminders = list(db.scalars(select(Reminder).where(Reminder.owner_id == current_user.id)).all())
                if not user_reminders:
                    results.append(None)
                    messages.append("No calendar reminders found to delete")
                else:
                    target = user_reminders[-1]
                    title_search = params.get("title", "").lower()
                    for r in user_reminders:
                        if title_search and r.title.lower() in title_search:
                            target = r
                            break
                    deleted_title = target.title
                    db.delete(target)
                    db.flush()
                    results.append({"id": str(target.id)})
                    messages.append(f"Deleted calendar reminder '{deleted_title}'")

            # --- DELETE PET ---
            elif action_type == AssistantActionType.DELETE_PET.value:
                pets = list(db.scalars(select(Animal).where(Animal.owner_id == current_user.id)).all())
                if not pets:
                    results.append(None)
                    messages.append("No pet profiles found to delete")
                else:
                    pet_name = (params.get("name") or "").lower()
                    target_pet = None
                    for p in pets:
                        if pet_name and (pet_name in p.name.lower() or p.name.lower() in pet_name):
                            target_pet = p
                            break
                    if target_pet is None and len(pets) == 1:
                        target_pet = pets[0]

                    if target_pet is None:
                        results.append(None)
                        messages.append(f"Could not find pet '{params.get('name')}' to delete")
                    else:
                        deleted_name = target_pet.name
                        db.delete(target_pet)
                        db.flush()
                        results.append({"id": str(target_pet.id)})
                        messages.append(f"Deleted pet '{deleted_name}'")

            # --- UPDATE PET ---
            elif action_type == AssistantActionType.UPDATE_PET.value:
                pets = list(db.scalars(select(Animal).where(Animal.owner_id == current_user.id)).all())
                if not pets:
                    results.append(None)
                    messages.append("No pet profiles found to update")
                else:
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
                    db.flush()
                    db.refresh(target_pet)
                    results.append({"id": str(target_pet.id)})
                    messages.append(f"Updated details for pet '{target_pet.name}'")

            # --- NON-MUTATING ACTIONS (navigate, search_vets, create_post, general_reply, etc.) ---
            else:
                results.append(None)
                if resp_txt:
                    messages.append(resp_txt)

        db.commit()

        if messages:
            if len(messages) == 1:
                final_text = messages[0]
                if not final_text.endswith((".", "!")):
                    final_text += "!"
            else:
                final_text = ". ".join(m.rstrip(".!") for m in messages) + "!"
        else:
            final_text = "Completed requested actions."

        return results, final_text

    def execute_action(
        self, db: Session, current_user: User, intent: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """Execute a single action (backward compatibility wrapper)."""
        actions = intent.get("actions") or [intent]
        results, combined_text = self.execute_actions(db, current_user, actions)
        return (results[0] if results else None), combined_text

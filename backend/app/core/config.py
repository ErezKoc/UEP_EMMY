from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "UEP EMMY — AI-Assisted Veterinary Platform"
    api_v1_prefix: str = "/v1"

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/uep_emmy"

    # Local S3 simulation
    storage_root: str = "./storage"
    storage_bucket: str = "uep-emmy-media"

    max_upload_mb: int = 10
    cors_origins: str = "http://localhost:5173"

    # Refuse to serve triage results from rules whose citations nobody has
    # checked. False while the team is still verifying sources; must be true
    # anywhere real users can reach the app.
    triage_require_verified_rules: bool = False

    # Auth (MVP): signs session tokens. Override in .env for anything shared.
    secret_key: str = "dev-only-change-me"
    token_ttl_hours: int = 24 * 7

    # Email. Leave `smtp_host` empty and nothing is sent: the message is
    # written to <storage_root>/outbox as a complete .eml and logged instead.
    # That is the default deliberately - this runs in Docker with no mail
    # credentials, and a sender that throws on every notification is worse than
    # one that writes down what it would have sent.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from: str = "UEP EMMY <no-reply@uepemmy.local>"

    # How often the reminder scheduler wakes up. Minutes, because reminders are
    # day-grained: checking more often cannot make an alert arrive sooner.
    notification_sweep_minutes: int = 15
    # Set false to keep the loop from starting at all (tests, one-off scripts).
    notification_sweep_enabled: bool = True

    # AI Assistant (Ollama & Whisper)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    whisper_model_size: str = "base"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

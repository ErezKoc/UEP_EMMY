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
    #: STARTTLS on the connection above (port 587). Set false only for a local
    #: capture server such as MailHog, which speaks plain SMTP on 1025.
    smtp_use_tls: bool = True
    #: Implicit TLS from the first byte (port 465). Mutually exclusive with
    #: STARTTLS; when both are set this one wins, because a server on 465 will
    #: not answer a plaintext EHLO and the connection would hang until timeout.
    smtp_use_ssl: bool = False
    smtp_from: str = "UEP EMMY <no-reply@uepemmy.local>"
    #: Nothing waits on this in a request - the queue runs in the background -
    #: but an unbounded socket read would still pin one sweep forever against a
    #: server that accepts the connection and then says nothing.
    smtp_timeout_seconds: int = 10

    #: Where the browser is, for links inside emails. There is nothing sensible
    #: to derive this from at send time: the queue runs in a background task
    #: with no request to read a Host header off, and guessing from the API's
    #: own origin would send people to the JSON API rather than the app.
    frontend_base_url: str = "http://localhost:5173"

    #: How often the email queue drains, in seconds. Seconds rather than the
    #: reminder sweep's minutes, because a password-reset link that waits a
    #: quarter of an hour is a password-reset link nobody uses.
    email_sweep_seconds: int = 30
    #: Messages moved per pass. A ceiling so one enormous backlog cannot hold a
    #: single pass open indefinitely; the next pass picks up where it left off.
    email_batch_size: int = 20
    #: Delivery attempts before a message is given up on as FAILED. Five
    #: attempts across the backoff schedule in `email_queue` covers about two
    #: hours, which is long enough to ride out a mail server restart and short
    #: enough that nobody is waiting on a message that will never arrive.
    email_max_attempts: int = 5

    #: How long an address-verification link stays valid. Long, deliberately:
    #: it is proof of an address rather than a credential, and a link that dies
    #: overnight is one people find expired the next morning.
    verify_email_ttl_hours: int = 48
    #: How long a password-reset link stays valid. Short, deliberately: for the
    #: minutes it lives, this link IS the password.
    password_reset_ttl_minutes: int = 60

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

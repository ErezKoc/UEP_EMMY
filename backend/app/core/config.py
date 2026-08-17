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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

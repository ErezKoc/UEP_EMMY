import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.seed import ensure_admin_account, seed_demo_data
from app.db.session import SessionLocal, engine
from app.services.ai import get_analysis_service

# Uvicorn only configures its own loggers, so without this the app's own INFO
# lines (which analyzer loaded, why it fell back) never reach the container log.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")

logger = logging.getLogger(__name__)

settings = get_settings()


def ensure_compatibility_columns() -> None:
    """Apply small MVP-era additions until Alembic is introduced."""
    inspector = inspect(engine)
    animal_columns = {column["name"] for column in inspector.get_columns("animals")}
    animal_additions = {
        # Added with the pets work; databases created before it never got them,
        # which made every /v1/animals call fail with "no such column".
        "birth_date": "ALTER TABLE animals ADD COLUMN birth_date DATE",
        "photo_url": "ALTER TABLE animals ADD COLUMN photo_url VARCHAR(1024)",
        "photo_position_x": (
            "ALTER TABLE animals ADD COLUMN photo_position_x INTEGER NOT NULL DEFAULT 50"
        ),
        "photo_position_y": (
            "ALTER TABLE animals ADD COLUMN photo_position_y INTEGER NOT NULL DEFAULT 50"
        ),
        "photo_zoom": "ALTER TABLE animals ADD COLUMN photo_zoom REAL NOT NULL DEFAULT 1.0",
    }
    analysis_columns = {
        column["name"] for column in inspector.get_columns("ai_analysis_logs")
    }
    analysis_additions = {
        "user_id": "ALTER TABLE ai_analysis_logs ADD COLUMN user_id CHAR(32)",
        "intake": "ALTER TABLE ai_analysis_logs ADD COLUMN intake JSON",
        "triage": "ALTER TABLE ai_analysis_logs ADD COLUMN triage JSON",
        "triage_level": "ALTER TABLE ai_analysis_logs ADD COLUMN triage_level VARCHAR(10)",
    }
    post_columns = {column["name"] for column in inspector.get_columns("posts")}
    post_additions = {
        "analysis_id": "ALTER TABLE posts ADD COLUMN analysis_id CHAR(32)",
        "image_url": "ALTER TABLE posts ADD COLUMN image_url VARCHAR(1024)",
    }
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    user_additions = {
        "verification_status": (
            "ALTER TABLE users ADD COLUMN verification_status VARCHAR(10) "
            "NOT NULL DEFAULT 'unverified'"
        ),
        # Community moderation (reports → suspend/ban).
        "account_status": (
            "ALTER TABLE users ADD COLUMN account_status VARCHAR(9) "
            "NOT NULL DEFAULT 'active'"
        ),
        "suspended_until": "ALTER TABLE users ADD COLUMN suspended_until TIMESTAMP",
        "moderation_note": "ALTER TABLE users ADD COLUMN moderation_note VARCHAR(1000)",
    }
    missing = [
        statement
        for name, statement in animal_additions.items()
        if name not in animal_columns
    ]
    missing.extend(
        statement
        for name, statement in analysis_additions.items()
        if name not in analysis_columns
    )
    missing.extend(
        statement
        for name, statement in post_additions.items()
        if name not in post_columns
    )
    missing.extend(
        statement
        for name, statement in user_additions.items()
        if name not in user_columns
    )
    with engine.begin() as connection:
        for statement in missing:
            connection.execute(text(statement))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ai_analysis_logs_user_id "
                "ON ai_analysis_logs (user_id)"
            )
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_posts_analysis_id ON posts (analysis_id)")
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_ai_analysis_logs_triage_level "
                "ON ai_analysis_logs (triage_level)"
            )
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP bootstrap: create tables directly from the models and seed demo
    # data. Replace with Alembic migrations before the schema starts evolving.
    Base.metadata.create_all(bind=engine)
    ensure_compatibility_columns()
    with SessionLocal() as db:
        seed_demo_data(db)
        # Runs on every boot: vet verification is unusable without an admin, and
        # existing databases predate the admin role.
        ensure_admin_account(db)

    # Build the analysis service now rather than on first use. Reading the two
    # ~19 MB ONNX files cold can take well over half a minute in Docker, and
    # paying that inside the first upload made the request outlive the client's
    # timeout — the user saw "the server did not respond" on an upload that was
    # in fact still running. Startup is the right place to absorb it.
    try:
        service = get_analysis_service()
        logger.info("Analysis service ready: %s", type(service).__name__)
    except Exception:
        # A warm-up failure must not stop the app booting; the request path
        # falls back to the mock analyzer on its own.
        logger.exception("Could not warm up the analysis service.")

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve objects from the local "S3 bucket" over HTTP. With real S3 this mount
# disappears in favor of presigned URLs / CloudFront.
media_dir = Path(settings.storage_root) / settings.storage_bucket
media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=media_dir), name="media")

app.include_router(api_router, prefix=settings.api_v1_prefix)

from app.api.recommendations import router as recommendations_router
app.include_router(recommendations_router, prefix=f"{settings.api_v1_prefix}")


@app.get("/healthz", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}

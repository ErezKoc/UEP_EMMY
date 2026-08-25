import logging
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.seed import ensure_admin_account, ensure_demo_clinic_details, seed_demo_data
from app.services.notifications import due_reminder_notifications
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
        # Owner corrections, added with the "let me fix what the AI got wrong"
        # work. Existing rows have neither, which reads as "not corrected".
        "correction": "ALTER TABLE ai_analysis_logs ADD COLUMN correction JSON",
        "corrected_at": "ALTER TABLE ai_analysis_logs ADD COLUMN corrected_at TIMESTAMP",
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
        # Clinic contact and location, added with the "find a vet" work. An
        # existing database has none of these, and every /v1/vets call would
        # fail with "no such column" until they are added.
        "clinic_phone": "ALTER TABLE users ADD COLUMN clinic_phone VARCHAR(40)",
        "clinic_emergency_phone": (
            "ALTER TABLE users ADD COLUMN clinic_emergency_phone VARCHAR(40)"
        ),
        "clinic_email": "ALTER TABLE users ADD COLUMN clinic_email VARCHAR(255)",
        "clinic_website": "ALTER TABLE users ADD COLUMN clinic_website VARCHAR(1024)",
        "clinic_address_line": (
            "ALTER TABLE users ADD COLUMN clinic_address_line VARCHAR(255)"
        ),
        "clinic_city": "ALTER TABLE users ADD COLUMN clinic_city VARCHAR(120)",
        "clinic_postcode": "ALTER TABLE users ADD COLUMN clinic_postcode VARCHAR(20)",
        "clinic_country": "ALTER TABLE users ADD COLUMN clinic_country VARCHAR(120)",
        "clinic_hours": "ALTER TABLE users ADD COLUMN clinic_hours VARCHAR(500)",
        "accepts_appointments": (
            "ALTER TABLE users ADD COLUMN accepts_appointments BOOLEAN NOT NULL DEFAULT 0"
        ),
        # Notification preferences. Both channels default ON for existing
        # accounts: somebody who already set reminders asked to be reminded.
        "notify_in_app": (
            "ALTER TABLE users ADD COLUMN notify_in_app BOOLEAN NOT NULL DEFAULT 1"
        ),
        "notify_email": (
            "ALTER TABLE users ADD COLUMN notify_email BOOLEAN NOT NULL DEFAULT 1"
        ),
        "notify_lead_days": (
            "ALTER TABLE users ADD COLUMN notify_lead_days INTEGER NOT NULL DEFAULT 1"
        ),
        # What time of day alerts go out, and the zone that time is in.
        # 09:00 for existing accounts: it is the hour they would have chosen,
        # and the alternative - keeping the old behaviour of "whenever the
        # sweep next woke up" - is the thing being fixed.
        "notify_time": (
            "ALTER TABLE users ADD COLUMN notify_time TIME NOT NULL DEFAULT '09:00:00'"
        ),
        # NULL means UTC, and the settings page says so rather than guessing.
        "notify_timezone": "ALTER TABLE users ADD COLUMN notify_timezone VARCHAR(64)",
    }
    comment_columns = {column["name"] for column in inspector.get_columns("comments")}
    comment_additions = {
        # Citations on community answers. `comment_votes` is a new TABLE and so
        # is created by `create_all`; these are new COLUMNS on an existing one,
        # which create_all does not touch — an existing database 500s on every
        # /v1/posts call without them.
        "source_url": "ALTER TABLE comments ADD COLUMN source_url VARCHAR(1024)",
        "source_title": "ALTER TABLE comments ADD COLUMN source_title VARCHAR(200)",
    }
    appointment_columns = {
        column["name"] for column in inspector.get_columns("appointments")
    }
    appointment_additions = {
        # Exact times, and rescheduling. `appointment_messages` is a new TABLE
        # and so is created by `create_all`; these are new COLUMNS on an
        # existing one, which create_all does not touch - an existing database
        # 500s on every /v1/appointments call without them.
        #
        # All nullable, with no backfill. A row confirmed before this feature
        # existed genuinely has no time on it, and inventing one - 09:00, or
        # midnight - would put a number in front of an owner that no practice
        # ever said. NULL reads as "no time was given", which is the truth.
        "preferred_time": "ALTER TABLE appointments ADD COLUMN preferred_time TIME",
        "scheduled_time": "ALTER TABLE appointments ADD COLUMN scheduled_time TIME",
        "proposed_date": "ALTER TABLE appointments ADD COLUMN proposed_date DATE",
        "proposed_time": "ALTER TABLE appointments ADD COLUMN proposed_time TIME",
        "proposed_by_id": "ALTER TABLE appointments ADD COLUMN proposed_by_id CHAR(32)",
        "proposed_note": "ALTER TABLE appointments ADD COLUMN proposed_note VARCHAR(1000)",
    }
    reminder_columns = {column["name"] for column in inspector.get_columns("reminders")}
    reminder_additions = {
        # Custom recurrence. An existing "monthly" row means every 1 month,
        # which is exactly what a default of 1 gives it.
        "recurrence_interval": (
            "ALTER TABLE reminders ADD COLUMN recurrence_interval INTEGER NOT NULL DEFAULT 1"
        ),
        "repeat_until": "ALTER TABLE reminders ADD COLUMN repeat_until DATE",
        # Per-reminder lead time. NULL rather than a copy of the account
        # default, so changing that default still moves everything which never
        # asked for something different. `reminder_occurrences` is a new TABLE
        # and so is created by `create_all`; this is a new COLUMN on an
        # existing one, which create_all does not touch.
        "notify_lead_days": "ALTER TABLE reminders ADD COLUMN notify_lead_days INTEGER",
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
    missing.extend(
        statement
        for name, statement in reminder_additions.items()
        if name not in reminder_columns
    )
    missing.extend(
        statement
        for name, statement in comment_additions.items()
        if name not in comment_columns
    )
    missing.extend(
        statement
        for name, statement in appointment_additions.items()
        if name not in appointment_columns
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


async def _notification_sweep() -> None:
    """Announce reminders coming due, for as long as the app is running.

    An asyncio task rather than cron or a worker process, because this deploys
    as a single container and adding a scheduler service to a project that has
    none would be a lot of infrastructure for a job that takes milliseconds.

    Two properties matter more than precision. It must never raise out of the
    loop - one bad reminder row must not silently end notifications for
    everybody until the next restart - and it must be safe to run as often as
    it likes, which is what the dedupe key in `notifications.py` guarantees.

    A second instance of this container would double up the work but not the
    alerts, for the same reason.
    """
    settings = get_settings()
    interval = max(60, settings.notification_sweep_minutes * 60)
    while True:
        try:
            with SessionLocal() as db:
                created = due_reminder_notifications(db)
            if created:
                logger.info("Notification sweep created %d reminder alert(s).", created)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification sweep failed; will try again next time.")
        await asyncio.sleep(interval)


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
        # Same reason: the demo veterinarians were seeded before clinic contact
        # details existed, and seeding never runs again once there is a user.
        ensure_demo_clinic_details(db)

    # Build the analysis service now rather than on first use. Reading the two
    # ~19 MB ONNX files cold can take well over half a minute in Docker, and
    # paying that inside the first upload made the request outlive the client's
    # timeout — the user saw "the server did not respond" on an upload that was
    # in fact still running. Startup is the right place to absorb it.
    # The sweep runs for the life of the process. Held on `app.state` so
    # shutdown can cancel it rather than leaving a task writing to a database
    # session that is being torn down.
    sweep_task: asyncio.Task | None = None
    if get_settings().notification_sweep_enabled:
        sweep_task = asyncio.create_task(_notification_sweep())

    try:
        service = get_analysis_service()
        logger.info("Analysis service ready: %s", type(service).__name__)
    except Exception:
        # A warm-up failure must not stop the app booting; the request path
        # falls back to the mock analyzer on its own.
        logger.exception("Could not warm up the analysis service.")

    yield

    if sweep_task is not None:
        sweep_task.cancel()
        # Swallowed on purpose: cancelling is how this task is meant to end,
        # and re-raising CancelledError here would make shutdown look failed.
        with suppress(asyncio.CancelledError):
            await sweep_task


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

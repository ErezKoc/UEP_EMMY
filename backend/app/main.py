from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine

settings = get_settings()


def ensure_compatibility_columns() -> None:
    """Apply small MVP-era additions until Alembic is introduced."""
    columns = {column["name"] for column in inspect(engine).get_columns("animals")}
    additions = {
        "photo_position_x": (
            "ALTER TABLE animals ADD COLUMN photo_position_x INTEGER NOT NULL DEFAULT 50"
        ),
        "photo_position_y": (
            "ALTER TABLE animals ADD COLUMN photo_position_y INTEGER NOT NULL DEFAULT 50"
        ),
        "photo_zoom": "ALTER TABLE animals ADD COLUMN photo_zoom REAL NOT NULL DEFAULT 1.0",
    }
    missing = [statement for name, statement in additions.items() if name not in columns]
    if not missing:
        return
    with engine.begin() as connection:
        for statement in missing:
            connection.execute(text(statement))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP bootstrap: create tables directly from the models and seed demo
    # data. Replace with Alembic migrations before the schema starts evolving.
    Base.metadata.create_all(bind=engine)
    ensure_compatibility_columns()
    with SessionLocal() as db:
        seed_demo_data(db)
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


@app.get("/healthz", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}

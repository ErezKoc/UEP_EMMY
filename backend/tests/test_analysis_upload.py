import asyncio
import json
from io import BytesIO

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.analysis import upload_and_analyze
from app.db.base import Base
from app.models import AIAnalysisLog
from app.services.ai import MockImageAnalysisService
from app.services.storage import LocalS3Storage
from app.services.triage import TriageEngine


def test_unlinked_upload_uses_detected_species_for_triage(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    upload = UploadFile(
        filename="eye.jpg",
        file=BytesIO(b"deterministic mock image"),
        headers=Headers({"content-type": "image/jpeg"}),
    )
    intake = json.dumps(
        {
            "concern": "eyes",
            "body_area": "eye",
            "duration": "today",
            "trend": "unchanged",
            "red_flags": [],
        }
    )

    with Session(engine) as session:
        response = asyncio.run(
            upload_and_analyze(
                file=upload,
                animal_id=None,
                intake=intake,
                db=session,
                current_user=None,
                storage=LocalS3Storage(str(tmp_path), "test-bucket"),
                analyzer=MockImageAnalysisService(),
                triage_engine=TriageEngine(require_verified=False),
            )
        )

        stored = session.scalar(select(AIAnalysisLog))

    assert response.triage is not None
    assert response.triage.headline == "Veterinary examination recommended within 24 hours"
    assert stored is not None
    assert stored.intake["species"] == response.result.species

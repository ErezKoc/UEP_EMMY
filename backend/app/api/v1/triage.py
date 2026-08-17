"""Symptom triage.

`POST /v1/triage` assesses an intake without storing anything — useful for
testing the rules and for previewing a verdict. The stored path is
`POST /v1/analysis/upload`, which attaches the same assessment to the analysis
so it appears in the pet's history.
"""

from fastapi import APIRouter, Depends

from app.schemas.triage import SymptomIntake, TriageAssessment
from app.services.triage import TriageEngine, get_triage_engine

router = APIRouter()


@router.post("", response_model=TriageAssessment)
def assess(
    intake: SymptomIntake,
    engine: TriageEngine = Depends(get_triage_engine),
) -> TriageAssessment:
    """Assess reported symptoms. Stores nothing."""
    return engine.assess(intake)

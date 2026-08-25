from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    animals,
    appointments,
    dashboard,
    notifications,
    assistant,
    auth,
    posts,
    reminders,
    reports,
    symptom_checks,
    triage,
    users,
    verification,
    vets,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(animals.router, prefix="/animals", tags=["animals"])
api_router.include_router(triage.router, prefix="/triage", tags=["triage"])
api_router.include_router(
    symptom_checks.router, prefix="/symptom-checks", tags=["symptom-checks"]
)
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(vets.router, prefix="/vets", tags=["vets"])
api_router.include_router(
    appointments.router, prefix="/appointments", tags=["appointments"]
)
api_router.include_router(reminders.router, prefix="/reminders", tags=["reminders"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(verification.router, prefix="/verification", tags=["verification"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(assistant.router, prefix="/assistant", tags=["assistant"])

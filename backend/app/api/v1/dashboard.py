"""The owner's dashboard: every pet, what needs doing, and what is next."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.dashboard import (
    AppointmentBrief,
    DashboardRead,
    PetSummaryRead,
    TaskRead,
)
from app.services.dashboard import build_dashboard

router = APIRouter()


def _brief(appointment: Appointment | None) -> AppointmentBrief | None:
    if appointment is None:
        return None
    return AppointmentBrief(
        id=appointment.id,
        scheduled_date=appointment.scheduled_date,
        scheduled_time=appointment.scheduled_time,
        practice=appointment.vet.clinic_name or appointment.vet.display_name,
        pet_name=appointment.animal.name if appointment.animal else None,
        # Said on the card rather than left for the appointments page. A date
        # presented as settled while a move is waiting on an answer is how
        # somebody turns up on a day that changed.
        move_pending=appointment.status is AppointmentStatus.RESCHEDULE_PROPOSED,
    )


@router.get("", response_model=DashboardRead)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardRead:
    """Everything the dashboard needs, in one request.

    One call rather than five. The page was already exceeding the browser's
    six-connection budget - the getting-started checks had been made sequential
    for exactly that reason - and per-pet summaries assembled client-side would
    have meant a request per pet on top.
    """
    data = build_dashboard(db, current_user)
    return DashboardRead(
        pets=[
            PetSummaryRead(
                animal=summary.animal,
                overdue_reminders=summary.overdue_reminders,
                next_reminder_title=summary.next_reminder_title,
                next_reminder_date=summary.next_reminder_date,
                next_appointment=_brief(summary.next_appointment),
                last_check_level=summary.last_check_level,
                last_check_headline=summary.last_check_headline,
                last_check_at=summary.last_check_at,
                last_analysis_at=summary.last_analysis_at,
                profile_conflicts=summary.profile_conflicts,
                tasks=[TaskRead.model_validate(task) for task in summary.tasks],
            )
            for summary in data["pets"]
        ],
        tasks=[TaskRead.model_validate(task) for task in data["tasks"]],
        next_appointment=_brief(data["next_appointment"]),
        urgent_count=data["urgent_count"],
    )

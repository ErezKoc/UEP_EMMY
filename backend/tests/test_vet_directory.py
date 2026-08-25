"""Finding a vet by distance, specialty, opening status, price and availability.

One rule runs through every test here, and it is the one worth breaking the
build over: a practice that has told us nothing must never be reported as a
"no". A clinic with no coordinates is not far away, one with no opening grid is
not closed, and one with no published slots is not fully booked. Getting that
wrong means the directory quietly hides real practices from an owner looking
for help, and none of those practices would ever know.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers every table with Base.metadata
from app.api.v1.vets import list_slots, list_veterinarians, publish_slots, withdraw_slot
from app.db.base import Base
from app.models import AvailabilitySlot, User, UserRole, VerificationStatus
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.availability import SlotCreate
from app.services.clinic_directory import (
    distance_km,
    normalise_grid,
    normalise_specialties,
    opening_status,
)

TODAY = date.today()

# Istanbul and Ankara, roughly. Far enough apart that no rounding argument can
# make them look like neighbours.
ISTANBUL = (41.0082, 28.9784)
ANKARA = (39.9334, 32.8597)

FULL_WEEK = {
    "mon": [["09:00", "13:00"], ["14:00", "18:00"]],
    "tue": [["09:00", "18:00"]],
    "wed": [["09:00", "18:00"]],
    "thu": [["09:00", "18:00"]],
    "fri": [["09:00", "18:00"]],
    "sat": [["09:00", "13:00"]],
}


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def make_vet(session, name="Dr. Test", **fields) -> User:
    defaults = dict(
        email=f"{name.lower().replace(' ', '.').replace('.', '')}@example.com",
        display_name=name,
        role=UserRole.VETERINARIAN,
        verification_status=VerificationStatus.VERIFIED,
        accepts_appointments=True,
    )
    defaults.update(fields)
    vet = User(**defaults)
    session.add(vet)
    session.commit()
    return vet


def search(session, **kwargs):
    """`list_veterinarians` with every query parameter spelled out.

    Calling the endpoint directly skips FastAPI, so an omitted argument arrives
    as the `Query(...)` object itself rather than its default.
    """
    params = dict(
        q=None,
        verified_only=False,
        accepting_only=False,
        lat=None,
        lng=None,
        radius_km=None,
        specialty=None,
        open_now=False,
        max_fee=None,
        has_availability=False,
        availability_days=14,
        sort="relevance",
    )
    params.update(kwargs)
    return list_veterinarians(db=session, **params)


def names(rows) -> list[str]:
    return [row.display_name for row in rows]


# ------------------------------------------------------------------ distance


def test_distance_is_none_when_either_end_is_unplaced():
    assert distance_km(None, None, *ISTANBUL) is None
    assert distance_km(*ISTANBUL, None, None) is None


def test_distance_between_two_known_points_is_about_right():
    """Istanbul to Ankara is roughly 350 km in a straight line."""
    measured = distance_km(*ISTANBUL, *ANKARA)
    assert 340 < measured < 360


def test_a_practice_with_no_coordinates_is_not_treated_as_far_away(session):
    """It has no distance at all, and a radius filter leaves it out rather than
    ranking it last with a made-up number."""
    make_vet(session, "Dr. Placed", clinic_latitude=ISTANBUL[0], clinic_longitude=ISTANBUL[1])
    make_vet(session, "Dr. Unplaced")

    everything = search(session, lat=ISTANBUL[0], lng=ISTANBUL[1])
    placed = {row.display_name: row.distance_km for row in everything}

    assert placed["Dr. Unplaced"] is None
    assert placed["Dr. Placed"] == 0.0
    # Still listed when nobody asked about distance.
    assert "Dr. Unplaced" in names(everything)


def test_a_radius_excludes_the_far_and_the_unplaced_alike(session):
    make_vet(session, "Dr. Near", clinic_latitude=ISTANBUL[0], clinic_longitude=ISTANBUL[1])
    make_vet(session, "Dr. Far", clinic_latitude=ANKARA[0], clinic_longitude=ANKARA[1])
    make_vet(session, "Dr. Unplaced")

    near = search(session, lat=ISTANBUL[0], lng=ISTANBUL[1], radius_km=50)

    assert names(near) == ["Dr. Near"]


def test_sorting_by_distance_sinks_the_unplaced_rather_than_dropping_them(session):
    """A sort is not a filter. `radius_km` is how somebody says "only ones you
    can place"; asking for the nearest first must not silently delete the rest."""
    make_vet(session, "Dr. Far", clinic_latitude=ANKARA[0], clinic_longitude=ANKARA[1])
    make_vet(session, "Dr. Unplaced")
    make_vet(session, "Dr. Near", clinic_latitude=ISTANBUL[0], clinic_longitude=ISTANBUL[1])

    rows = search(session, lat=ISTANBUL[0], lng=ISTANBUL[1], sort="distance")

    assert names(rows) == ["Dr. Near", "Dr. Far", "Dr. Unplaced"]


# ----------------------------------------------------------------- specialty


def test_unknown_specialties_are_dropped_rather_than_stored():
    """A specialty nothing can filter on is a claim no search will ever match."""
    assert normalise_specialties(["surgery", "wizardry", "DENTISTRY"]) == [
        "surgery",
        "dentistry",
    ]
    assert normalise_specialties([]) is None
    assert normalise_specialties("surgery") is None


def test_filtering_by_specialty_keeps_any_match_not_every_match(session):
    """Somebody who ticks "surgery" and "dentistry" wants either, not both -
    a practice offering one of the two is a practice that can help."""
    make_vet(session, "Dr. Surgeon", specialties=["surgery"])
    make_vet(session, "Dr. Dentist", specialties=["dentistry"])
    make_vet(session, "Dr. General", specialties=["general"])

    rows = search(session, specialty=["surgery", "dentistry"])

    assert sorted(names(rows)) == ["Dr. Dentist", "Dr. Surgeon"]


def test_a_practice_that_listed_no_specialty_is_still_in_the_directory(session):
    make_vet(session, "Dr. Quiet")

    assert names(search(session)) == ["Dr. Quiet"]
    assert search(session, specialty=["surgery"]) == []


# ------------------------------------------------------------ opening status


def test_open_now_is_none_when_no_hours_are_published():
    """The third state that stops this feature closing real clinics.

    "We do not know" and "closed" look identical on a card with only a boolean,
    and telling somebody a clinic is shut when nobody ever said so is how a pet
    does not get seen.
    """
    assert opening_status(None, "Europe/Istanbul").is_open is None
    assert opening_status({}, "Europe/Istanbul").is_open is None


def test_open_now_reads_the_grid_in_the_clinics_own_timezone():
    """09:00 on a server in UTC is not 09:00 at the practice."""
    # 07:00 UTC on a Wednesday is 10:00 in Istanbul - open.
    wednesday = datetime(2026, 8, 26, 7, 0, tzinfo=timezone.utc)

    here = opening_status(FULL_WEEK, "Europe/Istanbul", wednesday)
    utc = opening_status(FULL_WEEK, None, wednesday)

    assert here.is_open is True and here.closes_at == "18:00"
    # Read as UTC the same instant is 07:00, before opening.
    assert utc.is_open is False and utc.opens_at == "09:00"


def test_the_lunch_gap_in_split_hours_counts_as_closed():
    """A single open-close pair would tell somebody with an emergency at 13:30
    to set off."""
    monday_lunch = datetime(2026, 8, 24, 10, 30, tzinfo=timezone.utc)  # 13:30 local

    status = opening_status(FULL_WEEK, "Europe/Istanbul", monday_lunch)

    assert status.is_open is False
    assert status.opens_at == "14:00"
    assert status.opens_day == "today"


def test_when_closed_for_the_day_it_names_the_next_day_that_opens():
    """Saturday 14:00 local - shut, and Sunday is not in the grid at all."""
    saturday_afternoon = datetime(2026, 8, 29, 11, 0, tzinfo=timezone.utc)

    status = opening_status(FULL_WEEK, "Europe/Istanbul", saturday_afternoon)

    assert status.is_open is False
    assert status.opens_day == "Monday"


def test_a_backwards_period_is_dropped_rather_than_honoured():
    """It is a typo, not an overnight opening. Honouring it would report the
    practice as open for twenty-two hours."""
    assert normalise_grid({"mon": [["18:00", "09:00"]]}) is None
    assert normalise_grid({"mon": [["09:00", "17:00"], ["nonsense", "x"]]}) == {
        "mon": [["09:00", "17:00"]]
    }


def test_filtering_by_open_now_excludes_the_unknown(session):
    """`is True`, not truthiness: a practice we know nothing about must not be
    presented as one we have confirmed is open."""
    make_vet(session, "Dr. Open", clinic_hours_grid=FULL_WEEK, clinic_timezone="Europe/Istanbul")
    make_vet(session, "Dr. Silent")

    everything = search(session)
    assert sorted(names(everything)) == ["Dr. Open", "Dr. Silent"]
    assert {row.display_name: row.open_now for row in everything}["Dr. Silent"] is None

    filtered = search(session, open_now=True)
    assert "Dr. Silent" not in names(filtered)


# --------------------------------------------------------------------- price


def test_the_price_ceiling_is_compared_against_the_bottom_of_the_range(session):
    """The bottom is the only figure a practice quoting "400-900" committed to.
    Filtering on the top would hide every clinic whose most expensive procedure
    exceeds the budget, which is nearly all of them."""
    make_vet(session, "Dr. Cheap", consultation_fee_min=300, consultation_fee_max=1200)
    make_vet(session, "Dr. Dear", consultation_fee_min=900, consultation_fee_max=1500)

    rows = search(session, max_fee=500)

    assert names(rows) == ["Dr. Cheap"]


def test_a_practice_that_published_no_price_is_not_assumed_free(session):
    make_vet(session, "Dr. Quoted", consultation_fee_min=300)
    make_vet(session, "Dr. Unquoted")

    assert sorted(names(search(session))) == ["Dr. Quoted", "Dr. Unquoted"]
    assert names(search(session, max_fee=500)) == ["Dr. Quoted"]


def test_sorting_by_price_puts_the_unquoted_last(session):
    make_vet(session, "Dr. Unquoted")
    make_vet(session, "Dr. Dear", consultation_fee_min=900)
    make_vet(session, "Dr. Cheap", consultation_fee_min=300)

    assert names(search(session, sort="price")) == ["Dr. Cheap", "Dr. Dear", "Dr. Unquoted"]


# ---------------------------------------------------------------- publishing


def test_a_practice_can_publish_a_weekly_run_in_one_go(session):
    """Publishing one slot at a time is the reason nobody would ever do it."""
    vet = make_vet(session)

    created = publish_slots(
        SlotCreate(
            slot_date=TODAY + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(9, 30),
            repeat_weeks=3,
        ),
        db=session,
        current_user=vet,
    )

    assert len(created) == 4
    assert [slot.slot_date for slot in created] == [
        TODAY + timedelta(days=1 + 7 * week) for week in range(4)
    ]


def test_republishing_the_same_run_skips_what_already_exists(session):
    """A practice repeating a run means "make sure these are all published".
    Failing the whole thing over week three would leave them working out which
    weeks landed."""
    vet = make_vet(session)
    payload = SlotCreate(
        slot_date=TODAY + timedelta(days=1),
        start_time=time(9, 0),
        end_time=time(9, 30),
        repeat_weeks=2,
    )
    publish_slots(payload, db=session, current_user=vet)

    again = publish_slots(payload, db=session, current_user=vet)

    assert again == []
    assert len(vet.availability_slots) == 3


def test_only_a_veterinarian_can_publish_openings(session):
    """A slot is a practice saying "we are free then", and nobody can say that
    for them."""
    owner = User(email="owner@example.com", display_name="Owner")
    session.add(owner)
    session.commit()

    with pytest.raises(HTTPException) as raised:
        publish_slots(
            SlotCreate(
                slot_date=TODAY + timedelta(days=1),
                start_time=time(9, 0),
                end_time=time(9, 30),
            ),
            db=session,
            current_user=owner,
        )
    assert raised.value.status_code == 403


def test_a_slot_in_the_past_is_refused(session):
    vet = make_vet(session)

    with pytest.raises(HTTPException) as raised:
        publish_slots(
            SlotCreate(
                slot_date=TODAY - timedelta(days=1),
                start_time=time(9, 0),
                end_time=time(9, 30),
            ),
            db=session,
            current_user=vet,
        )
    assert raised.value.status_code == 400


def test_a_slot_must_end_after_it_starts():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SlotCreate(
            slot_date=TODAY + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(9, 0),
        )


# --------------------------------------------------------- what owners see


def _slot(session, vet, days_ahead=1, at=time(9, 0), capacity=1) -> AvailabilitySlot:
    slot = AvailabilitySlot(
        vet_id=vet.id,
        slot_date=TODAY + timedelta(days=days_ahead),
        start_time=at,
        end_time=time(at.hour + 1, at.minute),
        capacity=capacity,
    )
    session.add(slot)
    session.commit()
    return slot


def test_past_openings_are_never_listed(session):
    """An opening that has gone is not availability, and a stale page must not
    be able to send somebody to request yesterday."""
    vet = make_vet(session)
    session.add(
        AvailabilitySlot(
            vet_id=vet.id,
            slot_date=TODAY - timedelta(days=2),
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
    )
    session.commit()

    assert list_slots(vet.id, days=14, include_full=False, db=session) == []


def test_a_confirmed_appointment_uses_up_the_slot(session):
    vet = make_vet(session)
    owner = User(email="owner@example.com", display_name="Owner")
    session.add(owner)
    session.commit()
    slot = _slot(session, vet)

    session.add(
        Appointment(
            owner_id=owner.id,
            vet_id=vet.id,
            reason="Limping.",
            preferred_date=slot.slot_date,
            slot_id=slot.id,
            status=AppointmentStatus.CONFIRMED,
        )
    )
    session.commit()
    session.refresh(slot)

    assert slot.taken == 1
    assert slot.is_open is False
    assert list_slots(vet.id, days=14, include_full=False, db=session) == []


def test_an_unanswered_request_does_not_hold_the_slot(session):
    """The practice may yet decline it, and a slot held by a request nobody has
    answered is a slot quietly lost."""
    vet = make_vet(session)
    owner = User(email="owner@example.com", display_name="Owner")
    session.add(owner)
    session.commit()
    slot = _slot(session, vet)

    session.add(
        Appointment(
            owner_id=owner.id,
            vet_id=vet.id,
            reason="Limping.",
            preferred_date=slot.slot_date,
            slot_id=slot.id,
            status=AppointmentStatus.REQUESTED,
        )
    )
    session.commit()
    session.refresh(slot)

    assert slot.taken == 0
    assert slot.is_open is True


def test_an_open_surgery_takes_several_bookings(session):
    """Some practices tell six owners the same hour and see them in order.
    Forcing those onto separate slots would misrepresent how they work."""
    vet = make_vet(session)
    owner = User(email="owner@example.com", display_name="Owner")
    session.add(owner)
    session.commit()
    slot = _slot(session, vet, capacity=3)

    for _ in range(2):
        session.add(
            Appointment(
                owner_id=owner.id,
                vet_id=vet.id,
                reason="Vaccination.",
                preferred_date=slot.slot_date,
                slot_id=slot.id,
                status=AppointmentStatus.CONFIRMED,
            )
        )
    session.commit()
    session.refresh(slot)

    assert (slot.taken, slot.is_open) == (2, True)


def test_a_slot_somebody_is_booked_into_cannot_be_withdrawn(session):
    """Withdrawing it would not cancel their appointment - it would leave an
    owner holding a confirmation for a time the practice no longer shows."""
    vet = make_vet(session)
    owner = User(email="owner@example.com", display_name="Owner")
    session.add(owner)
    session.commit()
    slot = _slot(session, vet)
    session.add(
        Appointment(
            owner_id=owner.id,
            vet_id=vet.id,
            reason="Limping.",
            preferred_date=slot.slot_date,
            slot_id=slot.id,
            status=AppointmentStatus.CONFIRMED,
        )
    )
    session.commit()

    with pytest.raises(HTTPException) as raised:
        withdraw_slot(slot.id, db=session, current_user=vet)
    assert raised.value.status_code == 409


def test_a_practice_cannot_withdraw_somebody_elses_opening(session):
    vet = make_vet(session, "Dr. One")
    other = make_vet(session, "Dr. Two")
    slot = _slot(session, vet)

    with pytest.raises(HTTPException) as raised:
        withdraw_slot(slot.id, db=session, current_user=other)
    assert raised.value.status_code == 404


def test_having_availability_is_a_filter_not_a_ranking(session):
    """A practice that has published nothing is not fully booked - most
    practices publish nothing at all."""
    with_slots = make_vet(session, "Dr. Published")
    make_vet(session, "Dr. Silent")
    _slot(session, with_slots)

    everything = search(session)
    assert sorted(names(everything)) == ["Dr. Published", "Dr. Silent"]

    filtered = search(session, has_availability=True)
    assert names(filtered) == ["Dr. Published"]
    assert filtered[0].next_slot_date == TODAY + timedelta(days=1)
    assert filtered[0].published_slot_count == 1


def test_sorting_by_soonest_puts_the_unpublished_last(session):
    make_vet(session, "Dr. Silent")
    later = make_vet(session, "Dr. Later")
    sooner = make_vet(session, "Dr. Sooner")
    _slot(session, later, days_ahead=9)
    _slot(session, sooner, days_ahead=2)

    assert names(search(session, sort="soonest", availability_days=30)) == [
        "Dr. Sooner",
        "Dr. Later",
        "Dr. Silent",
    ]


def test_an_opening_beyond_the_window_is_not_counted_as_availability(session):
    """"Anything in the next fortnight?" must not be answered with a slot in
    November."""
    vet = make_vet(session, "Dr. Distant")
    _slot(session, vet, days_ahead=40)

    assert search(session, has_availability=True, availability_days=14) == []
    assert names(search(session, has_availability=True, availability_days=60)) == [
        "Dr. Distant"
    ]

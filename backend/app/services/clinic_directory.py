"""What a practice is, where it is, and whether its door is open right now.

Everything here answers a question an owner asks while standing in their
kitchen with a limping dog: how far, what do they treat, are they open, what
does it cost, and can I actually be seen. Each of those needs something the
directory did not hold, and each has a different honest failure mode when the
practice has not filled it in - which is most of what this module is about.

The rule throughout: a practice that has told us nothing must not be reported
as a "no". A clinic with no coordinates is not far away; a clinic with no
opening grid is not closed; a clinic with no published slots is not fully
booked. Every filter below leaves those out of the *filtered* result rather
than ranking them last with a wrong label, and every card says "not listed"
rather than inventing a value.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: The specialties a practice can claim, as slug -> label.
#:
#: A fixed list rather than free text, because this is a FILTER. Free text
#: gives "Exotics", "exotic animals", "Exotic pets" and "Zoo & Exotic" as four
#: different specialties, and an owner searching for any one of them misses the
#: practices that wrote the other three.
#:
#: Deliberately short and general. A longer list reads as more precise, but a
#: practice picking from thirty tick-boxes picks badly, and an owner filtering
#: on a specialty nobody selected sees an empty directory and concludes there
#: are no vets.
SPECIALTIES: dict[str, str] = {
    "general": "General practice",
    "emergency": "Emergency and critical care",
    "surgery": "Surgery",
    "dentistry": "Dentistry",
    "dermatology": "Skin and allergies",
    "cardiology": "Heart",
    "ophthalmology": "Eyes",
    "orthopaedics": "Bones and joints",
    "oncology": "Cancer care",
    "behaviour": "Behaviour",
    "exotics": "Exotics, birds and small mammals",
    "imaging": "Imaging and diagnostics",
}

#: Keys of the weekly opening grid, Monday first to match `date.weekday()`.
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

EARTH_RADIUS_KM = 6371.0


# ------------------------------------------------------------------ distance


def distance_km(
    lat1: float | None, lon1: float | None, lat2: float | None, lon2: float | None
) -> float | None:
    """Great-circle distance, or None when either end is unknown.

    Straight-line, not driving distance, and the interface says "straight line"
    for that reason. Routing needs a service this deployment does not have, and
    a number labelled simply "3.2 km" would be read as the distance the owner
    has to travel - which across a river or a motorway can be triple.
    """
    if None in (lat1, lon1, lat2, lon2):
        return None
    phi1, phi2 = radians(float(lat1)), radians(float(lat2))
    dphi = phi2 - phi1
    dlambda = radians(float(lon2) - float(lon1))
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * asin(sqrt(a)), 1)


# -------------------------------------------------------------- opening hours


def _parse_clock(value: Any) -> time | None:
    if not isinstance(value, str):
        return None
    try:
        hours, minutes = value.split(":")[:2]
        return time(int(hours), int(minutes))
    except (ValueError, TypeError):
        return None


def intervals_for(grid: dict[str, Any] | None, day: date) -> list[tuple[time, time]]:
    """The open periods on one day, as (from, to) pairs.

    A list per day rather than one pair, because split hours are the norm: a
    practice open 09:00-13:00 and 14:00-18:00 is closed at lunchtime, and a
    single pair would tell somebody with an emergency at 13:30 to set off.
    """
    if not isinstance(grid, dict):
        return []
    raw = grid.get(WEEKDAYS[day.weekday()])
    if not isinstance(raw, list):
        return []

    periods: list[tuple[time, time]] = []
    for entry in raw:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            continue
        opens, closes = _parse_clock(entry[0]), _parse_clock(entry[1])
        # A period that ends before it starts is a typo, not an overnight
        # opening. Dropping it loses one line; honouring it would report a
        # practice as open for twenty-two hours.
        if opens is None or closes is None or closes <= opens:
            continue
        periods.append((opens, closes))
    periods.sort()
    return periods


def clinic_now(timezone_name: str | None, moment: datetime | None = None) -> datetime:
    """The wall clock at the practice.

    Falls back to UTC when the practice has not said where it is, which is
    honest rather than clever: guessing from the server's own location would
    put a clinic's "open until 18:00" at whatever hour our host happens to sit
    in, and nobody could tell that from a bug.
    """
    moment = moment or datetime.now(timezone.utc)
    if not timezone_name:
        return moment.astimezone(timezone.utc)
    try:
        return moment.astimezone(ZoneInfo(timezone_name))
    except (ZoneInfoNotFoundError, ValueError):
        return moment.astimezone(timezone.utc)


class OpeningStatus:
    """Whether a practice is open, and the next thing that changes.

    `is_open` is deliberately `None` rather than `False` when the practice has
    published no grid. "We do not know" and "closed" look identical on a card
    that only has a boolean, and telling somebody a clinic is shut when nobody
    ever said so is the one mistake here that ends with a pet not being seen.
    """

    __slots__ = ("is_open", "closes_at", "opens_at", "opens_day")

    def __init__(
        self,
        is_open: bool | None,
        closes_at: str | None = None,
        opens_at: str | None = None,
        opens_day: str | None = None,
    ) -> None:
        self.is_open = is_open
        self.closes_at = closes_at
        self.opens_at = opens_at
        self.opens_day = opens_day


_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def opening_status(
    grid: dict[str, Any] | None,
    timezone_name: str | None,
    moment: datetime | None = None,
) -> OpeningStatus:
    """Open or closed right now, and when that next changes."""
    if not grid or not any(intervals_for(grid, date(2024, 1, 1) + timedelta(days=i)) for i in range(7)):
        return OpeningStatus(is_open=None)

    local = clinic_now(timezone_name, moment)
    today = local.date()
    now = local.time().replace(second=0, microsecond=0)

    for opens, closes in intervals_for(grid, today):
        if opens <= now < closes:
            return OpeningStatus(is_open=True, closes_at=f"{closes:%H:%M}")

    # Not open now, so find the next period that starts - later today first,
    # then forward through the week. A week is the whole cycle; anything not
    # found in seven days is a grid with no open periods at all.
    for offset in range(0, 8):
        day = today + timedelta(days=offset)
        for opens, _closes in intervals_for(grid, day):
            if offset == 0 and opens <= now:
                continue
            return OpeningStatus(
                is_open=False,
                opens_at=f"{opens:%H:%M}",
                opens_day=(
                    "today"
                    if offset == 0
                    else "tomorrow"
                    if offset == 1
                    else _DAY_NAMES[day.weekday()]
                ),
            )
    return OpeningStatus(is_open=False)


def normalise_grid(raw: Any) -> dict[str, list[list[str]]] | None:
    """Clean a submitted opening grid, or None if it says nothing.

    Rejected entries are dropped rather than refused, because this field is
    optional decoration on top of the free-text hours a practice already wrote.
    Failing the whole profile save over a malformed Tuesday would cost the
    practice its phone number edit as well.
    """
    if not isinstance(raw, dict):
        return None
    cleaned: dict[str, list[list[str]]] = {}
    for day in WEEKDAYS:
        periods = []
        for opens, closes in intervals_for({day: raw.get(day)}, _reference_day(day)):
            periods.append([f"{opens:%H:%M}", f"{closes:%H:%M}"])
        if periods:
            cleaned[day] = periods
    return cleaned or None


def _reference_day(day: str) -> date:
    """Any date falling on the named weekday, for reusing `intervals_for`."""
    return date(2024, 1, 1) + timedelta(days=WEEKDAYS.index(day))


# ------------------------------------------------------------------ specialty


def normalise_specialties(raw: Any) -> list[str] | None:
    """Keep the recognised slugs, in the catalogue's own order.

    Unknown values are dropped rather than stored. A specialty nothing can
    filter on is a claim on a profile that no search will ever match, which is
    worse for the practice than not making it.
    """
    if not isinstance(raw, list):
        return None
    chosen = {str(item).strip().lower() for item in raw}
    kept = [slug for slug in SPECIALTIES if slug in chosen]
    return kept or None


def specialty_labels(slugs: Iterable[str] | None) -> list[str]:
    if not slugs:
        return []
    return [SPECIALTIES[slug] for slug in slugs if slug in SPECIALTIES]

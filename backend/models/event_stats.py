from sqlmodel import SQLModel


class StatCount(SQLModel):
    """One bar of a breakdown. `label` is the enum's DISPLAY value (e.g.
    "Freshman", "Cullen College of Engineering") or, for majors, the raw
    free-text major string -- the frontend renders it verbatim and must not
    need its own copy of these enums."""
    label: str
    count: int


class EventStatsOut(SQLModel):
    """GET /events/{id}/stats -- aggregate only, no attendee is identifiable.

    See services/event_stats_services.py for why that constraint is what
    lets this endpoint be readable by any chair/E-Board member for any
    event, while the roster endpoint stays scoped through EventHost.
    """
    event_id: int
    title: str

    # Turnout
    signed_in: int
    signed_out: int
    still_signed_in: int
    guests_brought: int
    total_points_awarded: int
    average_minutes: int | None       # None when nobody scanned out
    first_time_attendees: int
    returning_attendees: int
    national_members: int

    # Breakdowns. classifications/colleges/membership are fixed-length and
    # canonically ordered (zeros included); majors is free text, so it's the
    # top few plus a collapsed tail.
    classifications: list[StatCount]
    colleges: list[StatCount]
    membership: list[StatCount]
    top_majors: list[StatCount]
    other_majors: int
    distinct_majors: int

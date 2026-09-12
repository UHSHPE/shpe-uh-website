from datetime import datetime
from sqlmodel import SQLModel, Field


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Which row of the event-tracker sheet this event came from -- the sync's
    # identity. The tracker is a fixed skeleton (rows 1..n pre-laid out by
    # date, chairs fill in a free row, nothing ever shifts), so the row number
    # is stable across any content edit -- unlike the old date|title key,
    # which forked a new identity every time someone renamed or moved an
    # event and left the stale row behind. Deliberately NOT unique: the
    # skeleton reuses slots, so a soft-deleted event and its replacement can
    # both hold row 40. NULL means "not from the sheet" (seeded, hand-added,
    # or a pre-migration past event) -- sync_events never touches those.
    sheet_row: int | None = Field(default=None, index=True)
    title: str
    description: str | None = None
    location: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    points_value: int = Field(default=0, ge=0)
    event_type: str | None = None #aka projects, professional, eboard, etc
    # Comma-joined canonical pillar keys from the tracker sheet's PILLAR(S)
    # column (see services/pillars.py) -- e.g. "community,leadership". NULL
    # means the cell was blank or held nothing recognized, which is 40 of 108
    # named rows in the live sheet and scores NO_PILLAR_POINTS. This drives
    # how many points a QR scan awards, so it is real state, not a cache.
    pillars: str | None = None
    sign_in_code: str | None = Field(default=None, index=True, unique=True)
    sign_out_code: str | None = Field(default=None, index=True, unique=True)
    # Soft delete: stamped when the event's sheet row is cleared. Nothing
    # hard-deletes an Event -- EventReminder/EventHost/EventAttendance all
    # carry a plain foreign_key="event.id" with no ondelete and no ORM
    # Relationship(), so a real delete raises ForeignKeyViolation and (since
    # sync_events commits once at the end) would roll back the whole batch.
    # Every read path filters on this via services/event_services.py.
    deleted_at: datetime | None = Field(default=None, index=True)


class EventOut(SQLModel):
    id: int
    title: str
    description: str | None
    location: str | None
    start_time: datetime
    end_time: datetime | None
    points_value: int
    event_type: str | None


class EventChairOut(SQLModel):
    """EventOut plus the sign-in/out codes and a quick roster count --
    chair/E-Board only (see require_event_host). Neither code may ever
    appear on EventOut, which is public and powers /calendar."""
    id: int
    title: str
    description: str | None
    location: str | None
    start_time: datetime
    end_time: datetime | None
    points_value: int
    event_type: str | None
    sign_in_code: str
    sign_out_code: str
    attendee_count: int


class EventAllOut(EventOut):
    """GET /events/all -- every chapter event for a chair/E-Board member.

    EventOut plus, per-event, whatever the caller is actually allowed to do
    with it. The codes are filled for events in
    attendance_services.code_scoped_events (an E-Board member gets every
    event, a chair gets what they host) and are None otherwise;
    can_view_roster tracks the narrower host_scoped_events set that gates
    GET /events/{id}/attendance. Both are carried on the payload so the page
    can hide a button rather than offer one that 403s -- the enforcement is
    still server-side on each of those endpoints.

    This is the one schema that may carry a code outside EventChairOut;
    EventOut itself must stay code-free, since it is public and powers
    /calendar (test_public_events_endpoint_never_exposes_codes pins that).
    """
    sign_in_code: str | None = None
    sign_out_code: str | None = None
    attendee_count: int = 0
    can_view_roster: bool = False

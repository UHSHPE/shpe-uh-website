from datetime import datetime
from sqlmodel import SQLModel, Field


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Sheet row is sync identity: edits preserve it; slots are reused; NULL marks non-sheet events.
    sheet_row: int | None = Field(default=None, index=True)
    title: str
    description: str | None = None
    location: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    points_value: int = Field(default=0, ge=0)
    event_type: str | None = None
    sign_in_code: str | None = Field(default=None, index=True, unique=True)
    sign_out_code: str | None = Field(default=None, index=True, unique=True)
    # Chair-created: flat 2 points whatever the host, sign-in only (sign_out_code stays NULL).
    is_committee_meeting: bool = Field(default=False)
    # Soft delete preserves FK-linked records; hard deletes would abort the sheet sync batch.
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
    """Chair/E-Board response; sign-in/out codes must stay out of public EventOut."""
    id: int
    title: str
    description: str | None
    location: str | None
    start_time: datetime
    end_time: datetime | None
    points_value: int
    event_type: str | None
    sign_in_code: str
    sign_out_code: str | None  # NULL for committee meetings
    attendee_count: int


class EventAllOut(EventOut):
    """Codes and roster access use separate scopes: code_scoped_events and host_scoped_events."""
    sign_in_code: str | None = None
    sign_out_code: str | None = None
    attendee_count: int = 0
    can_view_roster: bool = False

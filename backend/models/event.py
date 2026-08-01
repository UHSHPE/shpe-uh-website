from datetime import datetime
from sqlmodel import SQLModel, Field


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_row_id: str | None = Field(default=None, index=True, unique=True)
    title: str
    description: str | None = None
    location: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    points_value: int = Field(default=0, ge=0)
    event_type: str | None = None #aka projects, professional, eboard, etc
    sign_in_code: str | None = Field(default=None, index=True, unique=True)
    sign_out_code: str | None = Field(default=None, index=True, unique=True)


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

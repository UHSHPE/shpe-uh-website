from datetime import datetime
from sqlmodel import SQLModel, Field


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_row_id: str | None = Field(default=None, index=True)
    title: str
    description: str | None = None
    location: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    points_value: int = Field(default=0, ge=0)
    event_type: str | None = None


class EventOut(SQLModel):
    id: int
    title: str
    description: str | None
    location: str | None
    start_time: datetime
    end_time: datetime | None
    points_value: int
    event_type: str | None

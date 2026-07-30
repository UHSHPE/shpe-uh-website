from datetime import datetime
from sqlmodel import SQLModel, Field


class EventAttendance(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    event_id: int = Field(foreign_key="event.id", primary_key=True)
    signed_in_at: datetime
    signed_out_at: datetime | None = None

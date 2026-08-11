from datetime import datetime
from sqlmodel import SQLModel, Field

from services.time_services import utcnow


class EventReminder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    remind_at: datetime
    sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class EventReminderOut(SQLModel):
    id: int
    event_id: int
    remind_at: datetime
    sent_at: datetime | None

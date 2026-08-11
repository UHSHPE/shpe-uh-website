from datetime import datetime
from sqlmodel import SQLModel, Field


class Notification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_read: bool = Field(default=False)
    committee_id: int | None = Field(default=None, foreign_key="committee.id")


class NotificationOut(SQLModel):
    id: int
    body: str
    created_at: datetime
    is_read: bool
    committee_id: int | None

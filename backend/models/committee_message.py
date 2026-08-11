from datetime import datetime
from sqlmodel import SQLModel, Field


class CommitteeMessage(SQLModel, table=True):
    __tablename__ = "committee_message"

    id: int | None = Field(default=None, primary_key=True)
    committee_id: int = Field(foreign_key="committee.id")
    sender_id: int = Field(foreign_key="user.id")
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommitteeMessageCreate(SQLModel):
    body: str


class CommitteeMessageOut(SQLModel):
    id: int
    committee_id: int
    sender_name: str
    body: str
    created_at: datetime

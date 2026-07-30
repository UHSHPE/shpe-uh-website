from sqlmodel import SQLModel, Field

class EventHost(SQLModel, table=True):
    event_id: int = Field(foreign_key="event.id", primary_key=True)
    committee_id: int = Field(foreign_key="committee.id", primary_key=True, index=True)
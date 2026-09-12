"""Store membership-sheet claims independently of website accounts and orders."""

from datetime import datetime
from typing import Literal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from services.time_services import utcnow


class ImportedDues(SQLModel, table=True):
    """One payment claim per PSID and membership period."""

    __table_args__ = (UniqueConstraint("psid", "period_start", name="uq_imported_dues_psid_period"),)

    id: int | None = Field(default=None, primary_key=True)
    psid: str = Field(max_length=7)
    period_start: datetime
    verified: bool = False
    source_sheet_id: str | None = None
    source_title: str
    imported_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)


class DuesSyncResult(SQLModel):
    """Report sync outcomes without exposing member identifiers."""

    status: Literal["synced", "unconfigured", "invalid_sheet", "busy"]
    period_start: datetime | None = None
    processed: int = 0
    verified: int = 0
    skipped: int = 0
    message: str | None = None

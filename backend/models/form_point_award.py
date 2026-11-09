"""Points awarded from Google Form responses, reconciled nightly against the sheets."""

from datetime import datetime
from typing import Literal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from services.time_services import utcnow


class FormPointAward(SQLModel, table=True):
    """One award per response sheet per member; mirrors what the sheets currently say.

    member_key is "user:<id>" once matched to a verified account, else
    "psid:<psid>" / "email:<cougarnet email>" while pending. Pending rows have
    no user_id and have never touched User.points. The index row number is for
    tracing only -- it shifts whenever a chair deletes a row above it.
    """

    __table_args__ = (
        UniqueConstraint("spreadsheet_id", "gid", "member_key", name="uq_form_point_award_source_member"),
    )

    id: int | None = Field(default=None, primary_key=True)
    spreadsheet_id: str
    gid: int
    member_key: str
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    kind: str  # "sign_in" | "sign_out"
    points: int
    index_row: int
    event_name: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class FormsImportResult(SQLModel):
    """Run outcome, counts only -- no member identifiers."""

    status: Literal["synced", "unconfigured", "invalid_sheet", "busy"]
    sources_read: int = 0
    sources_failed: int = 0
    awarded: int = 0
    adjusted: int = 0
    revoked: int = 0
    pending: int = 0
    message: str | None = None

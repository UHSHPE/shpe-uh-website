from datetime import datetime
from sqlmodel import SQLModel, Field


class EventAttendance(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    event_id: int = Field(foreign_key="event.id", primary_key=True)
    # NULL when the member scanned only the sign-out code.
    signed_in_at: datetime | None = None
    signed_out_at: datetime | None = None
    # New-member claims are honor-system; names make them auditable.
    brought_new_member: bool = Field(default=False)
    new_member_name: str | None = Field(default=None)
    # GM sign-ins only; NULL means never asked, not "no".
    wore_shirt: bool | None = Field(default=None)
    # Snapshot prevents later rule changes from rewriting earned points.
    points_awarded: int = Field(default=0)


class AttendRequest(SQLModel):
    """New-member fields apply only to sign-in; sign-out scans ignore them."""
    code: str
    brought_new_member: bool = False
    new_member_name: str | None = None
    wore_shirt: bool = False


class AttendResult(SQLModel):
    action: str
    status: str
    event_id: int
    event_title: str
    points_awarded: int
    total_points: int
    signed_in_at: datetime | None = None
    signed_out_at: datetime | None = None


class CodePreviewOut(SQLModel):
    """Public preview is read-only and must never expose sign-in/out codes."""
    action: str
    event_id: int
    title: str
    location: str | None
    start_time: datetime
    end_time: datetime | None
    event_type: str | None
    points_value: int
    state: str
    asks_shirt: bool = False
    # Timestamp fields are limited to the authenticated caller's own attendance.
    signed_in_at: datetime | None = None
    signed_out_at: datetime | None = None


class AttendanceOut(SQLModel):
    user_id: int
    first_name: str
    last_name: str
    personal_email: str
    signed_in_at: datetime | None
    signed_out_at: datetime | None
    brought_new_member: bool
    new_member_name: str | None
    wore_shirt: bool | None
    points_awarded: int

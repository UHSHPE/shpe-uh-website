from datetime import datetime
from sqlmodel import SQLModel, Field


class EventAttendance(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    event_id: int = Field(foreign_key="event.id", primary_key=True)
    signed_in_at: datetime
    signed_out_at: datetime | None = None
    # "Did you bring a new member?" -- asked only on the sign-in scan.
    # Honor-system: capturing the name makes it auditable, not enforced.
    brought_new_member: bool = Field(default=False)
    new_member_name: str | None = Field(default=None)
    # Audit trail of what this member actually earned for this event
    # (sign-in points [+ new-member bonus], topped up by sign-out points when
    # they sign out) -- a later change to the points rule must not rewrite
    # history.
    points_awarded: int = Field(default=0)


class AttendRequest(SQLModel):
    """POST /events/attend body. brought_new_member/new_member_name only
    matter on a sign-in scan (see attendance_services.record_sign_in) --
    harmless if sent on a sign-out scan, just ignored."""
    code: str
    brought_new_member: bool = False
    new_member_name: str | None = None


class AttendResult(SQLModel):
    action: str            # "sign_in" | "sign_out"
    status: str             # "recorded" | "already_recorded"
    event_id: int
    event_title: str
    points_awarded: int     # points earned by THIS scan; 0 when already_recorded
    total_points: int       # the member's new running total


class AttendanceOut(SQLModel):
    """One row of a chair's attendance roster for GET /events/{id}/attendance."""
    user_id: int
    first_name: str
    last_name: str
    personal_email: str
    signed_in_at: datetime
    signed_out_at: datetime | None
    brought_new_member: bool
    new_member_name: str | None
    points_awarded: int

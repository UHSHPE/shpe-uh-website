from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlmodel import Session, select

from models.event import Event
from models.event_reminder import EventReminder
from models.user.user import User
from services.email_services import send_email
from services.time_services import utcnow

LOCAL_TZ = ZoneInfo("America/Chicago")


def compute_remind_at(start_time: datetime, now: datetime | None = None) -> datetime:
    """Pick when to send the reminder: 24h before the event, falling back to
    1h before (or right now) when the event is closer than that."""
    now = now or utcnow()

    if start_time <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event has already started",
        )

    for offset in (timedelta(hours=24), timedelta(hours=1)):
        remind_at = start_time - offset
        if remind_at >= now:
            return remind_at

    return now


def _format_local_time(start_time: datetime) -> str:
    local = start_time.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
    return local.strftime("%A, %B %-d at %-I:%M %p")


def send_due_reminders(session: Session, now: datetime | None = None) -> int:
    """Email every unsent reminder whose remind_at has passed. Reminders whose
    email fails to send stay unsent so the next run retries them."""
    now = now or utcnow()

    stmt = (
        select(EventReminder, Event, User)
        .where(
            EventReminder.sent_at == None,  # noqa: E711
            EventReminder.remind_at <= now,
            EventReminder.event_id == Event.id,
            EventReminder.user_id == User.id,
        )
    )

    sent_count = 0
    for reminder, event, user in session.exec(stmt).all():
        subject = f"Reminder: {event.title}"
        lines = [
            f"Hi {user.first_name},",
            "",
            f"{event.title} is coming up on {_format_local_time(event.start_time)}.",
        ]
        if event.location:
            lines.append(f"Location: {event.location}")
        if event.description:
            lines.append(f"\n{event.description}")
        lines += ["", "See you there!", "— SHPE UH"]

        if send_email(user.personal_email, subject, "\n".join(lines)):
            reminder.sent_at = now
            session.add(reminder)
            sent_count += 1

    session.commit()
    return sent_count

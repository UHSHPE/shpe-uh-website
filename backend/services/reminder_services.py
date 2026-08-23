from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlmodel import Session, select

from models.event import Event
from models.event_reminder import EventReminder
from models.user.user import User
from services.email_services import send_email
from services.event_services import not_deleted
from services.time_services import utcnow

LOCAL_TZ = ZoneInfo("America/Chicago")


def remind_at_for(start_time: datetime, now: datetime | None = None) -> datetime | None:
    """When to send the reminder: 24h before the event, falling back to 1h
    before (or right now) when the event is closer than that. None if the
    event has already started.

    Split out of compute_remind_at so the sheet sync can call it without the
    HTTPException -- raising a 400 out of a background loop would abort the
    sync, and "already started" is a normal thing to encounter there.
    """
    now = now or utcnow()

    if start_time <= now:
        return None

    for offset in (timedelta(hours=24), timedelta(hours=1)):
        remind_at = start_time - offset
        if remind_at >= now:
            return remind_at

    return now


def compute_remind_at(start_time: datetime, now: datetime | None = None) -> datetime:
    """remind_at_for() for request handlers: 400 instead of None."""
    remind_at = remind_at_for(start_time, now)
    if remind_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event has already started",
        )
    return remind_at


def reschedule_reminders(session: Session, event_id: int, start_time: datetime,
                         now: datetime | None = None) -> None:
    """Move an event's unsent reminders to match a new start_time.

    remind_at is computed once when the member sets the reminder and is never
    revisited, so an event whose time is edited in the tracker sheet would
    otherwise keep firing on the old schedule -- the email body reads
    event.start_time live and would show the corrected time, making it land as
    an unexplained early or late nudge. Reminders for an event that has been
    moved into the past are dropped: there is nothing left to remind anyone
    about. Caller commits.
    """
    now = now or utcnow()
    stmt = select(EventReminder).where(
        EventReminder.event_id == event_id,
        EventReminder.sent_at == None,  # noqa: E711
    )
    for reminder in session.exec(stmt).all():
        remind_at = remind_at_for(start_time, now)
        if remind_at is None:
            session.delete(reminder)
        else:
            reminder.remind_at = remind_at
            session.add(reminder)


def _format_local_time(start_time: datetime) -> str:
    local = start_time.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
    return local.strftime("%A, %B %-d at %-I:%M %p")


def send_due_reminders(session: Session, now: datetime | None = None) -> int:
    """Email every unsent reminder whose remind_at has passed. Reminders whose
    email fails to send stay unsent so the next run retries them."""
    now = now or utcnow()

    # Joined through live_events() so a soft-deleted event never generates
    # mail -- an event pulled from the tracker sheet is off the calendar, and
    # reminding a member to attend it would be worse than silence.
    stmt = (
        select(EventReminder, Event, User)
        .where(
            not_deleted(),
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

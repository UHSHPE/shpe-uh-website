import pytest
from datetime import datetime, timedelta

from fastapi import HTTPException

from models.event_reminder import EventReminder
from services import reminder_services
from services.reminder_services import compute_remind_at, send_due_reminders
from services.time_services import utcnow
from tests.conftest import make_event, make_user


def test_canary():
    assert True


# --- compute_remind_at ---

def test_remind_at_is_24_hours_before_for_far_events():
    now = datetime(2026, 6, 1, 12, 0)
    start = now + timedelta(days=7)
    assert compute_remind_at(start, now=now) == start - timedelta(hours=24)

def test_remind_at_is_1_hour_before_for_events_within_24_hours():
    now = datetime(2026, 6, 1, 12, 0)
    start = now + timedelta(hours=5)
    assert compute_remind_at(start, now=now) == start - timedelta(hours=1)

def test_remind_at_is_now_for_events_within_1_hour():
    now = datetime(2026, 6, 1, 12, 0)
    start = now + timedelta(minutes=30)
    assert compute_remind_at(start, now=now) == now

def test_remind_at_for_already_started_event_raises_400():
    now = datetime(2026, 6, 1, 12, 0)
    start = now - timedelta(minutes=1)

    with pytest.raises(HTTPException) as exc_info:
        compute_remind_at(start, now=now)

    assert exc_info.value.status_code == 400


# --- send_due_reminders ---

@pytest.fixture
def sent_emails(monkeypatch):
    sent = []

    def fake_send_email(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr(reminder_services, "send_email", fake_send_email)
    return sent


def _add_reminder(session, user, event, *, remind_in=timedelta(minutes=-1), sent_at=None):
    reminder = EventReminder(
        user_id=user.id,
        event_id=event.id,
        remind_at=utcnow() + remind_in,
        sent_at=sent_at,
    )
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder


def test_due_reminder_emails_user_and_marks_sent(session, sent_emails):
    user = make_user(session)
    event = make_event(session, title="Resume Workshop", start_in=timedelta(hours=12))
    reminder = _add_reminder(session, user, event)

    count = send_due_reminders(session)

    assert count == 1
    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == user.personal_email
    assert "Resume Workshop" in sent_emails[0]["subject"]
    assert "Resume Workshop" in sent_emails[0]["body"]

    session.refresh(reminder)
    assert reminder.sent_at is not None

def test_reminder_email_body_includes_location(session, sent_emails):
    user = make_user(session)
    event = make_event(session, location="PGH 232", start_in=timedelta(hours=12))
    _add_reminder(session, user, event)

    send_due_reminders(session)

    assert "PGH 232" in sent_emails[0]["body"]

def test_reminder_not_due_yet_is_not_sent(session, sent_emails):
    user = make_user(session)
    event = make_event(session)
    reminder = _add_reminder(session, user, event, remind_in=timedelta(hours=2))

    count = send_due_reminders(session)

    assert count == 0
    assert sent_emails == []

    session.refresh(reminder)
    assert reminder.sent_at is None

def test_already_sent_reminder_is_not_resent(session, sent_emails):
    user = make_user(session)
    event = make_event(session)
    _add_reminder(session, user, event, sent_at=utcnow())

    count = send_due_reminders(session)

    assert count == 0
    assert sent_emails == []

def test_failed_send_leaves_reminder_unsent_for_retry(session, monkeypatch):
    monkeypatch.setattr(reminder_services, "send_email", lambda to, subject, body: False)
    user = make_user(session)
    event = make_event(session)
    reminder = _add_reminder(session, user, event)

    count = send_due_reminders(session)

    assert count == 0
    session.refresh(reminder)
    assert reminder.sent_at is None

def test_sends_one_email_per_due_reminder(session, sent_emails):
    user_a = make_user(session)
    user_b = make_user(
        session,
        cougarnet_email="other@cougarnet.uh.edu",
        personal_email="other@gmail.com",
        psid="7654321",
    )
    event = make_event(session)
    _add_reminder(session, user_a, event)
    _add_reminder(session, user_b, event)

    count = send_due_reminders(session)

    assert count == 2
    assert {email["to"] for email in sent_emails} == {"test@gmail.com", "other@gmail.com"}

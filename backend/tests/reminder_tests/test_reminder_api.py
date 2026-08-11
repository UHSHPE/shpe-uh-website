from datetime import timedelta

from sqlmodel import select

from models.event_reminder import EventReminder
from services.time_services import utcnow
from tests.conftest import make_event, make_user


def test_canary():
    assert True


# --- POST /events/{id}/remind ---

def test_set_reminder_returns_created_reminder(client, session, user):
    event = make_event(session)

    res = client.post(f"/events/{event.id}/remind")

    assert res.status_code == 201
    data = res.json()
    assert data["event_id"] == event.id
    assert data["sent_at"] is None
    assert data["remind_at"] == (event.start_time - timedelta(hours=24)).isoformat()

def test_set_reminder_persists_reminder_for_user(client, session, user):
    event = make_event(session)

    client.post(f"/events/{event.id}/remind")

    session.expire_all()
    reminder = session.exec(select(EventReminder)).one()
    assert reminder.user_id == user.id
    assert reminder.event_id == event.id
    assert reminder.sent_at is None

def test_set_reminder_for_unknown_event_returns_404(client):
    res = client.post("/events/9999/remind")
    assert res.status_code == 404

def test_set_reminder_twice_returns_409(client, session):
    event = make_event(session)

    first = client.post(f"/events/{event.id}/remind")
    second = client.post(f"/events/{event.id}/remind")

    assert first.status_code == 201
    assert second.status_code == 409

def test_set_reminder_for_started_event_returns_400(client, session):
    event = make_event(session, start_in=timedelta(hours=-1))

    res = client.post(f"/events/{event.id}/remind")

    assert res.status_code == 400

def test_set_reminder_requires_auth(unauth_client, session):
    event = make_event(session)

    res = unauth_client.post(f"/events/{event.id}/remind")

    assert res.status_code == 401


# --- DELETE /events/{id}/remind ---

def test_cancel_reminder_deletes_it(client, session):
    event = make_event(session)
    client.post(f"/events/{event.id}/remind")

    res = client.delete(f"/events/{event.id}/remind")

    assert res.status_code == 200
    session.expire_all()
    assert session.exec(select(EventReminder)).all() == []

def test_cancel_without_reminder_returns_404(client, session):
    event = make_event(session)

    res = client.delete(f"/events/{event.id}/remind")

    assert res.status_code == 404

def test_cancel_requires_auth(unauth_client, session):
    event = make_event(session)

    res = unauth_client.delete(f"/events/{event.id}/remind")

    assert res.status_code == 401


# --- GET /events/reminders/me ---

def test_my_reminders_lists_only_current_users_reminders(client, session, user):
    my_event = make_event(session, title="My Event")
    other_event = make_event(session, title="Other Event")
    other_user = make_user(
        session,
        cougarnet_email="other@cougarnet.uh.edu",
        personal_email="other@gmail.com",
        psid="7654321",
    )
    client.post(f"/events/{my_event.id}/remind")
    session.add(EventReminder(
        user_id=other_user.id,
        event_id=other_event.id,
        remind_at=utcnow(),
    ))
    session.commit()

    res = client.get("/events/reminders/me")

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["event_id"] == my_event.id

def test_my_reminders_excludes_already_sent(client, session, user):
    event = make_event(session)
    session.add(EventReminder(
        user_id=user.id,
        event_id=event.id,
        remind_at=utcnow() - timedelta(hours=1),
        sent_at=utcnow(),
    ))
    session.commit()

    res = client.get("/events/reminders/me")

    assert res.status_code == 200
    assert res.json() == []

def test_my_reminders_requires_auth(unauth_client):
    res = unauth_client.get("/events/reminders/me")
    assert res.status_code == 401

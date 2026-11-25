# API tests for chair-created committee meetings: POST /events/meetings and
# GET /events/meetings. The chair sends only a start time; the committee comes
# from their role, so the body never names one.

from datetime import timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from database import get_session
from models.committee import CommitteeMembership
from models.event import Event
from models.event_host import EventHost
from models.user.user_enums import Role
from services.dependencies import get_current_user
from services.event_tracker_services import SHEET_TZ
from services.time_services import utcnow
from tests.conftest import make_event, make_user
from tests.event_tests.conftest import link_host, make_committee, make_meeting


def central_7pm_next_week():
    """(ISO string with offset as the browser sends it, expected naive-UTC start_time)."""
    local = (
        (utcnow() + timedelta(days=7))
        .replace(tzinfo=timezone.utc)
        .astimezone(SHEET_TZ)
        .replace(hour=19, minute=0, second=0, microsecond=0)
    )
    return local.isoformat(), local.astimezone(timezone.utc).replace(tzinfo=None)


def meetings_in_db(session):
    return session.exec(select(Event).where(Event.is_committee_meeting == True)).all()  # noqa: E712


# --- POST /events/meetings ---

def test_chair_creates_a_meeting_for_their_committee(chair_client, session, committee):
    start, expected_start = central_7pm_next_week()

    resp = chair_client.post("/events/meetings", json={"start_time": start})

    assert resp.status_code == 201
    [meeting] = meetings_in_db(session)
    assert meeting.title == "Social Meeting"
    assert meeting.start_time == expected_start
    assert meeting.end_time is None
    assert meeting.sheet_row is None
    assert meeting.event_type == "social"
    assert meeting.sign_in_code
    assert meeting.sign_out_code is None
    hosts = session.exec(select(EventHost).where(EventHost.event_id == meeting.id)).all()
    assert [h.committee_id for h in hosts] == [committee.id]


def test_a_committee_id_in_the_body_is_ignored(chair_client, session, committee):
    outreach = make_committee(session, name="Outreach", chair_role=Role.outreach_chair)
    start, _ = central_7pm_next_week()

    resp = chair_client.post("/events/meetings", json={"start_time": start, "committee_id": outreach.id})

    assert resp.status_code == 201
    [meeting] = meetings_in_db(session)
    hosts = session.exec(select(EventHost).where(EventHost.event_id == meeting.id)).all()
    assert [h.committee_id for h in hosts] == [committee.id]


def test_a_regular_member_cannot_create_a_meeting(client, session):
    start, _ = central_7pm_next_week()

    resp = client.post("/events/meetings", json={"start_time": start})

    assert resp.status_code == 403
    assert meetings_in_db(session) == []


def test_a_stale_chair_row_without_the_chair_role_cannot_create(session, committee):
    # Access follows the live role, so a demoted chair loses it immediately.
    from main import app

    former = make_user(
        session,
        cougarnet_email="former@cougarnet.uh.edu",
        personal_email="former@gmail.com",
        psid="3333333",
        role=Role.member,
    )
    session.add(CommitteeMembership(user_id=former.id, committee_id=committee.id, status=True, is_chair=True))
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: former
    try:
        start, _ = central_7pm_next_week()
        resp = TestClient(app).post("/events/meetings", json={"start_time": start})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert meetings_in_db(session) == []


@pytest.mark.parametrize("body", [
    {},
    {"start_time": "tomorrow"},
    {"start_time": "2026-12-03"},   # a date with no time
    {"start_time": (utcnow() - timedelta(hours=1)).replace(tzinfo=timezone.utc).isoformat()},   # in the past
])
def test_bad_start_time_is_rejected(chair_client, session, body):
    resp = chair_client.post("/events/meetings", json=body)

    assert resp.status_code == 422
    assert meetings_in_db(session) == []


# --- GET /events/meetings ---

def test_listing_shows_only_this_committees_live_meetings(chair_client, session, committee):
    outreach = make_committee(session, name="Outreach", chair_role=Role.outreach_chair)
    mine = make_meeting(session, committee)
    make_meeting(session, committee, deleted_at=utcnow())
    make_meeting(session, outreach)
    regular = make_event(session, title="Mixer", event_type="social")
    link_host(session, regular, committee)

    resp = chair_client.get("/events/meetings")

    assert resp.status_code == 200
    assert [m["id"] for m in resp.json()] == [mine.id]


def test_a_regular_member_cannot_list_meetings(client):
    assert client.get("/events/meetings").status_code == 403

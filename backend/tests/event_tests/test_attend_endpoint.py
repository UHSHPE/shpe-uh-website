# API tests for POST /events/attend. Uses the `client`/`user` fixtures from
# tests/conftest.py (an ordinary signed-in member, role=Role.member).
#
# make_event()'s default start_in=timedelta(days=7) puts the event well
# outside the 60-minute not-started grace window, so every test here that
# expects a successful scan passes start_in=timedelta(minutes=-5) (already
# open, not expired since there's no end_time) instead of relying on the
# fixture default.

from datetime import timedelta

import pytest

from models.event_attendance import EventAttendance
from services.time_services import utcnow
from tests.conftest import make_event

STARTED = timedelta(minutes=-5)


def test_sign_in_awards_points_and_creates_row(client, session, user):
    event = make_event(session, start_in=STARTED, sign_in_code="in-1", sign_out_code="out-1")

    resp = client.post("/events/attend", json={"code": "in-1"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "sign_in"
    assert body["status"] == "recorded"
    assert body["points_awarded"] == 2
    assert body["total_points"] == 2
    assert body["event_id"] == event.id
    assert body["signed_in_at"] is not None
    assert body["signed_out_at"] is None


def test_double_sign_in_returns_200_already_recorded(client, session):
    make_event(session, start_in=STARTED, sign_in_code="in-2", sign_out_code="out-2")

    first = client.post("/events/attend", json={"code": "in-2"})
    second = client.post("/events/attend", json={"code": "in-2"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "already_recorded"
    assert second.json()["points_awarded"] == 0
    # Points must not move on the repeat scan.
    assert second.json()["total_points"] == first.json()["total_points"]
    # The original check-in time is still reported so the "Already checked
    # in" screen can show it.
    assert second.json()["signed_in_at"] == first.json()["signed_in_at"]


def test_sign_out_awards_points_independently(client, session):
    make_event(session, start_in=STARTED, sign_in_code="in-3", sign_out_code="out-3")
    client.post("/events/attend", json={"code": "in-3"})

    resp = client.post("/events/attend", json={"code": "out-3"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "sign_out"
    assert body["status"] == "recorded"
    assert body["points_awarded"] == 2
    assert body["total_points"] == 4   # 2 sign-in + 2 sign-out
    assert body["signed_in_at"] is not None
    assert body["signed_out_at"] is not None


def test_sign_out_without_sign_in_is_recorded(client, session):
    make_event(session, start_in=STARTED, sign_in_code="in-4", sign_out_code="out-4")

    resp = client.post("/events/attend", json={"code": "out-4"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "sign_out"
    assert body["status"] == "recorded"
    assert body["points_awarded"] == 2
    assert body["total_points"] == 2
    assert body["signed_in_at"] is None
    assert body["signed_out_at"] is not None


def test_late_gm_sign_in_after_sign_out_is_recorded(client, session):
    make_event(
        session,
        start_in=STARTED,
        title="1ST GM LYB",
        event_type="eboard",
        sign_in_code="in-late",
        sign_out_code="out-late",
    )
    client.post("/events/attend", json={"code": "out-late"})

    resp = client.post("/events/attend", json={"code": "in-late", "wore_shirt": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "sign_in"
    assert body["status"] == "recorded"
    assert body["points_awarded"] == 5   # 3 GM sign-in + 2 shirt
    assert body["total_points"] == 7     # + 2 from the earlier sign-out
    assert body["signed_in_at"] is not None
    assert body["signed_out_at"] is not None


def test_double_sign_out_returns_200_already_recorded(client, session):
    make_event(session, start_in=STARTED, sign_in_code="in-5", sign_out_code="out-5")
    client.post("/events/attend", json={"code": "in-5"})
    client.post("/events/attend", json={"code": "out-5"})

    resp = client.post("/events/attend", json={"code": "out-5"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "already_recorded"
    assert resp.json()["points_awarded"] == 0


def test_bad_code_returns_generic_404(client):
    resp = client.post("/events/attend", json={"code": "not-a-real-code"})
    assert resp.status_code == 404


def test_expired_code_returns_410(client, session):
    past_event = make_event(
        session,
        start_in=timedelta(days=-2),
        end_time=utcnow() - timedelta(days=1),
        sign_in_code="in-expired",
        sign_out_code="out-expired",
    )

    resp = client.post("/events/attend", json={"code": "in-expired"})

    assert resp.status_code == 410
    assert past_event.sign_in_code == "in-expired"   # sanity: real event, real code


def test_new_member_bonus_is_captured_and_awarded(client, session):
    make_event(session, start_in=STARTED, sign_in_code="in-6", sign_out_code="out-6")

    resp = client.post("/events/attend", json={
        "code": "in-6",
        "brought_new_member": True,
        "new_member_name": "Jane Doe",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["points_awarded"] == 4   # 2 base + 2 bonus
    assert body["total_points"] == 4


@pytest.mark.parametrize("name", [None, "", "   "])
def test_new_member_without_a_name_is_rejected(client, session, user, name):
    event = make_event(session, start_in=STARTED, sign_in_code="in-noname")
    payload = {"code": "in-noname", "brought_new_member": True}
    if name is not None:
        payload["new_member_name"] = name

    resp = client.post("/events/attend", json=payload)

    assert resp.status_code == 422
    assert session.get(EventAttendance, (user.id, event.id)) is None
    session.refresh(user)
    assert user.points == 0


def test_gbm_sign_in_awards_three_points(client, session):
    make_event(
        session,
        start_in=STARTED,
        title="1ST GM LYB",
        event_type="eboard",
        sign_in_code="in-gbm",
        sign_out_code="out-gbm",
    )

    resp = client.post("/events/attend", json={"code": "in-gbm"})

    assert resp.status_code == 200
    assert resp.json()["points_awarded"] == 3


def test_gm_sign_in_awards_shirt_and_new_member_bonuses(client, session, user):
    event = make_event(
        session,
        start_in=STARTED,
        end_time=utcnow() + timedelta(hours=1),
        title="1ST GM LYB",
        event_type="eboard",
        sign_in_code="in-gm-shirt",
    )

    resp = client.post("/events/attend", json={
        "code": "in-gm-shirt",
        "wore_shirt": True,
        "brought_new_member": True,
        "new_member_name": "Jane Doe",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["points_awarded"] == 7
    assert body["total_points"] == 7
    attendance = session.get(EventAttendance, (user.id, event.id))
    assert attendance.wore_shirt is True
    assert attendance.brought_new_member is True
    assert attendance.new_member_name == "Jane Doe"


def test_non_gm_sign_in_leaves_wore_shirt_null(client, session, user):
    event = make_event(
        session,
        start_in=STARTED,
        end_time=utcnow() + timedelta(hours=1),
        title="Resume Workshop",
        event_type="professional",
        sign_in_code="in-workshop",
    )

    resp = client.post("/events/attend", json={"code": "in-workshop"})

    assert resp.status_code == 200
    attendance = session.get(EventAttendance, (user.id, event.id))
    assert attendance.wore_shirt is None


def test_check_in_before_grace_window_returns_425(client, session):
    make_event(
        session,
        start_in=timedelta(minutes=90),
        sign_in_code="in-early",
        sign_out_code="out-early",
    )

    resp = client.post("/events/attend", json={"code": "in-early"})

    assert resp.status_code == 425


def test_check_in_inside_grace_window_is_allowed(client, session):
    # The boundary is the whole point of the rule -- 59 minutes out is
    # inside the 60-minute grace window and must succeed.
    make_event(
        session,
        start_in=timedelta(minutes=59),
        sign_in_code="in-almost",
        sign_out_code="out-almost",
    )

    resp = client.post("/events/attend", json={"code": "in-almost"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "recorded"


def test_public_events_endpoint_never_exposes_codes(unauth_client, session):
    make_event(session, sign_in_code="secret-in", sign_out_code="secret-out")

    resp = unauth_client.get("/events")

    assert resp.status_code == 200
    body_text = resp.text
    assert "sign_in_code" not in body_text
    assert "sign_out_code" not in body_text
    assert "secret-in" not in body_text
    assert "secret-out" not in body_text


def test_public_events_points_value_reflects_the_rule(unauth_client, session):
    make_event(session, title="1ST GM LYB", event_type="eboard", points_value=0)

    resp = unauth_client.get("/events")

    assert resp.status_code == 200
    [event] = [e for e in resp.json() if e["title"] == "1ST GM LYB"]
    assert event["points_value"] == 3   # sign-in value for a GBM, not the raw 0 column

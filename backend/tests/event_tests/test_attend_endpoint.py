# API tests for POST /events/attend. Uses the `client`/`user` fixtures from
# tests/conftest.py (an ordinary signed-in member, role=Role.member).

from datetime import timedelta

from services.time_services import utcnow
from tests.conftest import make_event


def test_sign_in_awards_points_and_creates_row(client, session, user):
    event = make_event(session, sign_in_code="in-1", sign_out_code="out-1")

    resp = client.post("/events/attend", json={"code": "in-1"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "sign_in"
    assert body["status"] == "recorded"
    assert body["points_awarded"] == 2
    assert body["total_points"] == 2
    assert body["event_id"] == event.id


def test_double_sign_in_returns_200_already_recorded(client, session):
    make_event(session, sign_in_code="in-2", sign_out_code="out-2")

    first = client.post("/events/attend", json={"code": "in-2"})
    second = client.post("/events/attend", json={"code": "in-2"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "already_recorded"
    assert second.json()["points_awarded"] == 0
    # Points must not move on the repeat scan.
    assert second.json()["total_points"] == first.json()["total_points"]


def test_sign_out_awards_points_independently(client, session):
    make_event(session, sign_in_code="in-3", sign_out_code="out-3")
    client.post("/events/attend", json={"code": "in-3"})

    resp = client.post("/events/attend", json={"code": "out-3"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "sign_out"
    assert body["status"] == "recorded"
    assert body["points_awarded"] == 2
    assert body["total_points"] == 4   # 2 sign-in + 2 sign-out


def test_sign_out_before_sign_in_is_rejected(client, session):
    make_event(session, sign_in_code="in-4", sign_out_code="out-4")

    resp = client.post("/events/attend", json={"code": "out-4"})

    assert resp.status_code == 400


def test_double_sign_out_returns_200_already_recorded(client, session):
    make_event(session, sign_in_code="in-5", sign_out_code="out-5")
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
    make_event(session, sign_in_code="in-6", sign_out_code="out-6")

    resp = client.post("/events/attend", json={
        "code": "in-6",
        "brought_new_member": True,
        "new_member_name": "Jane Doe",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["points_awarded"] == 4   # 2 base + 2 bonus
    assert body["total_points"] == 4


def test_gbm_sign_in_awards_three_points(client, session):
    make_event(
        session,
        title="1ST GM LYB",
        event_type="eboard",
        sign_in_code="in-gbm",
        sign_out_code="out-gbm",
    )

    resp = client.post("/events/attend", json={"code": "in-gbm"})

    assert resp.status_code == 200
    assert resp.json()["points_awarded"] == 3


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

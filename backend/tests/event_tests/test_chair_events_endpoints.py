# API tests for GET /events/mine, GET /events/all,
# GET /events/{id}/attendance, and GET /events/{id}/scan-count. Uses the
# chair_client fixture from tests/event_tests/conftest.py (a
# Role.social_chair user chairing the "Social" committee).

from models.user.user_enums import Role
from services.attendance_services import record_sign_in, record_sign_out
from tests.conftest import make_event, make_user
from tests.event_tests.conftest import link_host, make_committee


def test_my_events_returns_only_hosted_events_with_codes(chair_client, session, committee):
    other = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    mine = make_event(session, title="Mixer")
    not_mine = make_event(session, title="Robotics Night")
    link_host(session, mine, committee)
    link_host(session, not_mine, other)

    resp = chair_client.get("/events/mine")

    assert resp.status_code == 200
    body = resp.json()
    assert [e["id"] for e in body] == [mine.id]
    assert body[0]["sign_in_code"]
    assert body[0]["sign_out_code"]
    assert body[0]["attendee_count"] == 0


def test_my_events_mints_codes_on_first_view(chair_client, session, committee):
    event = make_event(session, sign_in_code=None, sign_out_code=None)
    link_host(session, event, committee)

    chair_client.get("/events/mine")

    session.refresh(event)
    assert event.sign_in_code
    assert event.sign_out_code


def test_chair_cannot_see_another_committees_codes(chair_client, session, committee):
    other = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    other_event = make_event(session, title="Robotics Night")
    link_host(session, other_event, other)

    resp = chair_client.get("/events/mine")

    assert resp.status_code == 200
    assert resp.json() == []


def test_all_events_lists_every_event_without_codes(chair_client, session, committee):
    other = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    mine = make_event(session, title="Mixer")
    not_mine = make_event(session, title="Robotics Night")
    link_host(session, mine, committee)
    link_host(session, not_mine, other)

    resp = chair_client.get("/events/all")

    assert resp.status_code == 200
    ids = {e["id"] for e in resp.json()}
    assert ids == {mine.id, not_mine.id}
    assert "sign_in_code" not in resp.text
    assert "sign_out_code" not in resp.text


def test_regular_member_cannot_reach_mine_or_all(client):
    assert client.get("/events/mine").status_code == 403
    assert client.get("/events/all").status_code == 403


def test_attendance_roster_for_a_hosted_event(chair_client, session, committee):
    event = make_event(session)
    link_host(session, event, committee)
    attendee = make_user(
        session,
        cougarnet_email="attendee@cougarnet.uh.edu",
        personal_email="attendee@gmail.com",
        psid="4444444",
    )
    record_sign_in(session, attendee, event, brought_new_member=True, new_member_name="Jane Doe")

    resp = chair_client.get(f"/events/{event.id}/attendance")

    assert resp.status_code == 200
    [row] = resp.json()
    assert row["user_id"] == attendee.id
    assert row["brought_new_member"] is True
    assert row["new_member_name"] == "Jane Doe"


def test_attendance_roster_403s_for_another_committees_event(chair_client, session):
    other = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    other_event = make_event(session, title="Robotics Night")
    link_host(session, other_event, other)

    resp = chair_client.get(f"/events/{other_event.id}/attendance")

    assert resp.status_code == 403


def test_attendance_roster_404s_for_unknown_event(chair_client):
    resp = chair_client.get("/events/999999/attendance")
    assert resp.status_code == 404


def test_president_sees_every_event_on_mine(president_client, session):
    committee = make_committee(session, name="Social", chair_role=Role.social_chair)
    event = make_event(session, title="Mixer")
    link_host(session, event, committee)

    resp = president_client.get("/events/mine")

    assert resp.status_code == 200
    assert [e["id"] for e in resp.json()] == [event.id]


def test_scan_count_reflects_mixed_sign_in_and_sign_out_state(chair_client, session, committee):
    event = make_event(session)
    link_host(session, event, committee)
    signed_in_only = make_user(
        session,
        cougarnet_email="in-only@cougarnet.uh.edu",
        personal_email="in-only@gmail.com",
        psid="1111111",
    )
    signed_out_too = make_user(
        session,
        cougarnet_email="in-and-out@cougarnet.uh.edu",
        personal_email="in-and-out@gmail.com",
        psid="2222222",
    )
    record_sign_in(session, signed_in_only, event)
    record_sign_in(session, signed_out_too, event)
    record_sign_out(session, signed_out_too, event)

    resp = chair_client.get(f"/events/{event.id}/scan-count")

    assert resp.status_code == 200
    assert resp.json() == {"signed_in": 2, "signed_out": 1}


def test_scan_count_403s_for_another_committees_event(chair_client, session):
    other = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    other_event = make_event(session, title="Robotics Night")
    link_host(session, other_event, other)

    resp = chair_client.get(f"/events/{other_event.id}/scan-count")

    assert resp.status_code == 403


def test_scan_count_404s_for_unknown_event(chair_client):
    resp = chair_client.get("/events/999999/scan-count")
    assert resp.status_code == 404

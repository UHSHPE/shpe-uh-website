# API tests for GET /events/mine, GET /events/all,
# GET /events/{id}/attendance, and GET /events/{id}/scan-count. Uses the
# chair_client fixture from tests/event_tests/conftest.py (a
# Role.social_chair user chairing the "Social" committee).

from datetime import timedelta

from models.user.user_enums import Role
from services.attendance_services import record_sign_in, record_sign_out
from services.time_services import utcnow
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


def test_my_events_reads_existing_codes_without_writes(chair_client, session, committee, monkeypatch):
    event = make_event(session, sign_in_code="existing-in", sign_out_code="existing-out")
    link_host(session, event, committee)

    def unexpected_commit():
        raise AssertionError("Reading hosted events must not commit")

    monkeypatch.setattr(session, "commit", unexpected_commit)
    response = chair_client.get("/events/mine")

    assert response.status_code == 200
    assert response.json()[0]["sign_in_code"] == "existing-in"
    assert response.json()[0]["sign_out_code"] == "existing-out"
    session.refresh(event)
    assert (event.sign_in_code, event.sign_out_code) == ("existing-in", "existing-out")


def test_chair_cannot_see_another_committees_codes(chair_client, session, committee):
    other = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    other_event = make_event(session, title="Robotics Night")
    link_host(session, other_event, other)

    resp = chair_client.get("/events/mine")

    assert resp.status_code == 200
    assert resp.json() == []


def test_all_events_gives_a_chair_codes_only_for_what_they_host(chair_client, session, committee):
    # A chair sees the whole calendar, but /events/all hands out a code only
    # where /events/mine already would -- so All Events adds visibility, not
    # access. can_view_roster mirrors the same split.
    other = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    mine = make_event(session, title="Mixer")
    not_mine = make_event(session, title="Robotics Night")
    link_host(session, mine, committee)
    link_host(session, not_mine, other)

    resp = chair_client.get("/events/all")

    assert resp.status_code == 200
    by_id = {e["id"]: e for e in resp.json()}
    assert set(by_id) == {mine.id, not_mine.id}

    assert by_id[mine.id]["sign_in_code"]
    assert by_id[mine.id]["sign_out_code"]
    assert by_id[mine.id]["can_view_roster"] is True

    assert by_id[not_mine.id]["sign_in_code"] is None
    assert by_id[not_mine.id]["sign_out_code"] is None
    assert by_id[not_mine.id]["can_view_roster"] is False


def test_all_events_gives_an_officer_every_events_codes(officer_client, session):
    # The widening the Events page is built on: an E-Board member covering
    # the door at an event they didn't organize can still present the QR.
    social = make_committee(session, name="Social", chair_role=Role.social_chair)
    event = make_event(session, title="Mixer")
    link_host(session, event, social)

    body = officer_client.get("/events/all").json()

    assert [e["id"] for e in body] == [event.id]
    assert body[0]["sign_in_code"]
    assert body[0]["sign_out_code"]


def test_an_officers_code_access_does_not_extend_to_the_roster(officer_client, session):
    # The line the widening deliberately stops at: a code and a scan counter
    # identify nobody, a roster carries names and personal emails.
    social = make_committee(session, name="Social", chair_role=Role.social_chair)
    event = make_event(session, title="Mixer")
    link_host(session, event, social)

    body = officer_client.get("/events/all").json()
    assert body[0]["sign_in_code"]
    assert body[0]["can_view_roster"] is False

    assert officer_client.get(f"/events/{event.id}/attendance").status_code == 403
    # ...but the counter beside the QR they're allowed to present works.
    assert officer_client.get(f"/events/{event.id}/scan-count").status_code == 200


def test_all_events_mints_missing_codes(officer_client, session):
    # Only sync_events mints at creation, so seeded and hand-added events
    # start with NULL in both columns.
    event = make_event(session, sign_in_code=None, sign_out_code=None)

    body = officer_client.get("/events/all").json()

    assert body[0]["sign_in_code"]
    assert body[0]["sign_out_code"]
    session.refresh(event)
    assert event.sign_in_code == body[0]["sign_in_code"]


def test_all_events_reports_attendee_counts(chair_client, session, committee):
    event = make_event(session, start_in=timedelta(hours=1))
    link_host(session, event, committee)
    for i in range(2):
        attendee = make_user(
            session,
            cougarnet_email=f"a{i}@cougarnet.uh.edu",
            personal_email=f"a{i}@gmail.com",
            psid=f"900000{i}",
        )
        record_sign_in(session, attendee, event)

    body = chair_client.get("/events/all").json()

    assert body[0]["attendee_count"] == 2


def test_all_events_hides_a_soft_deleted_event(chair_client, session, committee):
    live = make_event(session, title="Mixer")
    hidden = make_event(session, title="Cancelled Mixer", deleted_at=utcnow())
    link_host(session, live, committee)
    link_host(session, hidden, committee)

    resp = chair_client.get("/events/all")

    assert {e["id"] for e in resp.json()} == {live.id}


def test_upcoming_hides_a_soft_deleted_event(client, session):
    live = make_event(session, title="Mixer")
    make_event(session, title="Cancelled Mixer", deleted_at=utcnow())

    resp = client.get("/events/upcoming")

    assert {e["id"] for e in resp.json()} == {live.id}


def test_setting_a_reminder_on_a_soft_deleted_event_is_a_404(client, session):
    # get_live_event turns a hidden event into the route's ordinary 404, so a
    # member can't subscribe to mail about an event that's off the calendar.
    hidden = make_event(session, title="Cancelled Mixer", deleted_at=utcnow())

    assert client.post(f"/events/{hidden.id}/remind").status_code == 404


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

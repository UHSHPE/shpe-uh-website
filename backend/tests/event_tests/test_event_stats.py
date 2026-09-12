# GET /events/{id}/stats -- the aggregate statistics panel behind an event
# card on the chair/E-Board Events page. The properties worth pinning are
# (a) it never identifies an attendee, which is what lets it skip per-event
# scoping, and (b) the breakdowns stay complete: fixed categories keep their
# zero buckets, and free-text majors never silently drop out of the totals.

from datetime import timedelta

from models.user.user_enums import Classification, Colleges, MembershipStatus, Role
from services.attendance_services import record_sign_in, record_sign_out
from services.time_services import utcnow
from tests.conftest import make_event, make_user
from tests.event_tests.conftest import link_host, make_committee


def attendee(session, n, **overrides):
    """A distinct member. personal_email and psid are unique too, so all
    three have to vary -- see CLAUDE.md's "What NOT to do"."""
    fields = dict(
        cougarnet_email=f"m{n}@cougarnet.uh.edu",
        personal_email=f"m{n}@gmail.com",
        psid=f"200000{n}",
    )
    fields.update(overrides)
    return make_user(session, **fields)


def hosted_event(session, committee, **overrides):
    event = make_event(session, start_in=timedelta(hours=1), **overrides)
    link_host(session, event, committee)
    return event


def test_stats_counts_turnout(chair_client, session, committee):
    event = hosted_event(session, committee)
    stayed = attendee(session, 1)
    left_early = attendee(session, 2)
    record_sign_in(session, stayed, event)
    record_sign_in(session, left_early, event)
    record_sign_out(session, left_early, event)

    body = chair_client.get(f"/events/{event.id}/stats").json()

    assert body["event_id"] == event.id
    assert body["title"] == event.title
    assert body["signed_in"] == 2
    assert body["signed_out"] == 1
    assert body["still_signed_in"] == 1


def test_stats_counts_guests_points_and_national_members(chair_client, session, committee):
    event = hosted_event(session, committee)
    host = attendee(session, 1, is_national_member=True)
    plain = attendee(session, 2, is_national_member=False)
    _, host_points = record_sign_in(session, host, event, brought_new_member=True, new_member_name="Ana")
    _, plain_points = record_sign_in(session, plain, event)

    body = chair_client.get(f"/events/{event.id}/stats").json()

    assert body["guests_brought"] == 1
    assert body["national_members"] == 1
    assert body["total_points_awarded"] == host_points + plain_points


def test_average_minutes_ignores_members_who_never_signed_out(chair_client, session, committee):
    # Counting a no-sign-out as a 0-minute visit would drag the average
    # toward "nobody stayed" on exactly the events where sign-out was never
    # announced.
    event = hosted_event(session, committee)
    stayed = attendee(session, 1)
    never_left = attendee(session, 2)
    attendance, _ = record_sign_in(session, stayed, event)
    record_sign_in(session, never_left, event)

    attendance.signed_in_at = utcnow() - timedelta(minutes=90)
    session.add(attendance)
    session.commit()
    record_sign_out(session, stayed, event)

    body = chair_client.get(f"/events/{event.id}/stats").json()

    assert body["average_minutes"] == 90


def test_average_minutes_is_null_when_nobody_signed_out(chair_client, session, committee):
    event = hosted_event(session, committee)
    record_sign_in(session, attendee(session, 1), event)

    assert chair_client.get(f"/events/{event.id}/stats").json()["average_minutes"] is None


def test_classifications_keep_their_empty_buckets(chair_client, session, committee):
    # The frontend draws a fixed bar row, so a missing category has to read
    # as "nobody came" rather than vanishing from the chart.
    event = hosted_event(session, committee)
    record_sign_in(session, attendee(session, 1, classification=Classification.junior), event)

    body = chair_client.get(f"/events/{event.id}/stats").json()

    labels = [c["label"] for c in body["classifications"]]
    assert labels == [c.value for c in Classification]
    counts = {c["label"]: c["count"] for c in body["classifications"]}
    assert counts["Junior"] == 1
    assert counts["Freshman"] == 0


def test_college_and_membership_breakdowns_are_complete(chair_client, session, committee):
    event = hosted_event(session, committee)
    record_sign_in(session, attendee(
        session, 1, college=Colleges.engineering, is_returning=MembershipStatus.returning_2,
    ), event)

    body = chair_client.get(f"/events/{event.id}/stats").json()

    assert [c["label"] for c in body["colleges"]] == [c.value for c in Colleges]
    assert [m["label"] for m in body["membership"]] == [m.value for m in MembershipStatus]
    assert {c["label"]: c["count"] for c in body["colleges"]}[Colleges.engineering.value] == 1
    assert {m["label"]: m["count"] for m in body["membership"]}[
        MembershipStatus.returning_2.value
    ] == 1


def test_top_majors_collapses_the_tail_without_losing_anyone(chair_client, session, committee):
    # Six distinct majors, one of them held by two people. Only five are
    # named, so the sixth has to survive in other_majors -- otherwise the
    # breakdown quietly stops adding up to signed_in.
    event = hosted_event(session, committee)
    majors = [
        "Mechanical Engineering",
        "Mechanical Engineering",
        "Civil Engineering",
        "Chemical Engineering",
        "Biology",
        "Physics",
        "Mathematics",
    ]
    for i, major in enumerate(majors):
        record_sign_in(session, attendee(session, i, major=major), event)

    body = chair_client.get(f"/events/{event.id}/stats").json()

    assert len(body["top_majors"]) == 5
    assert body["top_majors"][0] == {"label": "Mechanical Engineering", "count": 2}
    assert body["distinct_majors"] == 6
    named = sum(m["count"] for m in body["top_majors"])
    assert named + body["other_majors"] == body["signed_in"] == 7


def test_top_majors_breaks_ties_alphabetically(chair_client, session, committee):
    # Stable order across reloads -- a Counter's insertion order would
    # reshuffle the chart whenever the roster query came back differently.
    event = hosted_event(session, committee)
    for i, major in enumerate(["Physics", "Biology", "Chemistry"]):
        record_sign_in(session, attendee(session, i, major=major), event)

    body = chair_client.get(f"/events/{event.id}/stats").json()

    assert [m["label"] for m in body["top_majors"]] == ["Biology", "Chemistry", "Physics"]


def test_first_time_attendees_counts_only_a_members_earliest_event(chair_client, session, committee):
    earlier = hosted_event(session, committee, title="First GM")
    later = hosted_event(session, committee, title="Second GM")
    veteran = attendee(session, 1)
    newcomer = attendee(session, 2)

    record_sign_in(session, veteran, earlier)
    record_sign_in(session, veteran, later)
    record_sign_in(session, newcomer, later)

    body = chair_client.get(f"/events/{later.id}/stats").json()

    assert body["first_time_attendees"] == 1
    assert body["returning_attendees"] == 1
    assert chair_client.get(f"/events/{earlier.id}/stats").json()["first_time_attendees"] == 1


def test_stats_for_an_event_with_no_attendance(chair_client, session, committee):
    event = hosted_event(session, committee)

    body = chair_client.get(f"/events/{event.id}/stats").json()

    assert body["signed_in"] == 0
    assert body["average_minutes"] is None
    assert body["top_majors"] == []
    assert body["other_majors"] == 0
    # The fixed categories still render, all zero.
    assert len(body["classifications"]) == len(Classification)


def test_stats_exposes_no_attendee_identity(chair_client, session, committee):
    # The whole reason this endpoint can skip per-event scoping. If this
    # fails, the gate on the route has to be tightened to host_scoped_events.
    event = hosted_event(session, committee)
    member = attendee(session, 1, first_name="Renata", last_name="Quintero")
    record_sign_in(session, member, event, brought_new_member=True, new_member_name="Ana")

    resp = chair_client.get(f"/events/{event.id}/stats")

    for leak in ("Renata", "Quintero", member.personal_email, member.cougarnet_email, member.psid, "Ana"):
        assert leak not in resp.text


def test_any_chair_may_read_another_committees_stats(chair_client, session):
    # Aggregate-only, so All Events is clickable for every event -- unlike
    # the roster, which stays scoped through EventHost.
    other = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    event = hosted_event(session, other)

    assert chair_client.get(f"/events/{event.id}/attendance").status_code == 403
    assert chair_client.get(f"/events/{event.id}/stats").status_code == 200


def test_regular_member_cannot_read_stats(client, session, committee):
    event = hosted_event(session, committee)

    assert client.get(f"/events/{event.id}/stats").status_code == 403


def test_stats_for_a_soft_deleted_event_is_a_404(chair_client, session, committee):
    hidden = hosted_event(session, committee, deleted_at=utcnow())

    assert chair_client.get(f"/events/{hidden.id}/stats").status_code == 404

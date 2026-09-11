"""GET /leaderboard — public chapter points leaderboard.

The property that makes the breakdown trustworthy is that it reconciles:
User.points is written only by attendance_services, which writes the same
figure to EventAttendance.points_awarded, so the pillar columns plus
uncategorized must always equal the member's total. Several tests below assert
that directly rather than checking individual cells, because it is the
invariant that breaks silently if a third writer of User.points is added.
"""

import pytest

from models.event_attendance import EventAttendance
from services.leaderboard_services import (
    EVENT_TYPE_PILLAR,
    PILLAR_KEYS,
    pillar_for_event_type,
)
from tests.conftest import make_event, make_user


def attend(session, user, event, points):
    session.add(EventAttendance(
        user_id=user.id,
        event_id=event.id,
        signed_in_at=event.start_time,
        points_awarded=points,
    ))
    user.points += points
    session.add(user)
    session.commit()


def member(session, local, points=0, **kw):
    """A distinct user. cougarnet_email, personal_email and psid are all
    unique, so all three must vary per user or the insert dies on an index
    the test never mentions."""
    return make_user(
        session,
        first_name=local.title(),
        last_name="Member",
        cougarnet_email=f"{local}@cougarnet.uh.edu",
        personal_email=f"{local}@gmail.com",
        psid=str(abs(hash(local)) % 9000000 + 1000000),
        points=points,
        **kw,
    )


def fetch(unauth_client):
    res = unauth_client.get("/leaderboard")
    assert res.status_code == 200
    return res.json()


def test_leaderboard_is_public(unauth_client, session):
    """It renders on /membershpe, which is an unauthenticated page."""
    member(session, "ana", points=5)
    assert unauth_client.get("/leaderboard").status_code == 200


def test_members_are_ranked_by_points_descending(unauth_client, session):
    member(session, "low", points=3)
    member(session, "high", points=30)
    member(session, "mid", points=12)

    names = [e["name"] for e in fetch(unauth_client)["entries"]]
    assert names == ["High Member", "Mid Member", "Low Member"]


def test_ties_share_a_rank_and_the_next_member_skips(unauth_client, session):
    member(session, "aaa", points=10)
    member(session, "bbb", points=10)
    member(session, "ccc", points=1)

    ranks = [(e["name"], e["rank"]) for e in fetch(unauth_client)["entries"]]
    assert ranks == [("Aaa Member", 1), ("Bbb Member", 1), ("Ccc Member", 3)]


def test_every_verified_member_appears_even_with_zero_points(unauth_client, session):
    member(session, "scorer", points=8)
    member(session, "quiet", points=0)

    names = [e["name"] for e in fetch(unauth_client)["entries"]]
    assert "Quiet Member" in names


def test_unverified_accounts_are_excluded(unauth_client, session):
    """They cannot log in and always hold 0 points — listing them would
    publish pending signups on a public page."""
    member(session, "real", points=4)
    member(session, "pending", points=0, email_verified=False)

    names = [e["name"] for e in fetch(unauth_client)["entries"]]
    assert names == ["Real Member"]


def test_points_are_split_by_pillar(unauth_client, session):
    user = member(session, "split")
    attend(session, user, make_event(session, event_type="outreach"), 4)
    attend(session, user, make_event(session, event_type="professional"), 3)
    attend(session, user, make_event(session, event_type="academic"), 2)

    entry = fetch(unauth_client)["entries"][0]
    assert entry["total_points"] == 9
    assert entry["points_by_pillar"]["community"] == 4
    assert entry["points_by_pillar"]["professional"] == 3
    assert entry["points_by_pillar"]["academic"] == 2
    assert entry["points_by_pillar"]["chapter"] == 0


def test_same_pillar_events_accumulate(unauth_client, session):
    """outreach and shpe_jr are both Community — they must sum into one cell,
    not overwrite each other."""
    user = member(session, "community")
    attend(session, user, make_event(session, event_type="outreach"), 4)
    attend(session, user, make_event(session, event_type="shpe_jr"), 6)

    entry = fetch(unauth_client)["entries"][0]
    assert entry["points_by_pillar"]["community"] == 10


def test_breakdown_always_sums_to_the_total(unauth_client, session):
    """The invariant the whole feature rests on."""
    user = member(session, "sums")
    for slug, pts in (("social", 2), ("eboard", 3), ("mentorshpe", 5), ("eec", 1)):
        attend(session, user, make_event(session, event_type=slug), pts)

    entry = fetch(unauth_client)["entries"][0]
    assert sum(entry["points_by_pillar"].values()) + entry["uncategorized_points"] == entry["total_points"]


def test_unknown_event_type_counts_toward_the_total_not_a_pillar(unauth_client, session):
    """A new tracker-sheet dropdown option must not silently vanish from the
    total, or the columns stop adding up with nothing to explain the gap."""
    user = member(session, "unknown")
    attend(session, user, make_event(session, event_type="brand_new_thing"), 7)

    entry = fetch(unauth_client)["entries"][0]
    assert entry["total_points"] == 7
    assert entry["uncategorized_points"] == 7
    assert sum(entry["points_by_pillar"].values()) == 0


def test_null_event_type_is_uncategorized(unauth_client, session):
    user = member(session, "nulltype")
    attend(session, user, make_event(session, event_type=None), 3)

    assert fetch(unauth_client)["entries"][0]["uncategorized_points"] == 3


def test_soft_deleted_events_still_count(unauth_client, session):
    """Every other event read path hides soft-deleted events. This one must
    not: the points were really earned, User.points still includes them, and
    filtering here is exactly what would break the reconciliation."""
    from services.time_services import utcnow

    user = member(session, "deleted")
    event = make_event(session, event_type="outreach")
    attend(session, user, event, 4)
    event.deleted_at = utcnow()
    session.add(event)
    session.commit()

    entry = fetch(unauth_client)["entries"][0]
    assert entry["total_points"] == 4
    assert entry["points_by_pillar"]["community"] == 4


def test_every_pillar_key_is_present_even_when_zero(unauth_client, session):
    """The frontend renders a fixed column set and indexes without guards."""
    member(session, "zeros", points=0)
    entry = fetch(unauth_client)["entries"][0]
    assert sorted(entry["points_by_pillar"]) == sorted(PILLAR_KEYS)


def test_pillar_definitions_ride_along_with_the_rows(unauth_client, session):
    """One source of truth for the column set — the frontend builds its
    headers from this rather than mirroring the list."""
    member(session, "cols")
    payload = fetch(unauth_client)
    assert [p["key"] for p in payload["pillars"]] == PILLAR_KEYS
    assert all(p["label"] and p["short"] for p in payload["pillars"])


def test_leaderboard_exposes_no_personal_details(unauth_client, session):
    """PUBLIC endpoint. Name and points only — no id, email, PSID or
    classification. If this fails, a public roster became a public directory."""
    member(session, "private", points=2)
    entry = fetch(unauth_client)["entries"][0]
    assert set(entry) == {"rank", "name", "total_points", "points_by_pillar", "uncategorized_points"}
    blob = str(entry).lower()
    for leaked in ("cougarnet", "gmail", "psid", "@"):
        assert leaked not in blob


@pytest.mark.parametrize("slug", sorted(EVENT_TYPE_PILLAR))
def test_every_known_slug_maps_to_a_real_pillar(slug):
    assert pillar_for_event_type(slug) in PILLAR_KEYS


def test_slug_matching_is_case_and_whitespace_insensitive(session):
    assert pillar_for_event_type("  Outreach ") == "community"

"""GET /leaderboard — public chapter points leaderboard, total only.

Every source of points (QR attendance, Google Forms, approved gallery photos)
lands in User.points, so the leaderboard reads that one figure and needs no
per-source or per-category breakdown to stay correct.
"""

from services.gallery_services import add_gallery_points_to_user
from tests.conftest import make_user
from tests.gallery_tests.helpers import make_gallery_photo


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


def test_total_is_the_members_stored_points(unauth_client, session):
    member(session, "stored", points=17)
    assert fetch(unauth_client)["entries"][0]["total_points"] == 17


def test_approved_gallery_photo_points_count_toward_the_total(unauth_client, session):
    """Gallery points never write an EventAttendance row — the total must
    still include them."""
    user = member(session, "photographer", points=5)
    photo = make_gallery_photo(session, user)
    add_gallery_points_to_user(photo, session)
    session.commit()

    assert fetch(unauth_client)["entries"][0]["total_points"] == 6


def test_response_carries_entries_only(unauth_client, session):
    """Total-only: no pillar definitions or other column metadata ride along."""
    member(session, "shape")
    assert set(fetch(unauth_client)) == {"entries"}


def test_leaderboard_exposes_no_personal_details(unauth_client, session):
    """PUBLIC endpoint. Name and points only — no id, email, PSID or
    classification. If this fails, a public roster became a public directory."""
    member(session, "private", points=2)
    entry = fetch(unauth_client)["entries"][0]
    assert set(entry) == {"rank", "name", "total_points"}
    blob = str(entry).lower()
    for leaked in ("cougarnet", "gmail", "psid", "@"):
        assert leaked not in blob

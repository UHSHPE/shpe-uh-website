"""Committee.joinable enforced on the write and read paths.

Regression coverage for security finding F10: the flag was consulted only by
read paths (get_all_committees, host_scoped_events) while join_committee
inserted a membership with no check beyond authentication. committee_id is a
bare path int and the ids are contiguous by seed order -- the 14 real
committees, then the 10 joinable=False E-Board rows -- so any verified member
could walk them and self-insert into an officer's container, which
GET /committees/{id}/messages then accepted as a legitimate membership.
"""

from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlmodel import select

from database import get_session
from models.committee import CommitteeMembership
from models.committee_message import CommitteeMessage
from models.user.user_enums import Role
from services.dependencies import get_current_user
from services.rate_limit import JOIN_LIMIT, limit_count

from tests.committee_tests.conftest import make_chair, make_committee


@contextmanager
def client_for(session, user):
    """An auth'd TestClient for an arbitrary user.

    chair_client is bound to the joinable `committee` fixture and these tests
    need a chair of a joinable=False row. Same override mechanics, same rule:
    one auth'd client per test -- don't nest this with `client`.
    """
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def hidden_committee(session, **overrides):
    """One of the E-Board rows that exist only so EventHost has a target."""
    fields = dict(name="Vice President External", chair_role=Role.vpe, joinable=False)
    fields.update(overrides)
    return make_committee(session, **fields)


def memberships_in(session, committee_id):
    return session.exec(
        select(CommitteeMembership).where(
            CommitteeMembership.committee_id == committee_id
        )
    ).all()


def post_message(session, committee, sender, body="Officer-only business"):
    session.add(CommitteeMessage(
        committee_id=committee.id,
        sender_id=sender.id,
        body=body,
    ))
    session.commit()


# --- the write path -------------------------------------------------------

def test_join_refuses_a_non_joinable_committee(client, session):
    """The F10 core. 404 rather than 403: a 403 would confirm the row exists."""
    hidden = hidden_committee(session)

    assert client.post(f"/committees/{hidden.id}/join").status_code == 404


def test_refused_join_writes_no_membership(client, session):
    """Assert on the table, not just the status code -- the membership row is
    what the message gate reads, so a 404 with a row written would close
    nothing."""
    hidden = hidden_committee(session)

    client.post(f"/committees/{hidden.id}/join")

    assert memberships_in(session, hidden.id) == []


def test_join_still_works_on_a_real_committee(client, session, committee):
    """The behaviour being preserved -- the fix must not refuse real joins."""
    assert client.post(f"/committees/{committee.id}/join").status_code == 200
    assert len(memberships_in(session, committee.id)) == 1


def test_a_refused_join_spends_no_budget(client, session, committee):
    """Pins the ordering: the joinable check sits ABOVE join_budget_exhausted.

    Reverse the two and walking the hidden ids -- requests that write nothing
    at all -- would burn a member's hourly budget and lock them out of joining
    the committees they actually want.
    """
    hidden = hidden_committee(session)

    for _ in range(limit_count(JOIN_LIMIT)):
        assert client.post(f"/committees/{hidden.id}/join").status_code == 404

    assert client.post(f"/committees/{committee.id}/join").status_code == 200


# --- the read path --------------------------------------------------------

def test_preexisting_membership_cannot_read_a_hidden_committees_messages(client, session, user):
    """The case the write check alone misses.

    Refusing the join is prospective only. A row inserted before that check
    existed -- or left behind by _sync_chair_memberships demoting an officer,
    which clears is_chair but keeps status=True -- keeps passing the gate
    forever, and the two are byte-identical. This is that row.
    """
    hidden = hidden_committee(session)
    chair = make_chair(session, hidden)
    post_message(session, hidden, chair)

    session.add(CommitteeMembership(
        user_id=user.id,
        committee_id=hidden.id,
        status=True,
        is_chair=False,
    ))
    session.commit()

    assert client.get(f"/committees/{hidden.id}/messages").status_code == 403


def test_member_can_still_read_a_real_committees_messages(client, session, committee):
    """Regression: the added joinable term must not break the ordinary gate."""
    chair = make_chair(session, committee)
    post_message(session, committee, chair, body="Meeting moved to Thursday")

    assert client.post(f"/committees/{committee.id}/join").status_code == 200

    response = client.get(f"/committees/{committee.id}/messages")
    assert response.status_code == 200
    assert [m["body"] for m in response.json()] == ["Meeting moved to Thursday"]


# --- the officer paths that must keep working -----------------------------

def test_chair_of_a_hidden_committee_can_still_read_its_messages(session):
    """Pins the decision to check in join_committee, not get_committee_or_404.

    9 of the 10 E-Board rows carry a real chair_role and _sync_chair_memberships
    creates the officer's is_chair row automatically, so a blanket refusal in
    the resolver would lock the VPE out of their own seat.
    """
    hidden = hidden_committee(session)
    chair = make_chair(session, hidden)
    post_message(session, hidden, chair)

    with client_for(session, chair) as chair_side:
        response = chair_side.get(f"/committees/{hidden.id}/messages")

    assert response.status_code == 200
    assert [m["body"] for m in response.json()] == ["Officer-only business"]


def test_chair_of_a_hidden_committee_can_still_post_and_read_the_roster(session):
    """Same pin, on the two other get_committee_or_404 callers."""
    hidden = hidden_committee(session)
    chair = make_chair(session, hidden)

    with client_for(session, chair) as chair_side:
        sent = chair_side.post(
            f"/committees/{hidden.id}/messages",
            json={"body": "Agenda for the next GBM"},
        )
        roster = chair_side.get(f"/committees/{hidden.id}/members")

    assert sent.status_code == 200
    assert roster.status_code == 200

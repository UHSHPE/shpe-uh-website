"""POST /committees/{id}/join -- idempotence and the per-account join budget.

Regression coverage for security finding F9: the route used to treat a repeat
join as a fresh one, re-emitting a notification to the joining member and one
to every chair on each POST. Nothing in the codebase deletes a Notification
row and GET /notifications is unpaginated, so an unbounded loop could bury a
chair's feed permanently.
"""

from services.rate_limit import JOIN_LIMIT, limit_count

from tests.committee_tests.conftest import make_committee, notifications_for


def test_first_join_notifies_member_and_each_chair(client, session, user, committee, co_chairs):
    """The behaviour being preserved -- the fix must not just delete the notifications."""
    assert client.post(f"/committees/{committee.id}/join").status_code == 200

    assert len(notifications_for(session, user.id)) == 1
    for chair in co_chairs:
        assert len(notifications_for(session, chair.id)) == 1


def test_repeat_join_writes_no_new_notifications(client, session, user, committee, co_chairs):
    """The F9 core: a second join is a no-op, not a second round of notifications."""
    client.post(f"/committees/{committee.id}/join")
    before = {c.id: len(notifications_for(session, c.id)) for c in co_chairs}

    for _ in range(5):
        # Still a success -- a double-tap must not look like a failure.
        assert client.post(f"/committees/{committee.id}/join").status_code == 200

    assert len(notifications_for(session, user.id)) == 1
    for chair in co_chairs:
        assert len(notifications_for(session, chair.id)) == before[chair.id]


def test_rejoin_after_leave_still_notifies(client, session, user, committee, co_chairs):
    """A genuine rejoin must still notify -- the case an over-eager early return breaks."""
    client.post(f"/committees/{committee.id}/join")
    assert client.delete(f"/committees/{committee.id}/leave").status_code == 204
    assert client.post(f"/committees/{committee.id}/join").status_code == 200

    for chair in co_chairs:
        assert len(notifications_for(session, chair.id)) == 2


def test_join_leave_loop_exhausts_the_budget(client, committee, co_chairs):
    """The actual F9 bypass.

    leave_committee hard-deletes the membership row, so join/leave/join keeps
    recreating the "no existing membership" condition and the early return never
    fires -- every iteration is a real join. The per-account budget is what
    bounds it.
    """
    for _ in range(limit_count(JOIN_LIMIT)):
        assert client.post(f"/committees/{committee.id}/join").status_code == 200
        assert client.delete(f"/committees/{committee.id}/leave").status_code == 204

    assert client.post(f"/committees/{committee.id}/join").status_code == 429


def test_exhausted_budget_still_allows_a_no_op_join(client, session, committee, co_chairs):
    """Pins the ordering: the early return sits ABOVE the budget check.

    Reverse the two and a member who has legitimately spent their budget gets a
    429 for re-clicking Join on a committee they are already in -- a request
    that writes nothing at all. Note this only bites once the budget is spent,
    which is why simply looping no-op joins proves nothing.
    """
    other = make_committee(session, name="Outreach", chair_role=None)

    # One real join we keep, then burn the remaining budget elsewhere.
    assert client.post(f"/committees/{committee.id}/join").status_code == 200
    for _ in range(limit_count(JOIN_LIMIT) - 1):
        assert client.post(f"/committees/{other.id}/join").status_code == 200
        assert client.delete(f"/committees/{other.id}/leave").status_code == 204

    # Budget spent: a real join is refused...
    assert client.post(f"/committees/{other.id}/join").status_code == 429
    # ...but re-joining the committee we are already in still succeeds.
    assert client.post(f"/committees/{committee.id}/join").status_code == 200

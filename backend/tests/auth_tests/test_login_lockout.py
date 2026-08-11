"""Per-account login lockout: LOCKOUT_THRESHOLD consecutive failures lock the
account for LOCKOUT_MINUTES → 429 even with the correct password. Distinct
from (and layered under) slowapi's per-IP 5/minute limit on /login — these
tests call limiter.reset() between attempts so the IP limiter's 429s never
shadow the lockout's."""
from datetime import timedelta

import pytest

from routes.auth_routes import LOCKOUT_THRESHOLD
from security.hashing import get_password_hash
from services.rate_limit import limiter
from services.time_services import utcnow
from tests.conftest import make_user

PASSWORD = "correct-horse-battery"
WRONG = "wrong-password-guess"


@pytest.fixture
def login_user(session):
    # make_user defaults email_verified=True; multi-select rows aren't needed
    # for /login (only /me requires them).
    return make_user(session, hashed_password=get_password_hash(PASSWORD))


def login(client, email, password):
    # Reset the per-IP slowapi counter first — we're testing the per-account
    # lockout, not the IP throttle.
    limiter.reset()
    return client.post("/login", data={"username": email, "password": password})


def fail_login(client, email, times):
    for _ in range(times):
        res = login(client, email, WRONG)
        assert res.status_code == 401
    return res


def test_lock_engages_after_threshold_failures(unauth_client, session, login_user):
    fail_login(unauth_client, login_user.cougarnet_email, LOCKOUT_THRESHOLD)

    session.refresh(login_user)
    assert login_user.failed_login_count == LOCKOUT_THRESHOLD
    assert login_user.locked_until is not None

    # Even the CORRECT password bounces while locked.
    res = login(unauth_client, login_user.cougarnet_email, PASSWORD)
    assert res.status_code == 429


def test_failed_count_persists_across_requests(unauth_client, session, login_user):
    # Each failure is its own request — the count must be committed every time,
    # not only once the threshold is crossed.
    fail_login(unauth_client, login_user.cougarnet_email, 3)

    session.refresh(login_user)
    assert login_user.failed_login_count == 3
    assert login_user.locked_until is None


def test_one_failure_below_threshold_still_allows_login(unauth_client, session, login_user):
    fail_login(unauth_client, login_user.cougarnet_email, LOCKOUT_THRESHOLD - 1)
    assert login(unauth_client, login_user.cougarnet_email, PASSWORD).status_code == 200


def test_successful_login_resets_counter(unauth_client, session, login_user):
    fail_login(unauth_client, login_user.cougarnet_email, 4)

    assert login(unauth_client, login_user.cougarnet_email, PASSWORD).status_code == 200

    session.refresh(login_user)
    assert login_user.failed_login_count == 0
    assert login_user.locked_until is None


def test_expired_lock_clears_and_login_succeeds(unauth_client, session, login_user):
    # Simulate a lock that has already run out.
    login_user.failed_login_count = LOCKOUT_THRESHOLD
    login_user.locked_until = utcnow() - timedelta(minutes=1)
    session.add(login_user)
    session.commit()

    assert login(unauth_client, login_user.cougarnet_email, PASSWORD).status_code == 200

    session.refresh(login_user)
    assert login_user.failed_login_count == 0
    assert login_user.locked_until is None


def test_single_failure_after_expired_lock_does_not_relock(unauth_client, session, login_user):
    # An expired lock must fully reset the counter — one fresh typo starts the
    # count at 1, it doesn't ride on the stale pre-lock count.
    login_user.failed_login_count = LOCKOUT_THRESHOLD
    login_user.locked_until = utcnow() - timedelta(minutes=1)
    session.add(login_user)
    session.commit()

    res = login(unauth_client, login_user.cougarnet_email, WRONG)
    assert res.status_code == 401

    session.refresh(login_user)
    assert login_user.failed_login_count == 1
    assert login_user.locked_until is None


def test_unknown_email_failures_return_401(unauth_client, session):
    # No user row → nothing to count; must stay a clean generic 401, never 500.
    for _ in range(3):
        res = login(unauth_client, "ghost@cougarnet.uh.edu", WRONG)
        assert res.status_code == 401

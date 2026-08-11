# API tests for GET /events/code/{code} -- the public, read-only preview
# consumed by the mobile check-in flow before anything is recorded.
#
# GET /events/code/{code} depends on get_optional_user directly, not
# get_current_user -- the `client` fixture (tests/conftest.py) only
# overrides get_current_user, and TestClient sends no Authorization header
# by default, so a plain `client.get(...)` here is indistinguishable from an
# anonymous call. Tests that need an authed preview use the `signed_in`
# fixture below, same pattern as tests/shop_tests/test_dues_rules.py.

from datetime import timedelta

import pytest

from main import app
from services.dependencies import get_optional_user
from services.time_services import utcnow
from tests.conftest import make_event

STARTED = timedelta(minutes=-5)


@pytest.fixture
def signed_in(user):
    app.dependency_overrides[get_optional_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_optional_user, None)


def test_anonymous_preview_returns_event_but_never_codes(unauth_client, session):
    make_event(session, start_in=STARTED, sign_in_code="prev-in-1", sign_out_code="prev-out-1")

    resp = unauth_client.get("/events/code/prev-in-1")

    assert resp.status_code == 200
    body_text = resp.text
    assert "sign_in_code" not in body_text
    assert "sign_out_code" not in body_text
    assert "prev-in-1" not in body_text
    assert "prev-out-1" not in body_text
    body = resp.json()
    assert body["action"] == "sign_in"
    assert body["state"] == "ok"
    assert body["signed_in_at"] is None


def test_unknown_code_returns_generic_404(unauth_client):
    resp = unauth_client.get("/events/code/not-a-real-code")
    assert resp.status_code == 404


def test_expired_event_reports_ended_state(unauth_client, session):
    make_event(
        session,
        start_in=timedelta(days=-2),
        end_time=utcnow() - timedelta(days=1),
        sign_in_code="prev-in-2",
        sign_out_code="prev-out-2",
    )

    resp = unauth_client.get("/events/code/prev-in-2")

    assert resp.status_code == 200
    assert resp.json()["state"] == "ended"


def test_future_event_reports_not_started_state(unauth_client, session):
    make_event(
        session,
        start_in=timedelta(minutes=90),
        sign_in_code="prev-in-3",
        sign_out_code="prev-out-3",
    )

    resp = unauth_client.get("/events/code/prev-in-3")

    assert resp.status_code == 200
    assert resp.json()["state"] == "not_started"


def test_authed_preview_fills_signed_in_at_after_sign_in(client, session, signed_in):
    make_event(session, start_in=STARTED, sign_in_code="prev-in-4", sign_out_code="prev-out-4")

    client.post("/events/attend", json={"code": "prev-in-4"})
    resp = client.get("/events/code/prev-in-4")

    assert resp.status_code == 200
    body = resp.json()
    assert body["signed_in_at"] is not None
    assert body["signed_out_at"] is None


def test_sign_out_preview_with_no_check_in_leaves_timestamps_null(client, session, signed_in):
    """Signal the frontend uses for the 'no check-in on record' screen: an
    authed sign-out preview with no attendance row at all."""
    make_event(session, start_in=STARTED, sign_in_code="prev-in-5", sign_out_code="prev-out-5")

    resp = client.get("/events/code/prev-out-5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "sign_out"
    assert body["signed_in_at"] is None
    assert body["signed_out_at"] is None


def test_unauthenticated_preview_does_not_leak_another_users_timestamps(
    unauth_client, session, user
):
    """No token at all -- get_optional_user returns None -- so the caller's
    own row is never looked up or echoed back, even though a row exists for
    someone else."""
    make_event(session, start_in=STARTED, sign_in_code="prev-in-6", sign_out_code="prev-out-6")

    resp = unauth_client.get("/events/code/prev-in-6")

    assert resp.status_code == 200
    assert resp.json()["signed_in_at"] is None

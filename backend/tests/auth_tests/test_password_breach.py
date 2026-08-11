"""HIBP breached-password check: unit tests for is_password_pwned (with a
stubbed httpx.get — never hits the network) and route tests proving /signup
and /password-reset/confirm reject a pwned password with 422 without
mutating anything.

The conftest autouse fixture disable_hibp_check stubs the module attribute to
False for the whole suite; capturing the real function at import time (before
fixtures run) lets the unit tests exercise the genuine implementation, and the
route tests re-monkeypatch the attribute after the fixture applied.
"""
import hashlib
from datetime import timedelta

import pytest
from sqlmodel import select

from models.user.user import User
from models.user.pw_reset_token import PasswordResetToken
from services import hibp_services
from services.hibp_services import is_password_pwned as real_is_password_pwned
from services.pw_reset_services import generate_reset_token
from services.time_services import utcnow
from tests.conftest import make_user
from tests.auth_tests.test_email_verification import signup_payload


# --- unit tests: is_password_pwned with a stubbed httpx.get ---

PASSWORD = "hunter2-but-longer"
SHA1 = hashlib.sha1(PASSWORD.encode("utf-8")).hexdigest().upper()
PREFIX, SUFFIX = SHA1[:5], SHA1[5:]


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def stub_httpx_get(monkeypatch, body):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(body)

    monkeypatch.setattr(hibp_services.httpx, "get", fake_get)
    return calls


def test_pwned_password_detected(monkeypatch):
    stub_httpx_get(monkeypatch, f"AAAAAA:1\n{SUFFIX}:1337\nBBBBBB:2")
    assert real_is_password_pwned(PASSWORD) is True


def test_clean_password_not_detected(monkeypatch):
    stub_httpx_get(monkeypatch, "AAAAAA:1\nBBBBBB:2")
    assert real_is_password_pwned(PASSWORD) is False


def test_count_zero_padding_entry_ignored(monkeypatch):
    # Add-Padding: true pads responses with count-0 dummy suffixes — a 0 count
    # means "not actually breached".
    stub_httpx_get(monkeypatch, f"{SUFFIX}:0\nBBBBBB:2")
    assert real_is_password_pwned(PASSWORD) is False


def test_network_error_fails_open(monkeypatch):
    def boom(url, **kwargs):
        raise ConnectionError("HIBP is down")

    monkeypatch.setattr(hibp_services.httpx, "get", boom)
    assert real_is_password_pwned(PASSWORD) is False


def test_only_five_char_prefix_is_sent(monkeypatch):
    # k-anonymity: the URL must carry the 5-char prefix, never the full hash.
    calls = stub_httpx_get(monkeypatch, "AAAAAA:1")
    real_is_password_pwned(PASSWORD)

    assert len(calls) == 1
    assert calls[0].endswith(f"/range/{PREFIX}")
    assert SUFFIX not in calls[0]


# --- route tests: pwned password rejected with 422, nothing mutated ---

@pytest.fixture
def hibp_says_pwned(monkeypatch):
    # Runs after the autouse disable_hibp_check fixture, so this wins.
    monkeypatch.setattr(hibp_services, "is_password_pwned", lambda password: True)


def test_signup_rejects_pwned_password(unauth_client, session, hibp_says_pwned):
    res = unauth_client.post("/signup", json=signup_payload())

    assert res.status_code == 422
    assert "data breach" in res.json()["detail"]
    # No account was created.
    assert session.exec(select(User)).all() == []


def test_reset_confirm_rejects_pwned_password_and_keeps_token(unauth_client, session, hibp_says_pwned):
    user = make_user(session)
    raw, token_hash = generate_reset_token()
    session.add(PasswordResetToken(
        user_id=user.id, token_hash=token_hash, expires_at=utcnow() + timedelta(hours=1),
    ))
    session.commit()

    res = unauth_client.post(
        "/password-reset/confirm",
        json={"token": raw, "new_password": "totally-valid-length"},
    )

    assert res.status_code == 422
    assert "data breach" in res.json()["detail"]
    # The token must stay redeemable — the user gets another try.
    assert session.exec(select(PasswordResetToken)).one().used_at is None


def test_signup_fails_open_when_hibp_is_down(unauth_client, session, monkeypatch):
    # Real is_password_pwned + a network error → fail open, signup proceeds.
    monkeypatch.setattr(hibp_services, "is_password_pwned", real_is_password_pwned)

    def boom(url, **kwargs):
        raise ConnectionError("HIBP is down")

    monkeypatch.setattr(hibp_services.httpx, "get", boom)
    monkeypatch.setattr("routes.auth_routes.send_email", lambda *a, **k: True)

    res = unauth_client.post("/signup", json=signup_payload())
    assert res.status_code == 201
    assert len(session.exec(select(User)).all()) == 1

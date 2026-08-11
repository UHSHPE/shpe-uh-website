import time
from datetime import timedelta

import pytest
from sqlmodel import select

from models.user.multi_selections.user_country_origin import UserCountryOrigin
from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
from models.user.multi_selections.user_prof_dev import UserProfDev
from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
from models.user.user_enums import Industry, ProfDev, RaceEthnicity
from models.user.pw_reset_token import PasswordResetToken
from security.hashing import get_password_hash, verify_password
from services.pw_reset_services import generate_reset_token
from services.rate_limit import LOGIN_LIMIT, limit_count
from services.time_services import utcnow
from tests.conftest import make_user

OLD_PASSWORD = "oldpassword123"
NEW_PASSWORD = "newpassword456"


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture send_email calls made by the reset route (patched where it's imported)."""
    calls = []

    def record(to, subject, body):
        calls.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("routes.pw_reset_routes.send_email", record)
    return calls


def request_reset(client, email):
    return client.post("/password-reset/request", json={"email": email})


def confirm_reset(client, token, new_password=NEW_PASSWORD):
    return client.post("/password-reset/confirm", json={"token": token, "new_password": new_password})


def login(client, email, password):
    return client.post("/login", data={"username": email, "password": password})


def active_token_rows(session):
    return session.exec(
        select(PasswordResetToken).where(PasswordResetToken.used_at == None)  # noqa: E711
    ).all()


def extract_token(email_body):
    # The email contains {FRONTEND_URL}/reset-password?token=<raw>
    return email_body.split("token=")[1].split()[0]


def make_login_user(session):
    """User with a real password hash plus the multi-select rows GET /me requires."""
    user = make_user(session, hashed_password=get_password_hash(OLD_PASSWORD))
    session.add(UserRaceEthnicity(user_id=user.id, race_and_ethnicity=list(RaceEthnicity)[0]))
    session.add(UserInterestedIndustries(user_id=user.id, interested_industry=list(Industry)[0]))
    session.add(UserProfDev(user_id=user.id, prof_dev=list(ProfDev)[0]))
    session.add(UserCountryOrigin(user_id=user.id, country_origin="Mexico"))
    session.commit()
    return user


def make_reset_token(session, user, *, expires_in=timedelta(hours=1)):
    """Insert a PasswordResetToken row directly; returns the raw token."""
    raw, token_hash = generate_reset_token()
    session.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=utcnow() + expires_in))
    session.commit()
    return raw


# --- /password-reset/request ---

def test_request_nonexistent_email_is_generic_and_silent(unauth_client, session, sent_emails):
    res = request_reset(unauth_client, "ghost@cougarnet.uh.edu")

    assert res.status_code == 200
    assert session.exec(select(PasswordResetToken)).all() == []
    assert sent_emails == []


def test_request_real_user_creates_token_and_emails_cougarnet(unauth_client, session, user, sent_emails):
    res = request_reset(unauth_client, user.cougarnet_email)

    assert res.status_code == 200
    tokens = active_token_rows(session)
    assert len(tokens) == 1
    assert tokens[0].user_id == user.id
    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == user.cougarnet_email
    # The raw token rides in the email and only its hash is stored
    raw = extract_token(sent_emails[0]["body"])
    assert raw != tokens[0].token_hash
    assert raw not in tokens[0].token_hash


def test_request_responses_identical_for_real_and_fake_email(unauth_client, session, user, sent_emails):
    fake = request_reset(unauth_client, "ghost@cougarnet.uh.edu")
    real = request_reset(unauth_client, user.cougarnet_email)

    assert fake.status_code == real.status_code == 200
    assert fake.content == real.content


def test_request_invalidates_prior_active_tokens(unauth_client, session, user, sent_emails):
    request_reset(unauth_client, user.cougarnet_email)
    request_reset(unauth_client, user.cougarnet_email)

    assert len(active_token_rows(session)) == 1
    first_raw = extract_token(sent_emails[0]["body"])
    assert confirm_reset(unauth_client, first_raw).status_code == 400


# --- /password-reset/confirm ---

def test_confirm_valid_token_resets_password(unauth_client, session, sent_emails):
    user = make_user(session, hashed_password=get_password_hash(OLD_PASSWORD))
    request_reset(unauth_client, user.cougarnet_email)
    raw = extract_token(sent_emails[0]["body"])

    res = confirm_reset(unauth_client, raw)

    assert res.status_code == 200
    session.refresh(user)
    token_row = session.exec(select(PasswordResetToken)).one()
    assert token_row.used_at is not None
    assert user.password_changed_at is not None
    assert verify_password(NEW_PASSWORD, user.hashed_password)
    assert not verify_password(OLD_PASSWORD, user.hashed_password)


def test_confirm_expired_token_rejected(unauth_client, session, user):
    raw = make_reset_token(session, user, expires_in=timedelta(minutes=-1))
    assert confirm_reset(unauth_client, raw).status_code == 400


def test_confirm_token_is_single_use(unauth_client, session, user):
    raw = make_reset_token(session, user)
    assert confirm_reset(unauth_client, raw).status_code == 200
    assert confirm_reset(unauth_client, raw).status_code == 400


def test_confirm_garbage_token_rejected(unauth_client, session, user):
    assert confirm_reset(unauth_client, "not-a-real-token").status_code == 400


def test_confirm_failure_bodies_identical(unauth_client, session, user):
    expired_raw = make_reset_token(session, user, expires_in=timedelta(minutes=-1))
    used_raw = make_reset_token(session, user)
    confirm_reset(unauth_client, used_raw)

    expired = confirm_reset(unauth_client, expired_raw)
    used = confirm_reset(unauth_client, used_raw)
    garbage = confirm_reset(unauth_client, "not-a-real-token")

    assert expired.status_code == used.status_code == garbage.status_code == 400
    assert expired.content == used.content == garbage.content


def test_confirm_weak_password_rejected(unauth_client, session, user):
    raw = make_reset_token(session, user)
    res = confirm_reset(unauth_client, raw, new_password="short")
    assert res.status_code in (400, 422)
    # Token must survive the failed attempt untouched
    assert session.exec(select(PasswordResetToken)).one().used_at is None


def test_confirm_9_char_password_rejected(unauth_client, session, user):
    # One under the new 10-character minimum
    raw = make_reset_token(session, user)
    res = confirm_reset(unauth_client, raw, new_password="abc-def-9")
    assert res.status_code in (400, 422)
    assert session.exec(select(PasswordResetToken)).one().used_at is None


# --- JWT invalidation on reset ---

def test_reset_invalidates_previously_issued_jwt(unauth_client, session):
    user = make_login_user(session)
    token = login(unauth_client, user.cougarnet_email, OLD_PASSWORD).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert unauth_client.get("/me", headers=headers).status_code == 200

    # iat is floored to whole seconds — step past the second boundary so the
    # reset lands in a strictly later second than the token's iat.
    time.sleep(1.1)
    raw = make_reset_token(session, user)
    assert confirm_reset(unauth_client, raw).status_code == 200

    assert unauth_client.get("/me", headers=headers).status_code == 401


def test_token_issued_after_reset_still_works(unauth_client, session):
    user = make_login_user(session)
    raw = make_reset_token(session, user)
    assert confirm_reset(unauth_client, raw).status_code == 200

    # Login immediately (possibly within the same second as the reset) —
    # guards the whole-second strict-< comparison.
    res = login(unauth_client, user.cougarnet_email, NEW_PASSWORD)
    assert res.status_code == 200
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert unauth_client.get("/me", headers=headers).status_code == 200


# --- Rate limiting ---

def test_login_rate_limited_once_the_ip_budget_is_spent(unauth_client, session):
    # Derived from the configured limit (RATE_LIMIT_LOGIN) rather than
    # hardcoded. The address deliberately does not exist, so the per-account
    # lockout never engages and this exercises only the per-IP limiter.
    for _ in range(limit_count(LOGIN_LIMIT)):
        res = login(unauth_client, "test@cougarnet.uh.edu", "wrongpassword")
        assert res.status_code == 401
    assert login(unauth_client, "test@cougarnet.uh.edu", "wrongpassword").status_code == 429

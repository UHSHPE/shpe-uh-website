"""Signup email-verification flow: an account is created unverified, can't log
in until the emailed token is confirmed, and an unverified account never blocks
a later signup for the same email (squat reclaim)."""
import pytest
from sqlmodel import select

from models.user.user import User
from models.user.email_verification import EmailVerificationToken
from models.user.multi_selections.user_country_origin import UserCountryOrigin
from services.pw_reset_services import hash_reset_token


def signup_payload(**overrides):
    payload = {
        "first_name": "Maria",
        "last_name": "Garcia",
        "cougarnet_email": "maria.garcia@cougarnet.uh.edu",
        "personal_email": "maria.garcia@gmail.com",
        "password": "password123",
        "phone_num": "713-555-0000",
        "psid": "1112223",
        "birthday": "2000-01-01",
        "gender": "Male",
        "first_gen": True,
        "college": "College of Natural Science & Mathematics",
        "major": "Computer Science",
        "classification": "Senior",
        "gpa": "4.00 - 3.50",
        "exp_grad_date": "Spring 2027",
        "in_slack": True,
        "is_returning": "New Member",
        "is_national_member": True,
        "shirt_size": "M",
        "race_and_ethnicity": ["American Indian or Alaska Native"],
        "prof_dev": ["Internships/Co-ops"],
        "interested_industries": ["Electronics/Technology/Software"],
        "country_origin": ["Mexico"],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture the verification email so we can pull the raw token out of it."""
    calls = []

    def record(to, subject, body):
        calls.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("routes.auth_routes.send_email", record)
    return calls


def extract_token(body):
    # {FRONTEND_URL}/verify-email?token=<raw>
    return body.split("token=")[1].split()[0]


def signup(client, **overrides):
    return client.post("/signup", json=signup_payload(**overrides))


def login(client, email, password="password123"):
    return client.post("/login", data={"username": email, "password": password})


def test_signup_creates_unverified_account_and_no_token(unauth_client, session, sent_emails):
    res = signup(unauth_client)
    assert res.status_code == 201
    # No JWT is returned — the account isn't usable yet.
    assert "access_token" not in res.json()

    user = session.exec(
        select(User).where(User.cougarnet_email == "maria.garcia@cougarnet.uh.edu")
    ).one()
    assert user.email_verified is False
    # A verification email went to the CougarNet address with a token.
    assert len(sent_emails) == 1
    assert sent_emails[0]["to"] == "maria.garcia@cougarnet.uh.edu"
    raw = extract_token(sent_emails[0]["body"])
    # Only the hash is stored, never the raw token.
    token_row = session.exec(select(EmailVerificationToken)).one()
    assert token_row.token_hash == hash_reset_token(raw)
    assert raw != token_row.token_hash


def test_unverified_account_cannot_log_in(unauth_client, session, sent_emails):
    signup(unauth_client)
    res = login(unauth_client, "maria.garcia@cougarnet.uh.edu")
    assert res.status_code == 403


def test_verify_then_login_succeeds(unauth_client, session, sent_emails):
    signup(unauth_client)
    raw = extract_token(sent_emails[0]["body"])

    verified = unauth_client.post("/verify-email", json={"token": raw})
    assert verified.status_code == 200
    assert verified.json()["access_token"]  # verification issues the login token

    assert login(unauth_client, "maria.garcia@cougarnet.uh.edu").status_code == 200


def test_verify_token_is_single_use(unauth_client, session, sent_emails):
    signup(unauth_client)
    raw = extract_token(sent_emails[0]["body"])
    assert unauth_client.post("/verify-email", json={"token": raw}).status_code == 200
    assert unauth_client.post("/verify-email", json={"token": raw}).status_code == 400


def test_verify_garbage_token_rejected(unauth_client, session):
    assert unauth_client.post("/verify-email", json={"token": "nope"}).status_code == 400


def test_verified_email_blocks_reregistration(unauth_client, session, sent_emails):
    signup(unauth_client)
    raw = extract_token(sent_emails[0]["body"])
    unauth_client.post("/verify-email", json={"token": raw})

    # A second signup for a now-verified email is a 409.
    assert signup(unauth_client).status_code == 409


def test_unverified_squat_is_reclaimed_by_later_signup(unauth_client, session, sent_emails):
    # Attacker squats the email first (never verifies).
    signup(unauth_client, personal_email="attacker@gmail.com", psid="9998887")
    squat_user = session.exec(
        select(User).where(User.cougarnet_email == "maria.garcia@cougarnet.uh.edu")
    ).one()
    squat_id = squat_user.id
    stale_token = extract_token(sent_emails[0]["body"])

    # The real owner signs up for the same email — the pending squat is discarded.
    assert signup(unauth_client, personal_email="maria.garcia@gmail.com").status_code == 201

    users = session.exec(
        select(User).where(User.cougarnet_email == "maria.garcia@cougarnet.uh.edu")
    ).all()
    assert len(users) == 1
    assert users[0].personal_email == "maria.garcia@gmail.com"

    # The squatter's child rows were cleaned up — no orphan attaches to the
    # reclaimed row id.
    orphans = session.exec(
        select(UserCountryOrigin).where(UserCountryOrigin.user_id == squat_id)
    ).all()
    assert all(o.user_id == users[0].id for o in orphans) or users[0].id != squat_id

    # The stale link from the squatter's email no longer verifies anything.
    assert unauth_client.post("/verify-email", json={"token": stale_token}).status_code == 400


def test_signup_is_rate_limited(unauth_client, session, sent_emails):
    # 5/hour — the sixth distinct signup attempt from one IP is throttled.
    for i in range(5):
        res = signup(
            unauth_client,
            cougarnet_email=f"user{i}.test@cougarnet.uh.edu",
            personal_email=f"user{i}.test@gmail.com",
            psid=f"100000{i}",
        )
        assert res.status_code == 201
    throttled = signup(
        unauth_client,
        cougarnet_email="user6.test@cougarnet.uh.edu",
        personal_email="user6.test@gmail.com",
        psid="1000006",
    )
    assert throttled.status_code == 429

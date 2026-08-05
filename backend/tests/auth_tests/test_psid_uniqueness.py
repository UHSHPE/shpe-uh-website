"""PSID uniqueness: a PSID is a real-world identifier (UH's PeopleSoft ID) and
must map to at most one account, mirroring cougarnet_email's uniqueness. The
signup route checks PSID for a reclaimable unverified squat the same way it
already does for email — see auth_routes.py's `signup` handler comment on why
email is checked first."""
import pytest
from sqlmodel import select
from sqlalchemy.exc import IntegrityError

from models.user.user import User
from models.user.email_verification import EmailVerificationToken
from models.user.pw_reset_token import PasswordResetToken
from models.user.multi_selections.user_country_origin import UserCountryOrigin
from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
from models.user.multi_selections.user_prof_dev import UserProfDev
from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
from services.pw_reset_services import generate_reset_token, hash_reset_token
from services.time_services import utcnow
from datetime import timedelta

from tests.conftest import make_user


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


def signup(client, **overrides):
    return client.post("/signup", json=signup_payload(**overrides))


def test_duplicate_psid_against_verified_account_is_rejected(unauth_client, session):
    # A verified account already holds this PSID.
    make_user(
        session,
        cougarnet_email="holder@cougarnet.uh.edu",
        personal_email="holder@gmail.com",
        psid="1112223",
        email_verified=True,
    )

    res = signup(unauth_client)  # default payload uses psid=1112223, a different email
    assert res.status_code == 409
    assert res.status_code != 500
    assert "psid" in res.json()["detail"].lower()

    # No second user was created for the rejected signup.
    users = session.exec(select(User)).all()
    assert len(users) == 1


def test_duplicate_psid_against_unverified_account_is_reclaimed(unauth_client, session, sent_emails):
    # An unverified pending account squats the PSID under a different email.
    make_user(
        session,
        cougarnet_email="squatter@cougarnet.uh.edu",
        personal_email="squatter@gmail.com",
        psid="1112223",
        email_verified=False,
    )

    res = signup(unauth_client)  # default payload: maria.garcia@..., psid=1112223
    assert res.status_code == 201

    users = session.exec(select(User).where(User.psid == "1112223")).all()
    assert len(users) == 1
    assert users[0].cougarnet_email == "maria.garcia@cougarnet.uh.edu"

    # The pending squatter row is gone entirely (not just skipped over).
    squat_row = session.exec(
        select(User).where(User.cougarnet_email == "squatter@cougarnet.uh.edu")
    ).first()
    assert squat_row is None


def test_same_person_resubmits_signup_unchanged(unauth_client, session, sent_emails):
    """Same cougarnet_email AND same psid, unverified, submitted twice. This
    pins the email-then-PSID ordering in auth_routes.signup: the email branch
    deletes the pending row first, so by the time the PSID check runs, the
    row is already gone and that branch is a no-op — never two deletes
    racing to remove the same row, never a duplicate-account artifact."""
    assert signup(unauth_client).status_code == 201
    assert signup(unauth_client).status_code == 201

    users = session.exec(
        select(User).where(User.cougarnet_email == "maria.garcia@cougarnet.uh.edu")
    ).all()
    assert len(users) == 1
    assert users[0].psid == "1112223"


def test_psid_reclaim_deletes_child_rows(unauth_client, session, sent_emails):
    """Mirrors the email-reclaim child-row cleanup coverage in
    test_email_verification.py, but triggered via the PSID branch: the
    squatter has a DIFFERENT email so only the PSID lookup finds them."""
    squat_res = signup(
        unauth_client,
        cougarnet_email="squatter@cougarnet.uh.edu",
        personal_email="squatter@gmail.com",
    )
    assert squat_res.status_code == 201
    squat_user = session.exec(
        select(User).where(User.cougarnet_email == "squatter@cougarnet.uh.edu")
    ).one()
    squat_id = squat_user.id

    # Give the squatter a password-reset token too, so both token tables are
    # exercised (signup only ever creates an EmailVerificationToken itself).
    raw, hashed = generate_reset_token()
    session.add(PasswordResetToken(
        user_id=squat_id, token_hash=hashed,
        expires_at=utcnow() + timedelta(hours=1),
    ))
    session.commit()

    # A new signup for a different email but the SAME psid reclaims it.
    res = signup(unauth_client, cougarnet_email="maria.garcia@cougarnet.uh.edu")
    assert res.status_code == 201

    for model in (
        UserRaceEthnicity,
        UserInterestedIndustries,
        UserProfDev,
        UserCountryOrigin,
        EmailVerificationToken,
        PasswordResetToken,
    ):
        rows = session.exec(select(model).where(model.user_id == squat_id)).all()
        assert rows == [], f"{model.__name__} still has a row for the deleted squatter"

    assert session.get(User, squat_id) is None


def test_duplicate_psid_model_level_raises_integrity_error(session):
    """Proves the unique constraint reached the schema (a real Postgres
    UNIQUE index), not just a Pydantic-level check that the API route could
    route around."""
    make_user(session, psid="1234567")
    with pytest.raises(IntegrityError):
        make_user(
            session,
            cougarnet_email="other@cougarnet.uh.edu",
            personal_email="other@gmail.com",
            psid="1234567",
        )

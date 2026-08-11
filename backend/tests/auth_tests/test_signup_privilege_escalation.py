"""role and points must never be settable from the public /signup body.

Both fields used to live on UserBase (inherited by UserCreate), so a plain
POST /signup with extra "role"/"points" keys created a fully-admin account
with an inflated point total — no auth, no special tooling, reachable from
the public /docs "Try it out" button. They now live only on the User table
model, set exclusively by services.user_services.create_user's `role`
keyword (which the /signup route never passes), so the request body can no
longer choose either."""
from sqlmodel import select

from models.user.user import User
from models.user.user_enums import Role


def signup_payload(**overrides):
    payload = {
        "first_name": "Mallory",
        "last_name": "Attacker",
        "cougarnet_email": "mallory.attacker@cougarnet.uh.edu",
        "personal_email": "mallory.attacker@gmail.com",
        "password": "password123",
        "phone_num": "713-555-9999",
        "psid": "9998887",
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


def signup(client, **overrides):
    return client.post("/signup", json=signup_payload(**overrides))


def test_signup_cannot_grant_president_role(unauth_client, session):
    res = signup(unauth_client, role="President")
    assert res.status_code == 201

    created = session.exec(
        select(User).where(User.cougarnet_email == "mallory.attacker@cougarnet.uh.edu")
    ).one()
    assert created.role == Role.member


def test_signup_cannot_inflate_points(unauth_client, session):
    res = signup(unauth_client, points=999999)
    assert res.status_code == 201

    created = session.exec(
        select(User).where(User.cougarnet_email == "mallory.attacker@cougarnet.uh.edu")
    ).one()
    assert created.points == 0


def test_signup_cannot_grant_shop_admin_role(unauth_client, session):
    """Pins the price-manipulation vector specifically: marketing_chair is in
    SHOP_ADMIN_ROLES, so this role alone would let the attacker PATCH product
    prices, independent of anything president-only."""
    res = signup(unauth_client, role="Marketing Chair")
    assert res.status_code == 201

    created = session.exec(
        select(User).where(User.cougarnet_email == "mallory.attacker@cougarnet.uh.edu")
    ).one()
    assert created.role == Role.member


def test_me_reports_role_and_points(client, session, user):
    """Guards the silent-drop regression: UserOut doesn't inherit role/points
    from UserBase anymore, so it must re-declare them or /me would silently
    stop returning either (pydantic's default extra='ignore' means a missing
    field just vanishes, no error)."""
    # UserOut's validators require >=1 entry per multi-select list, and the
    # bare make_user fixture has none — give it the minimum so /me can
    # serialize (see tests/shop_tests/test_dues_rules.py::test_me_reports_dues_status).
    from models.user.multi_selections.user_country_origin import UserCountryOrigin
    from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
    from models.user.multi_selections.user_prof_dev import UserProfDev
    from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
    from models.user.user_enums import Industry, ProfDev, RaceEthnicity

    session.add_all([
        UserRaceEthnicity(user_id=user.id, race_and_ethnicity=RaceEthnicity.hispanic),
        UserInterestedIndustries(user_id=user.id, interested_industry=Industry.electronics),
        UserProfDev(user_id=user.id, prof_dev=ProfDev.internships),
        UserCountryOrigin(user_id=user.id, country_origin="Mexico"),
    ])
    session.commit()

    res = client.get("/me")
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == user.role.value
    assert body["points"] == user.points

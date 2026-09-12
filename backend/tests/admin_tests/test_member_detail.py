# GET /admin/members/{id} and /admin/members/{id}/resume -- the member detail
# view behind a row on the president's Members page.

from datetime import date

import pytest

from models.committee import CommitteeMembership
from models.user.multi_selections.user_country_origin import UserCountryOrigin
from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
from models.user.multi_selections.user_prof_dev import UserProfDev
from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
from models.user.user_enums import Industry, ProfDev, RaceEthnicity, Role
from tests.conftest import make_user
from tests.event_tests.conftest import make_committee


def member(session, local_part, **overrides):
    """Vary all three unique columns from one string -- cougarnet_email,
    personal_email and psid are each unique, and make_user's defaults are the
    same literals every call."""
    fields = dict(
        cougarnet_email=f"{local_part}@cougarnet.uh.edu",
        personal_email=f"{local_part}@gmail.com",
        psid=str(4000000 + abs(hash(local_part)) % 900000),
    )
    fields.update(overrides)
    return make_user(session, **fields)


def test_detail_returns_the_full_signup_profile(president_client, session):
    target = member(
        session, "ana",
        first_name="Ana", last_name="Torres",
        phone_num="713-555-0199", birthday=date(2003, 4, 9), first_gen=True,
    )

    body = president_client.get(f"/admin/members/{target.id}").json()

    assert body["id"] == target.id
    assert body["first_name"] == "Ana"
    assert body["phone_num"] == "713-555-0199"
    assert body["psid"] == target.psid
    assert body["birthday"] == "2003-04-09"
    assert body["major"] == target.major
    assert body["first_gen"] is True
    assert body["gender"] == target.gender.value
    assert body["exp_grad_date"] == target.exp_grad_date.value
    assert body["is_returning"] == target.is_returning.value
    assert body["email_verified"] is True
    assert "has_paid_dues" in body


def test_detail_includes_the_multi_select_answers(president_client, session):
    target = member(session, "luis")
    session.add_all([
        UserCountryOrigin(user_id=target.id, country_origin="Mexico"),
        UserCountryOrigin(user_id=target.id, country_origin="United States"),
        UserInterestedIndustries(user_id=target.id, interested_industry=Industry.aerospace),
        UserProfDev(user_id=target.id, prof_dev=ProfDev.internships),
        UserRaceEthnicity(user_id=target.id, race_and_ethnicity=RaceEthnicity.hispanic),
    ])
    session.commit()

    body = president_client.get(f"/admin/members/{target.id}").json()

    assert sorted(body["country_origin"]) == ["Mexico", "United States"]
    assert body["interested_industries"] == [Industry.aerospace.value]
    assert body["prof_dev"] == [ProfDev.internships.value]
    assert body["race_and_ethnicity"] == [RaceEthnicity.hispanic.value]


def test_detail_works_for_an_account_with_no_multi_select_rows(president_client, session):
    # The reason AdminMemberDetailOut declares plain lists instead of
    # inheriting UserMultiSelectedFields: those validators require >= 1 row
    # each, which would turn an incomplete account into a 500 on RESPONSE
    # validation -- and an admin directory is exactly where such an account
    # turns up. Same trap /me has.
    target = member(session, "bare")

    resp = president_client.get(f"/admin/members/{target.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["country_origin"] == []
    assert body["race_and_ethnicity"] == []


def test_detail_lists_committees_and_flags_chairs(president_client, session):
    target = member(session, "sofia")
    chaired = make_committee(session, name="Academics", chair_role=Role.academic_chair)
    joined = make_committee(session, name="Social", chair_role=Role.social_chair)
    session.add_all([
        CommitteeMembership(user_id=target.id, committee_id=chaired.id, status=True, is_chair=True),
        CommitteeMembership(user_id=target.id, committee_id=joined.id, status=True, is_chair=False),
    ])
    session.commit()

    body = president_client.get(f"/admin/members/{target.id}").json()

    assert [(c["name"], c["is_chair"]) for c in body["committees"]] == [
        ("Academics", True), ("Social", False),
    ]


def test_detail_omits_an_inactive_membership(president_client, session):
    # leave_committee hard-deletes, but a demoted chair keeps status=True --
    # an inactive row means they're genuinely out.
    target = member(session, "diego")
    left = make_committee(session, name="Social", chair_role=Role.social_chair)
    session.add(CommitteeMembership(user_id=target.id, committee_id=left.id, status=False, is_chair=False))
    session.commit()

    assert president_client.get(f"/admin/members/{target.id}").json()["committees"] == []


def test_detail_never_exposes_the_password_hash(president_client, session):
    target = member(session, "camila")

    resp = president_client.get(f"/admin/members/{target.id}")

    assert "hashed_password" not in resp.text
    assert target.hashed_password not in resp.text


def test_detail_404s_for_an_unknown_member(president_client):
    assert president_client.get("/admin/members/999999").status_code == 404


def test_a_regular_member_cannot_read_a_detail(client, session):
    target = member(session, "mateo")

    assert client.get(f"/admin/members/{target.id}").status_code == 403


def test_a_vp_can_read_a_detail(vp_client, session):
    # Same three-seat gate as the rest of the members page -- the VP limits
    # are on role ASSIGNMENT, not on reading the directory.
    target = member(session, "valeria")

    assert vp_client.get(f"/admin/members/{target.id}").status_code == 200


# --- resume ---------------------------------------------------------------

@pytest.fixture
def resume_dir(tmp_path, monkeypatch):
    """Point the admin route's module-level RESUME_DIR at a tmp_path, the
    same seam routes/resume_routes.py exposes."""
    import routes.admin_routes as admin_routes

    monkeypatch.setattr(admin_routes, "RESUME_DIR", tmp_path)
    return tmp_path


def test_president_can_download_a_members_resume(president_client, session, resume_dir):
    target = member(session, "renata", first_name="Renata", last_name="Quintero")
    target.resume_filename = "Renata_Quintero_1234567.pdf"
    session.add(target)
    session.commit()
    (resume_dir / f"user_{target.id}.pdf").write_bytes(b"%PDF-1.4 fake")

    resp = president_client.get(f"/admin/members/{target.id}/resume")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "Renata_Quintero_1234567.pdf" in resp.headers["content-disposition"]
    assert resp.content == b"%PDF-1.4 fake"


def test_resume_404s_when_the_member_has_none(president_client, session, resume_dir):
    target = member(session, "tomas")

    assert president_client.get(f"/admin/members/{target.id}/resume").status_code == 404


def test_resume_404s_when_the_row_points_at_a_missing_file(president_client, session, resume_dir):
    # resume_filename set but nothing on disk — a restored database without
    # the uploads volume. Must be a 404, not a 500.
    target = member(session, "paola")
    target.resume_filename = "Paola_Vargas_1111111.pdf"
    session.add(target)
    session.commit()

    assert president_client.get(f"/admin/members/{target.id}/resume").status_code == 404


def test_a_regular_member_cannot_download_someone_elses_resume(client, session, resume_dir):
    # The privacy narrowing stops at the three role-admin seats.
    target = member(session, "hector")
    target.resume_filename = "Hector_Rojas_2222222.pdf"
    session.add(target)
    session.commit()
    (resume_dir / f"user_{target.id}.pdf").write_bytes(b"%PDF-1.4 fake")

    assert client.get(f"/admin/members/{target.id}/resume").status_code == 403

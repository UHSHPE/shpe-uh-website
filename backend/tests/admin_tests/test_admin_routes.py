"""Chapter admin — member directory, stats, role assignment.

Reachable by the president and both VPs (ROLE_ADMIN_ROLES); VP-specific
limits around the presidency are covered at the bottom of this file.
"""

from models.committee import Committee, CommitteeMembership
from models.user.user_enums import Classification, Role, ShirtSize
from tests.admin_tests.conftest import make_dues_order
from tests.conftest import make_user


def make_member(session, tag, **overrides):
    """A distinct extra member — unique emails/psid derived from `tag` (1-9)."""
    fields = dict(
        first_name="Maria",
        last_name=f"Garcia{'A' * tag}"[:10],
        cougarnet_email=f"member{tag}@cougarnet.uh.edu",
        personal_email=f"member{tag}@gmail.com",
        psid=f"555000{tag}",
    )
    fields.update(overrides)
    return make_user(session, **fields)


def make_committee(session, name="Academic", chair_role=Role.academic_chair):
    committee = Committee(name=name, description="Test committee", chair_role=chair_role)
    session.add(committee)
    session.commit()
    session.refresh(committee)
    return committee


# --- access control ---

def test_admin_endpoints_reject_plain_members(client):
    # `client` is signed in as a plain member — every /admin call is 403.
    assert client.get("/admin/members").status_code == 403
    assert client.get("/admin/stats").status_code == 403
    assert client.get("/admin/roles").status_code == 403
    assert client.patch("/admin/members/1/role", json={"role": "Treasurer"}).status_code == 403


def test_president_has_shop_admin_access(president_client):
    assert president_client.get("/shop/admin/products").status_code == 200


def test_president_bypasses_chair_gate(president_client, session):
    committee = make_committee(session, name="Social", chair_role=Role.social_chair)
    assert president_client.get(f"/committees/{committee.id}/members").status_code == 200


def test_president_sees_manage_panel_on_every_committee(president_client, session):
    make_committee(session)
    make_committee(session, name="Social", chair_role=Role.social_chair)

    rows = president_client.get("/committees").json()

    assert len(rows) == 2
    assert all(row["is_chair"] for row in rows)


# --- member directory ---

def test_directory_lists_all_accounts_with_dues_status(president_client, session, president):
    member = make_member(session, 1)
    make_dues_order(session, member)

    rows = president_client.get("/admin/members").json()

    by_email = {row["cougarnet_email"] for row in rows}
    assert by_email == {president.cougarnet_email, member.cougarnet_email}
    status = {row["cougarnet_email"]: row["has_paid_dues"] for row in rows}
    assert status[member.cougarnet_email] is True
    assert status[president.cougarnet_email] is False


def test_directory_search_matches_name_email_and_psid(president_client, session):
    member = make_member(session, 1, first_name="Ximena")
    make_member(session, 2)

    for needle in ("ximena", "member1@cougarnet", "5550001"):
        rows = president_client.get("/admin/members", params={"search": needle}).json()
        assert [row["id"] for row in rows] == [member.id]


def test_directory_paid_and_role_filters(president_client, session, president):
    paid_member = make_member(session, 1)
    unpaid_member = make_member(session, 2)
    make_dues_order(session, paid_member)

    paid_rows = president_client.get("/admin/members", params={"paid": "true"}).json()
    assert [row["id"] for row in paid_rows] == [paid_member.id]

    unpaid_ids = {row["id"] for row in president_client.get("/admin/members", params={"paid": "false"}).json()}
    assert unpaid_ids == {president.id, unpaid_member.id}

    role_rows = president_client.get("/admin/members", params={"role": "President"}).json()
    assert [row["id"] for row in role_rows] == [president.id]


# --- stats ---

def test_stats_counts(president_client, session):
    paid_member = make_member(session, 1)
    make_member(
        session, 2,
        classification=Classification.freshman,
        shirt_size=ShirtSize.l,
        is_national_member=False,
    )
    make_dues_order(session, paid_member)

    stats = president_client.get("/admin/stats").json()

    assert stats["total_accounts"] == 3
    assert stats["dues_paid"] == 1
    assert stats["dues_unpaid"] == 2
    assert stats["national_members"] == 2
    assert stats["classification_counts"]["Freshman"] == 1
    assert stats["role_counts"]["President"] == 1
    assert stats["shirt_size_counts"] == {"M": 2, "L": 1}


def test_roles_endpoint_lists_every_role(president_client):
    roles = president_client.get("/admin/roles").json()
    assert roles == [role.value for role in Role]


# --- role assignment ---

def test_assign_role_updates_member(president_client, session):
    member = make_member(session, 1)

    res = president_client.patch(f"/admin/members/{member.id}/role", json={"role": "Treasurer"})

    assert res.status_code == 200
    assert res.json()["role"] == "Treasurer"
    session.refresh(member)
    assert member.role == Role.treasurer


def test_assigning_chair_role_creates_chair_membership(president_client, session):
    member = make_member(session, 1)
    committee = make_committee(session)

    res = president_client.patch(f"/admin/members/{member.id}/role", json={"role": "Academic Chair"})

    assert res.status_code == 200
    membership = session.get(CommitteeMembership, (member.id, committee.id))
    assert membership is not None
    assert membership.is_chair is True
    assert membership.status is True


def test_removing_chair_role_clears_chair_flag_but_keeps_membership(president_client, session):
    member = make_member(session, 1, role=Role.academic_chair)
    committee = make_committee(session)
    session.add(CommitteeMembership(
        user_id=member.id, committee_id=committee.id, status=True, is_chair=True,
    ))
    session.commit()

    res = president_client.patch(f"/admin/members/{member.id}/role", json={"role": "Member"})

    assert res.status_code == 200
    membership = session.get(CommitteeMembership, (member.id, committee.id))
    session.refresh(membership)
    assert membership.is_chair is False
    assert membership.status is True


def test_president_cannot_change_own_role(president_client, president):
    res = president_client.patch(f"/admin/members/{president.id}/role", json={"role": "Member"})
    assert res.status_code == 400


def test_assign_role_unknown_member_is_404(president_client):
    res = president_client.patch("/admin/members/9999/role", json={"role": "Member"})
    assert res.status_code == 404


def test_president_can_assign_the_presidency(president_client, session):
    # Handoff: two presidents coexist briefly, then the successor demotes you.
    member = make_member(session, 1)

    res = president_client.patch(f"/admin/members/{member.id}/role", json={"role": "President"})

    assert res.status_code == 200
    session.refresh(member)
    assert member.role == Role.president


# --- vice presidents share the tools, but not the presidency ---

def test_vp_can_use_the_directory(vp_client, session):
    make_member(session, 1)

    assert vp_client.get("/admin/members").status_code == 200
    assert vp_client.get("/admin/stats").status_code == 200
    assert vp_client.get("/admin/roles").status_code == 200


def test_vp_can_assign_an_ordinary_role(vp_client, session):
    member = make_member(session, 1)

    res = vp_client.patch(f"/admin/members/{member.id}/role", json={"role": "Treasurer"})

    assert res.status_code == 200
    session.refresh(member)
    assert member.role == Role.treasurer


def test_vp_assigning_chair_role_still_syncs_membership(vp_client, session):
    member = make_member(session, 1)
    committee = make_committee(session)

    res = vp_client.patch(f"/admin/members/{member.id}/role", json={"role": "Academic Chair"})

    assert res.status_code == 200
    membership = session.get(CommitteeMembership, (member.id, committee.id))
    assert membership is not None
    assert membership.is_chair is True


def test_vp_cannot_grant_the_presidency(vp_client, session):
    member = make_member(session, 1)

    res = vp_client.patch(f"/admin/members/{member.id}/role", json={"role": "President"})

    assert res.status_code == 403
    session.refresh(member)
    assert member.role == Role.member


def test_vp_cannot_change_the_sitting_president(vp_client, session):
    # Otherwise a VP could demote the president and leave nobody with full admin.
    from tests.admin_tests.conftest import make_president

    sitting = make_president(session)

    res = vp_client.patch(f"/admin/members/{sitting.id}/role", json={"role": "Member"})

    assert res.status_code == 403
    session.refresh(sitting)
    assert sitting.role == Role.president


def test_vp_cannot_change_own_role(vp_client, vp):
    res = vp_client.patch(f"/admin/members/{vp.id}/role", json={"role": "President"})
    assert res.status_code == 400


def test_roles_list_hides_president_from_vps(vp_client):
    roles = vp_client.get("/admin/roles").json()

    assert "President" not in roles
    assert "Treasurer" in roles


def test_roles_list_includes_president_for_the_president(president_client):
    assert "President" in president_client.get("/admin/roles").json()

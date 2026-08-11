"""The chapter reporting tree — /admin/structure.

The tree is organizational only. The last test in this file is the one that
matters most: it pins down that being someone's supervisor grants nothing.
"""

from sqlmodel import select

from models.role_report import RoleReport
from models.user.user_enums import Role
from tests.admin_tests.test_admin_routes import make_member


def node_for(rows, role_value):
    return next(n for n in rows if n["role"] == role_value)


# --- reading ---

def test_structure_lists_every_tier(president_client):
    rows = president_client.get("/admin/structure").json()

    tiers = {n["tier"] for n in rows}
    assert tiers == {"president", "vp", "officer", "chair"}
    # 1 president + 2 VPs + 6 officers + 14 chairs
    assert len(rows) == 23


def test_president_is_root_and_vps_report_to_them(president_client):
    rows = president_client.get("/admin/structure").json()

    assert node_for(rows, "President")["supervisor_role"] is None
    assert node_for(rows, "Vice President Internal")["supervisor_role"] == "President"


def test_unassigned_roles_report_null(president_client):
    # Nothing is seeded in the test DB, so every officer/chair starts empty.
    rows = president_client.get("/admin/structure").json()

    assert node_for(rows, "Treasurer")["supervisor_role"] is None
    assert node_for(rows, "Academic Chair")["supervisor_role"] is None


def test_structure_reports_who_holds_each_role(president_client, session):
    make_member(session, 1, role=Role.treasurer)

    rows = president_client.get("/admin/structure").json()

    holders = node_for(rows, "Treasurer")["holders"]
    assert len(holders) == 1
    assert holders[0]["last_name"].startswith("Garcia")
    assert node_for(rows, "Academic Chair")["holders"] == []


def test_co_chairs_both_appear_under_their_role(president_client, session):
    make_member(session, 1, role=Role.academic_chair)
    make_member(session, 2, role=Role.academic_chair)

    rows = president_client.get("/admin/structure").json()

    assert len(node_for(rows, "Academic Chair")["holders"]) == 2


# --- editing ---

def test_officer_can_be_assigned_to_a_vp(president_client, session):
    res = president_client.put("/admin/structure/Treasurer",
                               json={"supervisor_role": "Vice President External"})

    assert res.status_code == 200
    assert res.json()["supervisor_role"] == "Vice President External"
    assert session.get(RoleReport, Role.treasurer).supervisor_role == Role.vpe


def test_chair_can_be_assigned_to_an_officer(president_client):
    res = president_client.put("/admin/structure/Academic Chair",
                               json={"supervisor_role": "Treasurer"})

    assert res.status_code == 200
    assert res.json()["supervisor_role"] == "Treasurer"


def test_chair_can_be_assigned_directly_to_a_vp(president_client):
    res = president_client.put("/admin/structure/Academic Chair",
                               json={"supervisor_role": "Vice President Internal"})
    assert res.status_code == 200


def test_vps_can_edit_the_tree_too(vp_client):
    res = vp_client.put("/admin/structure/Secretary",
                        json={"supervisor_role": "Vice President Internal"})
    assert res.status_code == 200


def test_reassigning_updates_in_place(president_client, session):
    president_client.put("/admin/structure/Treasurer",
                         json={"supervisor_role": "Vice President External"})
    president_client.put("/admin/structure/Treasurer",
                         json={"supervisor_role": "Vice President Internal"})

    rows = session.exec(select(RoleReport)).all()
    assert len(rows) == 1                      # upsert, not a second row
    assert rows[0].supervisor_role == Role.vpi


# --- validation ---

def test_officer_cannot_report_to_a_chair(president_client):
    res = president_client.put("/admin/structure/Treasurer",
                               json={"supervisor_role": "Academic Chair"})
    assert res.status_code == 400


def test_chair_cannot_report_to_another_chair(president_client):
    res = president_client.put("/admin/structure/Academic Chair",
                               json={"supervisor_role": "Social Chair"})
    assert res.status_code == 400


def test_president_cannot_be_given_a_supervisor(president_client):
    res = president_client.put("/admin/structure/President",
                               json={"supervisor_role": "Vice President External"})
    assert res.status_code == 400


def test_vp_reporting_line_is_fixed(president_client):
    res = president_client.put("/admin/structure/Vice President External",
                               json={"supervisor_role": "Treasurer"})
    assert res.status_code == 400


def test_plain_member_is_not_part_of_the_tree(president_client):
    res = president_client.put("/admin/structure/Member",
                               json={"supervisor_role": "Treasurer"})
    assert res.status_code == 400


# --- access ---

def test_structure_requires_role_admin(client):
    assert client.get("/admin/structure").status_code == 403
    assert client.put("/admin/structure/Treasurer",
                      json={"supervisor_role": "Vice President External"}).status_code == 403


def test_supervising_grants_no_permissions(client, session):
    """The whole point of 'structure only'. An officer with a chair under them
    is still just an officer — if this ever fails, the tree has quietly become
    a permission system."""
    from services import structure_services

    officer = make_member(session, 1, role=Role.treasurer)
    structure_services.set_supervisor(session, Role.academic_chair, Role.treasurer)

    # `client` is a plain member; re-point it at the officer to act as them.
    from main import app
    from services.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: officer

    assert client.get("/admin/members").status_code == 403
    assert client.get("/admin/stats").status_code == 403
    assert client.get("/admin/structure").status_code == 403

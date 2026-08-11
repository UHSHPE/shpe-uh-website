"""The chapter reporting tree — president → VPs → officers → chairs.

This is organizational data only. Nothing here is consulted by any permission
check: an officer with ten chairs under them still has exactly the privileges
their Role grants. Role assignment stays gated by require_role_admin and
_assert_may_assign in routes/admin_routes.py. Keep it that way unless someone
deliberately decides to delegate, because "manager" silently becoming "can
edit" is the kind of thing nobody notices until it's abused.
"""

from fastapi import HTTPException, status
from sqlmodel import Session, select

from models.role_report import RoleHolderOut, RoleNodeOut, RoleReport
from models.user.user import User
from models.user.user_enums import (
    CHAIR_ROLES,
    OFFICER_ROLES,
    VP_ROLES,
    Role,
)

# Roles that occupy a slot in the tree, in Role-declaration order so the
# response reads president → VPs → officers → chairs without a sort key.
TREE_ROLES = [r for r in Role if r == Role.president or r in VP_ROLES
              or r in OFFICER_ROLES or r in CHAIR_ROLES]


def tier_of(role: Role) -> str | None:
    """Which layer a role sits on, or None if it isn't in the tree at all
    (Member and Nonmember)."""
    if role == Role.president:
        return "president"
    if role in VP_ROLES:
        return "vp"
    if role in OFFICER_ROLES:
        return "officer"
    if role in CHAIR_ROLES:
        return "chair"
    return None


def valid_supervisors(role: Role) -> set[Role]:
    """Who may sit above `role`. Empty means the link isn't editable —
    the president is the root, and VPs always report to the president."""
    tier = tier_of(role)
    if tier == "officer":
        return set(VP_ROLES)
    if tier == "chair":
        # Chairs usually hang off an officer, but a VP may take one directly.
        return set(VP_ROLES) | set(OFFICER_ROLES)
    return set()


def assert_valid_report(role: Role, supervisor_role: Role) -> None:
    """400 unless `supervisor_role` may supervise `role`. The tier rules make
    a cycle unreachable — every allowed edge points strictly upward — so there
    is no cycle check to maintain."""
    tier = tier_of(role)
    if tier is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{role.value} is not part of the reporting structure",
        )
    if tier == "president":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The president is the top of the structure and reports to nobody",
        )
    if tier == "vp":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vice presidents always report to the president",
        )

    allowed = valid_supervisors(role)
    if supervisor_role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{supervisor_role.value} can't supervise {role.value} — "
                f"a {tier} reports to "
                + ("a vice president" if tier == "officer"
                   else "a vice president or an e-board officer")
            ),
        )


def get_supervisor_map(session: Session) -> dict[Role, Role]:
    """Stored links only. VPs' implicit link to the president isn't a row."""
    return {row.role: row.supervisor_role for row in session.exec(select(RoleReport)).all()}


def get_structure(session: Session) -> list[RoleNodeOut]:
    """Every tree role with its supervisor and whoever currently holds it.
    Two queries total, regardless of chapter size."""
    stored = get_supervisor_map(session)

    holders: dict[Role, list[RoleHolderOut]] = {}
    for user in session.exec(select(User).order_by(User.last_name, User.first_name)).all():
        if tier_of(user.role) is not None:
            holders.setdefault(user.role, []).append(
                RoleHolderOut(id=user.id, first_name=user.first_name, last_name=user.last_name)
            )

    nodes = []
    for role in TREE_ROLES:
        tier = tier_of(role)
        if tier == "president":
            supervisor = None
        elif tier == "vp":
            supervisor = Role.president      # implicit, never stored
        else:
            supervisor = stored.get(role)    # None = not yet assigned
        nodes.append(RoleNodeOut(
            role=role,
            tier=tier,
            supervisor_role=supervisor,
            holders=holders.get(role, []),
        ))
    return nodes


def set_supervisor(session: Session, role: Role, supervisor_role: Role) -> RoleReport:
    """Upsert the link after validating it. Re-parenting the same role twice
    updates the row rather than adding one — `role` is the primary key."""
    assert_valid_report(role, supervisor_role)

    row = session.get(RoleReport, role)
    if row is None:
        row = RoleReport(role=role, supervisor_role=supervisor_role)
    else:
        row.supervisor_role = supervisor_role
    session.add(row)
    session.commit()
    session.refresh(row)
    return row

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from models.committee import Committee, CommitteeMembership
from models.user.user import User
from models.user.user_enums import Role
from models.user.user_schemas import AdminMemberOut, AdminRoleUpdate, AdminStatsOut
from services import shop_services
from services.dependencies import SessionDependencies, require_president

router = APIRouter(prefix="/admin", tags=["Admin"])


def _member_out(user: User, paid: bool) -> AdminMemberOut:
    out = AdminMemberOut.model_validate(user)
    out.has_paid_dues = paid
    return out


@router.get("/members", response_model=list[AdminMemberOut])
def list_members(
    president: Annotated[User, Depends(require_president)],
    session: SessionDependencies,
    search: str | None = None,
    paid: bool | None = None,
    role: Role | None = None,
):
    """The president's member directory — every account, with dues status.
    `search` matches name, either email, or PSID; `paid` filters on dues."""
    query = select(User).order_by(User.last_name, User.first_name)
    if role is not None:
        query = query.where(User.role == role)
    users = session.exec(query).all()

    if search and search.strip():
        needle = search.strip().lower()
        users = [
            u for u in users
            if needle in f"{u.first_name} {u.last_name}".lower()
            or needle in u.cougarnet_email.lower()
            or needle in u.personal_email.lower()
            or needle in u.psid
        ]

    paid_ids = shop_services.dues_paid_user_ids(session)
    rows = [_member_out(u, u.id in paid_ids) for u in users]
    if paid is not None:
        rows = [r for r in rows if r.has_paid_dues == paid]
    return rows


@router.get("/stats", response_model=AdminStatsOut)
def member_stats(
    president: Annotated[User, Depends(require_president)],
    session: SessionDependencies,
):
    """Chapter-wide account numbers for the members page tiles."""
    users = session.exec(select(User)).all()
    paid_ids = shop_services.dues_paid_user_ids(session)
    paid_count = sum(1 for u in users if u.id in paid_ids)

    return AdminStatsOut(
        total_accounts=len(users),
        dues_paid=paid_count,
        dues_unpaid=len(users) - paid_count,
        national_members=sum(1 for u in users if u.is_national_member),
        dues_period_start=shop_services.current_dues_period_start(),
        classification_counts=dict(Counter(u.classification.value for u in users)),
        role_counts=dict(Counter(u.role.value for u in users)),
        shirt_size_counts=dict(Counter(u.shirt_size.value for u in users)),
    )


@router.get("/roles", response_model=list[str])
def list_assignable_roles(president: Annotated[User, Depends(require_president)]):
    """Every assignable role value — keeps the frontend dropdown in sync
    with the Role enum instead of hardcoding the list."""
    return [role.value for role in Role]


def _sync_chair_memberships(session: Session, user: User, old_role: Role, new_role: Role) -> None:
    """Chair permissions need BOTH the role and an is_chair membership row
    (require_chair checks the role; rosters/notifications read the row) —
    keep the rows in step whenever a role change adds or drops a chair role."""
    if old_role == new_role:
        return

    # Demote: the committee the old role chaired (if any) loses this chair.
    # They stay a regular member of it rather than being removed outright.
    for committee in session.exec(select(Committee).where(Committee.chair_role == old_role)).all():
        membership = session.get(CommitteeMembership, (user.id, committee.id))
        if membership and membership.is_chair:
            membership.is_chair = False
            session.add(membership)

    # Promote: ensure an active is_chair membership for the new role's committee.
    for committee in session.exec(select(Committee).where(Committee.chair_role == new_role)).all():
        membership = session.get(CommitteeMembership, (user.id, committee.id))
        if membership:
            membership.status = True
            membership.is_chair = True
            session.add(membership)
        else:
            session.add(CommitteeMembership(
                user_id=user.id,
                committee_id=committee.id,
                status=True,
                is_chair=True,
            ))


@router.patch("/members/{user_id}/role", response_model=AdminMemberOut)
def assign_role(
    user_id: int,
    payload: AdminRoleUpdate,
    president: Annotated[User, Depends(require_president)],
    session: SessionDependencies,
):
    """Assign any role (e-board, chairs, member…). Chair-role changes also
    sync the committee's is_chair membership row. The president can't change
    their own role — hand off by promoting the incoming president first."""
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.id == president.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't change your own role. To hand off, promote the incoming president first.",
        )

    old_role = target.role
    target.role = payload.role
    session.add(target)
    _sync_chair_memberships(session, target, old_role, payload.role)
    session.commit()
    session.refresh(target)

    return _member_out(target, shop_services.has_paid_dues(session, target.id))

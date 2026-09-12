from collections import Counter
from pathlib import Path
from typing import Annotated

import config

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from models.committee import Committee, CommitteeMembership
from models.role_report import RoleNodeOut, RoleReportUpdate
from models.user.user import User
from models.user.user_enums import Role, TOP_TIER_ROLES
from models.user.multi_selections.user_country_origin import UserCountryOrigin
from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
from models.user.multi_selections.user_prof_dev import UserProfDev
from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
from models.user.user_schemas import (
    AdminMemberDetailOut,
    AdminMemberOut,
    AdminRoleUpdate,
    AdminStatsOut,
    MemberCommitteeOut,
)
from services import shop_services, structure_services, user_services
from services.dependencies import SessionDependencies, require_role_admin

router = APIRouter(prefix="/admin", tags=["Admin"])

# Re-exported as a module attribute rather than read as config.RESUME_DIR at
# the call site, matching routes/resume_routes.py — the resume tests
# monkeypatch this name to a tmp_path, and going through the config module
# would bypass the patch.
RESUME_DIR = config.RESUME_DIR


def _member_out(user: User, paid: bool) -> AdminMemberOut:
    out = AdminMemberOut.model_validate(user)
    out.has_paid_dues = paid
    return out


@router.get("/members", response_model=list[AdminMemberOut])
def list_members(
    actor: Annotated[User, Depends(require_role_admin)],
    session: SessionDependencies,
    search: str | None = None,
    paid: bool | None = None,
    role: Role | None = None,
):
    """The chapter member directory — every account, with dues status.
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


@router.get("/members/{user_id}", response_model=AdminMemberDetailOut)
def get_member(
    user_id: int,
    actor: Annotated[User, Depends(require_role_admin)],
    session: SessionDependencies,
):
    """One member's full profile — everything the signup form collected, plus
    their committees and whether a resume is on file.

    Declared BEFORE nothing in particular (it can't collide with /members,
    which has one fewer path segment) but note it DOES sit on the same prefix
    as /members/{user_id}/role — different method and depth, so no ordering
    discipline is needed here.
    """
    member = session.get(User, user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    countries = session.exec(
        select(UserCountryOrigin).where(UserCountryOrigin.user_id == member.id)
    ).all()
    industries = session.exec(
        select(UserInterestedIndustries).where(UserInterestedIndustries.user_id == member.id)
    ).all()
    prof_devs = session.exec(
        select(UserProfDev).where(UserProfDev.user_id == member.id)
    ).all()
    races = session.exec(
        select(UserRaceEthnicity).where(UserRaceEthnicity.user_id == member.id)
    ).all()

    memberships = session.exec(
        select(CommitteeMembership, Committee)
        .join(Committee, Committee.id == CommitteeMembership.committee_id)
        .where(
            CommitteeMembership.user_id == member.id,
            CommitteeMembership.status == True,  # noqa: E712
        )
        .order_by(Committee.name)
    ).all()

    detail = AdminMemberDetailOut.model_validate(member)
    detail.has_paid_dues = shop_services.has_paid_dues(session, member.id)
    detail.country_origin = [c.country_origin for c in countries]
    detail.interested_industries = [i.interested_industry for i in industries]
    detail.prof_dev = [p.prof_dev for p in prof_devs]
    detail.race_and_ethnicity = [r.race_and_ethnicity for r in races]
    detail.committees = [
        MemberCommitteeOut(id=committee.id, name=committee.name, is_chair=membership.is_chair)
        for membership, committee in memberships
    ]
    return detail


@router.get("/members/{user_id}/resume")
def download_member_resume(
    user_id: int,
    actor: Annotated[User, Depends(require_role_admin)],
    session: SessionDependencies,
):
    """A member's resume PDF, for the president and both VPs.

    This is a deliberate narrowing of "resumes are private to the owner":
    the resume book is a chapter asset the officers running it have to be
    able to open, and require_role_admin is the same three-seat gate as the
    rest of the members page. It is read-only on purpose — there is no admin
    upload or delete, so the member stays the only one who can change or
    remove their own file (and the Drive mirror stays in step with them).
    Chairs are NOT included; widening past the three seats should be a
    deliberate decision, not a side effect of adding a role.
    """
    member = session.get(User, user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    path = Path(RESUME_DIR) / f"user_{member.id}.pdf"
    if not member.resume_filename or not path.exists():
        raise HTTPException(status_code=404, detail="No resume on file")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=member.resume_filename,
    )


@router.get("/stats", response_model=AdminStatsOut)
def member_stats(
    actor: Annotated[User, Depends(require_role_admin)],
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
def list_assignable_roles(actor: Annotated[User, Depends(require_role_admin)]):
    """Every role the caller may assign — keeps the frontend dropdown in sync
    with the Role enum instead of hardcoding the list. VPs don't get the top
    tier, so the dropdown can't offer a pick that assign_role would reject."""
    roles = [role.value for role in Role]
    if actor.role != Role.president:
        blocked = {role.value for role in TOP_TIER_ROLES}
        roles = [role for role in roles if role not in blocked]
    return roles


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


def _assert_may_assign(actor: User, target: User, new_role: Role) -> None:
    """The president may assign anything. A VP may not grant a top-tier role
    nor modify anyone holding one — the president manages the presidency and
    both VP seats. Without the second rule a VP could demote the president (or
    the other VP) unilaterally; without the first they could mint a peer, which
    is the same power one step removed."""
    if actor.role == Role.president:
        return
    if new_role in TOP_TIER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the president can assign the President or VP roles",
        )
    if target.role in TOP_TIER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the president can change a president's or VP's role",
        )


@router.patch("/members/{user_id}/role", response_model=AdminMemberOut)
def assign_role(
    user_id: int,
    payload: AdminRoleUpdate,
    actor: Annotated[User, Depends(require_role_admin)],
    session: SessionDependencies,
):
    """Assign any role (e-board, chairs, member…). Chair-role changes also
    sync the committee's is_chair membership row. Nobody can change their own
    role — hand off by promoting the incoming president first."""
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't change your own role. To hand off, promote the incoming president first.",
        )
    _assert_may_assign(actor, target, payload.role)

    old_role = target.role
    target.role = payload.role
    session.add(target)
    _sync_chair_memberships(session, target, old_role, payload.role)
    session.commit()
    session.refresh(target)

    # After the commit, so the notice reflects live roles. Called as a module
    # attribute so tests can monkeypatch it. Best-effort inside — a mail outage
    # must not fail a role change that already succeeded. This route is a sync
    # `def`, so the blocking smtplib call runs in FastAPI's threadpool, not on
    # the event loop.
    if old_role != payload.role:
        user_services.notify_role_change(
            session, target, old_role, payload.role,
            f"{actor.first_name} {actor.last_name}",
        )

    return _member_out(target, shop_services.has_paid_dues(session, target.id))


# --- reporting structure (organizational only — grants no permissions) ---

@router.get("/structure", response_model=list[RoleNodeOut])
def get_structure(
    actor: Annotated[User, Depends(require_role_admin)],
    session: SessionDependencies,
):
    """The chapter org chart: every tree role with its supervisor and whoever
    holds it. Roles with `supervisor_role: null` haven't been assigned yet."""
    return structure_services.get_structure(session)


@router.put("/structure/{role}", response_model=RoleNodeOut)
def set_role_supervisor(
    role: Role,
    payload: RoleReportUpdate,
    actor: Annotated[User, Depends(require_role_admin)],
    session: SessionDependencies,
):
    """Re-parent a role. Officers report to a VP; chairs report to a VP or an
    officer; the president and the VP seats aren't editable (400). President
    and VPs may both edit the tree."""
    structure_services.set_supervisor(session, role, payload.supervisor_role)

    node = next(n for n in structure_services.get_structure(session) if n.role == role)
    return node

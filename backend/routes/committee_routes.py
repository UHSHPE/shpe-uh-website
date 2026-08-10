from services.committee_services import chair_contact_email, get_chair_users_from_committee_id, is_active_member
from models.committee import ChairOut, Committee, CommitteeMembership, CommitteeOut, MemberOut
from models.committee_message import CommitteeMessage, CommitteeMessageCreate, CommitteeMessageOut
from models.notification import Notification
from models.user.user import User
from models.user.user_enums import Role
from services.committee_services import get_committee_or_404, require_chair
from services.committee_services import get_all_committees
from services.committee_services import get_active_memberships_from_user_id
from services.dependencies import SessionDependencies, get_current_user
from services.rate_limit import join_budget_exhausted, record_join


from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select


from typing import Annotated

from services.user_services import get_user_by_user_id

router = APIRouter(prefix="/committees", tags=["Committee"])

@router.get('', response_model=list[CommitteeOut])
async def get_committees(
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):  
    committees = get_all_committees(session)
    memberships = get_active_memberships_from_user_id(user.id, session)

    membership_committee_ids = {membership.committee_id for membership in memberships}
    chair_committee_ids = {membership.committee_id for membership in memberships if membership.is_chair}
    # The president can manage every committee (require_chair lets them
    # through), so surface the manage panel on every card.
    is_president = user.role == Role.president

    result = []
    for committee in committees:
        chair_users = get_chair_users_from_committee_id(session, committee.id)

        chairs = [
            ChairOut(
                first_name=chair_user.first_name,
                last_name=chair_user.last_name,
                personal_email=chair_contact_email(committee, chair_user)
            )
            for chair_user in chair_users
        ]

        result.append(
            CommitteeOut(
                id=committee.id,
                name=committee.name,
                description=committee.description,
                is_member=committee.id in membership_committee_ids,
                is_chair=is_president or committee.id in chair_committee_ids,
                chairs=chairs
            )
        )
    
    return result

@router.post('/{committee_id}/join')
async def join_committee(
    committee_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    committee = get_committee_or_404(session, committee_id)

    # joinable=False rows exist only so EventHost can point at an officer seat.
    # get_all_committees() keeps them off /committees, but hiding is not
    # enforcement: committee_id is a bare path int and the ids are contiguous
    # (seed.py creates the 14 real committees before the 10 E-Board rows), so
    # they are trivially walked. The check lives here rather than in
    # get_committee_or_404 because its two other callers are chair-only and
    # officers legitimately chair E-Board rows -- a blanket refusal in the
    # resolver would lock the VPE out of their own seat.
    #
    # 404, not 403: a 403 confirms the row exists and is special, which is an
    # enumeration oracle for rows the listing deliberately hides. Same rule as
    # the shop order lookup's single generic 404.
    if not committee.joinable:
        raise HTTPException(status_code=404, detail="Committee not found")

    existing_membership = session.exec(
        select(CommitteeMembership).where(
            CommitteeMembership.user_id == user.id,
            CommitteeMembership.committee_id == committee_id,
        )
    ).first()
    
    # Already a member: a repeat join is a no-op, NOT a fresh one. Falling
    # through would re-emit the welcome notification plus one per chair on every
    # POST, against a table nothing prunes and a /notifications endpoint that
    # returns a member's whole history -- i.e. one member could permanently bury
    # a chair's feed. Returns the success body: it is idempotent, not an error.
    #
    # Guarded on status as well as existence. Nothing sets status False today
    # (leave_committee hard-deletes), so this reads as redundant -- it keeps the
    # reactivation branch below correct if leave ever becomes a soft delete.
    if existing_membership and existing_membership.status:
        return {"ok": True}

    # Only a join that actually writes notifications spends budget, which is why
    # this sits below the early return and uses the manual budget rather than a
    # @limiter.limit decorator. Per-account, so campus NAT can't dilute it.
    if join_budget_exhausted(user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You've joined too many committees recently. Try again later.",
        )

    if existing_membership:
        existing_membership.status = True
        session.add(existing_membership)
    else:
        session.add(
            CommitteeMembership(
                user_id=user.id,
                committee_id=committee_id,
                status=True
            )
        )

    # Welcome notification for the joining member
    session.add(Notification(
        user_id=user.id,
        body=f"Welcome to the {committee.name} committee!",
        committee_id=committee_id,
    ))

    # Notify the chairs (excluding the joiner if they are one)
    chairs = get_chair_users_from_committee_id(session, committee_id)

    for chair in chairs:
        if chair.id == user.id:
            continue

        session.add(Notification(
            user_id=chair.id,
            body=f"{user.first_name} {user.last_name} joined your {committee.name} committee",
            committee_id=committee_id,
        ))

    session.commit()
    record_join(user.id)
    return {"ok": True}


@router.delete('/{committee_id}/leave', status_code=204)
async def leave_committee(
    committee_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    existing_membership = session.exec(
        select(CommitteeMembership).where(
            CommitteeMembership.user_id == user.id,
            CommitteeMembership.committee_id == committee_id,
        )
    ).first()
    
    if not existing_membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    
    session.delete(existing_membership)
    session.commit()


@router.get('/{committee_id}/members', response_model=list[MemberOut])
async def get_committee_members(
    committee_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    committee = get_committee_or_404(session, committee_id)
    require_chair(committee, user)

    # Gets all members who are not a chair for that committee
    members = session.exec(
        select(User)
        .join(CommitteeMembership, CommitteeMembership.user_id == User.id)
        .where(
            CommitteeMembership.committee_id == committee_id,
            CommitteeMembership.status == True,  # noqa: E712
            CommitteeMembership.is_chair == False
        )
    ).all()
    
    return [
        MemberOut(
            id=member.id,
            first_name=member.first_name,
            last_name=member.last_name,
            personal_email=member.personal_email,
            phone_num=member.phone_num,
        )
        for member in members
    ]


@router.post('/{committee_id}/messages', response_model=CommitteeMessageOut)
async def send_committee_message(
    committee_id: int,
    message_in: CommitteeMessageCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    committee = get_committee_or_404(session, committee_id)
    require_chair(committee, user)

    body = message_in.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    message = CommitteeMessage(committee_id=committee_id, sender_id=user.id, body=body)
    session.add(message)

    members = session.exec(
        select(CommitteeMembership).where(
            CommitteeMembership.committee_id == committee_id,
            CommitteeMembership.status == True,  # noqa: E712
            CommitteeMembership.is_chair == False
        )
    ).all()
    preview = body[:80]
    for member in members:
        if member.user_id == user.id:
            continue
        
        session.add(Notification(
            user_id=member.user_id,
            body=f"New message in {committee.name}: {preview}",
            committee_id=committee_id,
        ))

    session.commit()
    session.refresh(message)
    return CommitteeMessageOut(
        id=message.id,
        committee_id=message.committee_id,
        sender_name=f"{user.first_name} {user.last_name}",
        body=message.body,
        created_at=message.created_at,
    )


@router.get('/{committee_id}/messages', response_model=list[CommitteeMessageOut])
async def get_committee_messages(
    committee_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    # Bare session.get, NOT get_committee_or_404: this route answers 403 for an
    # unknown id today, which is maximally opaque, and routing it through the
    # resolver would downgrade that to a 404 that reveals nonexistence. Folding
    # the missing case into the same 403 below keeps unknown, non-joinable and
    # non-member indistinguishable.
    committee = session.get(Committee, committee_id)
    chair_users = get_chair_users_from_committee_id(session, committee_id)
    # The president can read any committee's messages, like a chair.
    is_chair = user.role == Role.president or any(chair.id == user.id for chair in chair_users)

    # Membership alone is not enough on a joinable=False row. Refusing the join
    # is prospective only -- any row already in the table keeps passing this
    # gate forever, and two sources produce them: a join forged before that
    # check existed, and the demote branch in admin_routes._sync_chair_memberships,
    # which clears is_chair but leaves status=True, so an ex-officer keeps an
    # active non-chair row on their old E-Board seat. The two are byte-identical,
    # so they cannot be told apart by row shape -- gating the read neutralizes
    # both at once with no data migration. Chairs and the president pass above.
    if not is_chair and not (
        committee and committee.joinable and is_active_member(session, committee_id, user.id)
    ):
        raise HTTPException(status_code=403, detail="You are not a member of this committee")

    messages = session.exec(
        select(CommitteeMessage)
        .where(CommitteeMessage.committee_id == committee_id)
        .order_by(CommitteeMessage.created_at.desc())
    ).all()

    senders = {}
    out = []
    for msg in messages:
        sender = senders.get(msg.sender_id)
        
        if sender is None:
            sender = get_user_by_user_id(session, msg.sender_id)
            senders[msg.sender_id] = sender
            
        sender_name = f"{sender.first_name} {sender.last_name}" if sender else "Unknown"
        
        out.append(CommitteeMessageOut(
            id=msg.id,
            committee_id=msg.committee_id,
            sender_name=sender_name,
            body=msg.body,
            created_at=msg.created_at,
        ))
        
    return out
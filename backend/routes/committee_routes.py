from services.committee_services import chair_contact_email, get_chair_users_from_committee_id, is_active_member
from models.committee import ChairOut, CommitteeMembership, CommitteeOut, MemberOut
from models.committee_message import CommitteeMessage, CommitteeMessageCreate, CommitteeMessageOut
from models.notification import Notification
from models.user.user import User
from models.user.user_enums import Role
from services.committee_services import get_committee_or_404, require_chair
from services.committee_services import get_all_committees
from services.committee_services import get_active_memberships_from_user_id
from services.dependencies import SessionDependencies, get_current_user


from fastapi import APIRouter, Depends, HTTPException
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
    
    existing_membership = session.exec(
        select(CommitteeMembership).where(
            CommitteeMembership.user_id == user.id,
            CommitteeMembership.committee_id == committee_id,
        )
    ).first()
    
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
    chair_users = get_chair_users_from_committee_id(session, committee_id)
    # The president can read any committee's messages, like a chair.
    is_chair = user.role == Role.president or any(chair.id == user.id for chair in chair_users)

    if not is_chair and not is_active_member(session, committee_id, user.id):
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
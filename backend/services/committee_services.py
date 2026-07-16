from sqlmodel import Session, select
from fastapi import HTTPException

from models.committee import Committee, CommitteeMembership
from models.user.user import User
from models.user.user_enums import Role


# Committee role-based contact emails (shared by every co-chair of that role).
# Committees with no published role address fall back to the chair's own email.
CHAIR_EMAILS: dict[Role, str] = {
    Role.academic_chair: "academics@shpeuhchair.org",
    Role.athletic_chair: "Athletic.and.Wellness@shpeuhchair.org",
    Role.career_fair_chair: "Career.Fair@shpeuhchair.org",
    Role.eec_chair: "Engineering.Events.Coordinator@shpeuhchair.org",
    Role.marketing_chair: "Marketing@shpeuhchair.org",
    Role.mentorshpe_chair: "MentorSHPE@shpeuhchair.org",
    Role.projects_chair: "projects@shpeuhchair.org",
    Role.outreach_chair: "Outreach@shpeuhchair.org",
    Role.professional_chair: "Professional@shpeuhchair.org",
    Role.shpe_jr_chair: "SHPE.Jr@shpeuhchair.org",
    Role.social_chair: "Social@shpeuhchair.org",
    Role.shpetina_chair: "shpetina@shpeuhchair.org",
    Role.web_dev_chair: "Web.Dev@shpeuhchair.org",
    Role.member_relations_chair: "Member.Relations@shpeuhchair.org",
}


def chair_contact_email(committee: Committee, chair_user: User) -> str:
    """Public contact email for a committee's chairs.

    Co-chairs share one role-based address (see CHAIR_EMAILS). Any committee
    without a published role address falls back to the chair's own personal
    email so members still have a way to reach them.
    """
    return CHAIR_EMAILS.get(committee.chair_role) or chair_user.personal_email


def get_committee_or_404(session, committee_id: int) -> Committee:
    committee = session.get(Committee, committee_id)
    if not committee:
        raise HTTPException(status_code=404, detail="Committee not found")
    return committee


def require_chair(committee: Committee, user: User) -> None:
    if committee.chair_role is None or user.role != committee.chair_role:
        raise HTTPException(status_code=403, detail="Only this committee's chair can do that")


def is_active_member(session, committee_id: int, user_id: int) -> bool:
    membership = session.exec(
        select(CommitteeMembership).where(
            CommitteeMembership.user_id == user_id,
            CommitteeMembership.committee_id == committee_id,
            CommitteeMembership.status == True,  # noqa: E712
        )
    ).first()
    return membership is not None


def get_all_committees(session):
    return session.exec(
        select(Committee)
    ).all()


def get_active_memberships_from_user_id(user_id, session):
    return session.exec(
        select(CommitteeMembership).where(
            CommitteeMembership.user_id == user_id,
            CommitteeMembership.status == True
        )
    ).all()


def get_chair_memberships_from_committee_id(session, committee_id):
    return session.exec(
            select(CommitteeMembership).where(
                CommitteeMembership.committee_id == committee_id,
                CommitteeMembership.is_chair == True  # noqa: E712
            )
        ).all()


def get_chair_users_from_committee_id(session: Session, committee_id: int) -> list[User]:
    chair_memberships = get_chair_memberships_from_committee_id(session, committee_id)

    users = [session.get(User, membership.user_id) for membership in chair_memberships]
    return [user for user in users if user]

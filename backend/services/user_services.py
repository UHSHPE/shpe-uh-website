import logging

from models.user.multi_selections.user_country_origin import UserCountryOrigin
from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
from models.user.multi_selections.user_prof_dev import UserProfDev
from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
from models.user.user import User
from models.user.user_schemas import UserCreate
from models.user.user_enums import Role, TOP_TIER_ROLES
from security.hashing import get_password_hash
from services.email_services import send_email


from sqlmodel import Session, select

logger = logging.getLogger(__name__)


def create_user(session: Session, user_data: UserCreate, role: Role = Role.member):
    # role/points are set here, never taken from the request schema — a signup
    # body must never be able to choose its own role. Kept in the exclude set as
    # defense-in-depth in case either is ever re-added to UserBase.
    excluded_fields = {"password", "country_origin", "interested_industries",
                       "prof_dev", "race_and_ethnicity", "role", "points"}
    user_db = User(**user_data.model_dump(exclude=excluded_fields),
                   role=role,
                   hashed_password=get_password_hash(user_data.password))

    session.add(user_db)
    session.commit()
    session.refresh(user_db)

    for value in user_data.race_and_ethnicity:
        session.add(UserRaceEthnicity(user_id=user_db.id, race_and_ethnicity=value))
    for value in user_data.prof_dev:
        session.add(UserProfDev(user_id=user_db.id, prof_dev=value))
    for value in user_data.interested_industries:
        session.add(UserInterestedIndustries(user_id=user_db.id, interested_industry=value))
    for value in user_data.country_origin:
        session.add(UserCountryOrigin(user_id=user_db.id, country_origin=value))

    session.commit()

    return user_db


def get_user_by_email(session: Session, email: str) -> User | None:
    statement = select(User).where(User.cougarnet_email == email)
    user = session.exec(statement).first()
    return user

def get_user_by_psid(session: Session, psid: str) -> User | None:
    statement = select(User).where(User.psid == psid)
    user = session.exec(statement).first()
    return user

def get_user_by_user_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def notify_role_change(
    session: Session,
    target: User,
    old_role: Role,
    new_role: Role,
    actor_name: str,
) -> int:
    """Tell every sitting president/VP that somebody's role changed.

    This is a DETECTION control, not a prevention one. Anyone who can reach the
    database or the SECRET_KEY can escalate privileges without going through
    assign_role at all (a forged JWT leaves no row behind), so the realistic
    goal is that a privilege change can't happen *quietly* — not that it can't
    happen. Recipients are the top tier because they're the only people who can
    undo a role change.

    Call AFTER the change is committed: the recipient query reads live roles, so
    a newly-promoted president is already in the tier. `target` is excluded —
    they don't need to be told what was just done to their own account, and it
    keeps a self-promotion from mailing only the self-promoter.

    Best-effort by design: returns the number of recipients mailed and never
    raises. A mail outage must not fail the role change that triggered it.
    """
    recipients = [
        u for u in session.exec(select(User).where(User.role.in_(list(TOP_TIER_ROLES)))).all()
        if u.id != target.id
    ]
    if not recipients:
        # Normal on the very first bootstrap promotion — nobody holds the tier yet.
        logger.info("Role change for %s: no top-tier holders to notify.", target.cougarnet_email)
        return 0

    subject = f"SHPE UH — role changed: {target.first_name} {target.last_name}"
    body = (
        f"{target.first_name} {target.last_name} ({target.cougarnet_email}) "
        f"was changed from {old_role.value} to {new_role.value}.\n\n"
        f"Changed by: {actor_name}\n\n"
        "If you did not expect this, review the member directory at /members "
        "and change the role back.\n\n"
        "— SHPE UH website"
    )

    sent = 0
    for admin in recipients:
        try:
            if send_email(admin.personal_email, subject, body):
                sent += 1
            else:
                logger.warning("Role-change notice to %s failed to send.", admin.personal_email)
        except Exception:
            logger.exception("Role-change notice to %s raised.", admin.personal_email)
    return sent

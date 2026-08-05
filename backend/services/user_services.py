from models.user.multi_selections.user_country_origin import UserCountryOrigin
from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
from models.user.multi_selections.user_prof_dev import UserProfDev
from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
from models.user.user import User
from models.user.user_schemas import UserCreate
from security.hashing import get_password_hash


from sqlmodel import Session, select


def create_user(session: Session, user_data: UserCreate):
    excluded_fields = {"password", "country_origin", "interested_industries", "prof_dev", "race_and_ethnicity"}
    user_db = User(**user_data.model_dump(exclude=excluded_fields), hashed_password=get_password_hash(user_data.password))

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

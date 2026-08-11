from sqlmodel import Session

from models.user.user import User
from security.hashing import verify_password
from .user_services import get_user_by_email

def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(session, email)

    if not user or not verify_password(password, user.hashed_password):
        return None

    return user

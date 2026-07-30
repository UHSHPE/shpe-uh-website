from datetime import datetime, timezone
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlmodel import Session
import jwt
from jwt.exceptions import InvalidTokenError

from fastapi.security import OAuth2PasswordBearer

from security.jwt import oauth2_scheme, SECRET_KEY, ALGORITHM, TokenData
from services.user_services import get_user_by_email
from database import get_session

SessionDependencies = Annotated[Session, Depends(get_session)]

# Like oauth2_scheme but returns None instead of raising 401 when no token is
# sent — for public endpoints that behave slightly differently when logged in.
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDependencies):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        if email is None:
            raise credentials_exception

        token_data = TokenData(email=email)

    except InvalidTokenError:
        raise credentials_exception

    user = get_user_by_email(session, token_data.email)

    if user is None:
        raise credentials_exception

    # A password reset invalidates every token issued before it. PyJWT floors
    # iat to whole seconds while password_changed_at keeps microseconds, so
    # compare at whole-second granularity with strict < — a token issued in
    # the same second as the reset stays valid.
    if user.password_changed_at is not None:
        iat = payload.get("iat")
        if iat is None:
            raise credentials_exception
        issued_at = datetime.fromtimestamp(int(iat), tz=timezone.utc).replace(tzinfo=None)
        if issued_at < user.password_changed_at.replace(microsecond=0):
            raise credentials_exception

    return user


def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_scheme_optional)],
    session: SessionDependencies,
):
    """Current user if a valid bearer token was sent, else None. Used by public
    shop endpoints so a logged-in buyer's order links to their account."""
    if token is None:
        return None
    try:
        return get_current_user(token, session)
    except HTTPException:
        return None


def require_shop_admin(user=Depends(get_current_user)):
    """Gate for shop-admin endpoints — mirrors the committee require_chair
    pattern. Shop admin is held by the comms director, marketing chair,
    and the president."""
    from models.user.user_enums import SHOP_ADMIN_ROLES

    if user.role not in SHOP_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only shop admins can do that",
        )
    return user


def require_president(user=Depends(get_current_user)):
    """Gate for chapter-admin endpoints (member directory, stats, role
    assignment). Only the president holds these."""
    from models.user.user_enums import Role

    if user.role != Role.president:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the chapter president can do that",
        )
    return user
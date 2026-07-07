from datetime import datetime, timezone
from typing import Annotated
from fastapi import Depends, HTTPException, status
from sqlmodel import Session
import jwt
from jwt.exceptions import InvalidTokenError

from security.jwt import oauth2_scheme, SECRET_KEY, ALGORITHM, TokenData
from services.user_services import get_user_by_email
from database import get_session

SessionDependencies = Annotated[Session, Depends(get_session)]

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
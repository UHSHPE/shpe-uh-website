from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import select, SQLModel

from models.user.multi_selections.user_country_origin import UserCountryOrigin
from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
from models.user.multi_selections.user_prof_dev import UserProfDev
from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
from models.user.user import User
from models.user.user_schemas import UserCreate, UserOut
from security.jwt import ACCESS_TOKEN_EXPIRE_MINUTES, Token, create_access_token
from services import shop_services
from services.auth_user import authenticate_user
from services.user_services import create_user, get_user_by_user_id
from services.dependencies import SessionDependencies, get_current_user
from services.rate_limit import limiter
from services.user_services import get_user_by_email
from validators.email import normalize_email
from fastapi.security import OAuth2PasswordRequestForm
from services.pw_reset_services import generate_reset_token, hash_reset_token
from models.user.email_verification import EmailVerificationToken
from models.user.pw_reset_token import PasswordResetToken
from services.email_services import send_email
from services.time_services import utcnow
import os
from dotenv import load_dotenv

load_dotenv()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


router = APIRouter(tags=["Auth"])

class EmailVerifyConfirm(SQLModel):
    token: str


def _delete_unverified_user(session, user: User) -> None:
    """Remove a pending (unverified) account and everything foreign-keyed to it
    so a re-signup for the same email starts clean. SQLite doesn't cascade and
    reuses row ids, so leftover child rows would otherwise attach to the next
    user created with the reclaimed id."""
    for model in (
        UserRaceEthnicity,
        UserInterestedIndustries,
        UserProfDev,
        UserCountryOrigin,
        EmailVerificationToken,
        PasswordResetToken,
    ):
        for row in session.exec(select(model).where(model.user_id == user.id)).all():
            session.delete(row)
    session.delete(user)
    session.commit()

@router.post("/login")
@limiter.limit("5/minute")
async def login_for_token(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDependencies) -> Token:
    email = normalize_email(form_data.username)
    user = authenticate_user(session, email, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first. Check your inbox.")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.cougarnet_email}, expires_delta=access_token_expires)
    return Token(access_token=access_token, token_type="bearer")

@router.get('/me', response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)], session: SessionDependencies):
    race = session.exec(select(UserRaceEthnicity).where(UserRaceEthnicity.user_id == user.id)).all()
    industries = session.exec(select(UserInterestedIndustries).where(UserInterestedIndustries.user_id == user.id)).all()
    prof_devs = session.exec(select(UserProfDev).where(UserProfDev.user_id == user.id)).all()
    countries = session.exec(select(UserCountryOrigin).where(UserCountryOrigin.user_id == user.id)).all()
    return UserOut(
        **user.model_dump(),
        race_and_ethnicity=[r.race_and_ethnicity for r in race],
        interested_industries=[i.interested_industry for i in industries],
        prof_dev=[p.prof_dev for p in prof_devs],
        country_origin=[c.country_origin for c in countries],
        has_paid_dues=shop_services.has_paid_dues(session, user.id),
    )

# Creates user form sign up
@router.post('/signup', status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def signup(request: Request, user_in: UserCreate, session: SessionDependencies):
    email = normalize_email(user_in.cougarnet_email)
    existing = get_user_by_email(session, email)

    if existing:
        if existing.email_verified:
            # Only a *verified* account blocks re-registration.
            raise HTTPException(status_code=409, detail="Email is already registered")
        # Unverified squat: discard the pending account (and its child rows) and
        # re-issue a fresh token. Re-submitting signup doubles as "resend link".
        _delete_unverified_user(session, existing)

    user_db = create_user(session, user_in)
    raw, hashed = generate_reset_token()
    session.add(EmailVerificationToken(
        user_id=user_db.id, token_hash=hashed,
        expires_at=utcnow() + timedelta(hours=24),
    ))
    session.commit()

    link = f"{FRONTEND_URL}/verify-email?token={raw}"
    send_email(user_db.cougarnet_email, "Verify your SHPE UH account",
               f"Hi {user_db.first_name}, confirm your account:\n\n{link}\n\nThis link expires in 24 hours.")

    return {"detail": "Check your CougarNet email to verify your account."}

@router.post('/verify-email')
async def verify_email(req: EmailVerifyConfirm, session: SessionDependencies):
    invalid = HTTPException(status_code=400, detail="Invalid or expired token")
    db_token = session.exec(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_reset_token(req.token))
    ).first()
    if db_token is None or db_token.used_at is not None or db_token.expires_at <= utcnow():
        raise invalid

    user = get_user_by_user_id(session, db_token.user_id)
    # The token's user can be gone (e.g. a stale link after the account was
    # reclaimed by a later signup) — treat that as an invalid token.
    if user is None:
        raise invalid

    user.email_verified = True
    db_token.used_at = utcnow()
    session.add(user)
    session.add(db_token)
    session.commit()

    # Verified — now safe to issue the login token.
    access_token = create_access_token(
        data={"sub": user.cougarnet_email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, token_type="bearer")

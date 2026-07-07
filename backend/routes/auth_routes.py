from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import select

from models.user.multi_selections.user_country_origin import UserCountryOrigin
from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
from models.user.multi_selections.user_prof_dev import UserProfDev
from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
from models.user.user import User
from models.user.user_schemas import UserCreate, UserOut
from security.jwt import ACCESS_TOKEN_EXPIRE_MINUTES, Token, create_access_token
from services.auth_user import authenticate_user
from services.user_services import create_user
from services.dependencies import SessionDependencies, get_current_user
from services.rate_limit import limiter
from services.user_services import get_user_by_email
from validators.email import normalize_email
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(tags=["Auth"])

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
    )

# Creates user form sign up
@router.post('/signup', status_code=status.HTTP_201_CREATED)
async def signup(user_in: UserCreate, session: SessionDependencies):
    existing_user = get_user_by_email(session, normalize_email(user_in.cougarnet_email))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered"
        )


    user_db = create_user(session, user_in)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user_db.cougarnet_email}, expires_delta=access_token_expires)

    return Token(access_token=access_token, token_type="bearer")
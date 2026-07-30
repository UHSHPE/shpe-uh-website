import asyncio
import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import field_validator
from services import hibp_services
from services.dependencies import SessionDependencies
from services.rate_limit import limiter
from validators.email import normalize_email
from services.user_services import get_user_by_email, get_user_by_user_id
from services.pw_reset_services import generate_reset_token, hash_reset_token
from services.time_services import utcnow
from services.email_services import send_email
from security.hashing import get_password_hash
from datetime import timedelta
from sqlmodel import select, SQLModel
from models.user.pw_reset_token import PasswordResetToken
from models.user.user_schemas import validate_password_strength

load_dotenv()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

RESET_TOKEN_TTL = timedelta(hours=1)

class PasswordResetRequest(SQLModel):
    email: str

class PasswordResetConfirm(SQLModel):
    token: str
    new_password: str

    @field_validator("new_password", mode="before")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(str(v))

router = APIRouter(prefix="/password-reset", tags=["PasswordReset"])

@router.post("/request")
@limiter.limit("3/hour")
async def request_password_reset(request: Request, req: PasswordResetRequest, session: SessionDependencies):
    email = normalize_email(req.email)
    member = get_user_by_email(session, email)

    if member:
        # Only the newest token may be redeemed — retire any still-active ones
        active_tokens = session.exec(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == member.id)
            .where(PasswordResetToken.used_at == None)  # noqa: E711
        ).all()
        for old in active_tokens:
            old.used_at = utcnow()
            session.add(old)

        raw, hashed = generate_reset_token()
        data = PasswordResetToken(user_id=member.id, token_hash=hashed, expires_at=utcnow() + RESET_TOKEN_TTL)
        session.add(data)
        session.commit()

        subject = "Reset your SHPE password"
        reset_link = f"{FRONTEND_URL}/reset-password?token={raw}"
        body = (
            f"Hi {member.first_name},\n\n"
            "We received a request to reset your SHPE password. "
            "Click the link below to choose a new one:\n\n"
            f"{reset_link}\n\n"
            "This link expires in 1 hour. "
            "If you didn't request a password reset, you can safely ignore this email."
        )
        # A failed send must not change the response — never reveal account existence
        send_email(member.cougarnet_email, subject, body)

    return {"detail": "If an account with that email exists, a reset link has been sent."}

@router.post("/confirm")
async def confirm_password_reset(req: PasswordResetConfirm, session: SessionDependencies):
    # One generic error for not-found / used / expired — don't leak which it was
    invalid_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired token",
    )

    token_hash = hash_reset_token(req.token)
    db_token = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).first()

    if db_token is None or db_token.used_at is not None or db_token.expires_at <= utcnow():
        raise invalid_token

    member = get_user_by_user_id(session, db_token.user_id)
    if member is None:
        raise invalid_token

    # Breached-password check (fail-open) — BEFORE marking the token used, so a
    # rejected password leaves the link redeemable. 422 (not 400: the reset page
    # shows "invalid link" for 400). Module attribute for test monkeypatching;
    # to_thread because httpx's sync client would block the event loop.
    if await asyncio.to_thread(hibp_services.is_password_pwned, req.new_password):
        raise HTTPException(
            status_code=422,
            detail="This password has appeared in a data breach — choose a different one.",
        )

    member.hashed_password = get_password_hash(req.new_password)
    member.password_changed_at = utcnow()
    db_token.used_at = utcnow()
    session.add(member)
    session.add(db_token)
    session.commit()

    return {"detail": "Password has been reset. You can now sign in."}

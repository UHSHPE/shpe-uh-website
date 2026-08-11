import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer
import jwt

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
# 12 hours. There is no refresh-token flow, so a short TTL means members
# re-authenticate constantly — and every re-auth is a 64 MiB argon2 verify.
# At a 300-person event that turns a browsing burst into a hashing burst.
# Revocation does not depend on expiry: get_current_user rejects any token
# issued before User.password_changed_at, so a password reset still kills
# live sessions immediately.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 720))

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    # iat lets get_current_user reject tokens issued before a password reset
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
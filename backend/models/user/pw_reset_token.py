from datetime import datetime
from sqlmodel import SQLModel, Field
from services.time_services import utcnow

class PasswordResetToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(index=True)   # sha256 of the raw token — NEVER the raw token
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime                  # naive UTC: utcnow() + timedelta(hours=1)
    used_at: datetime | None = Field(default=None)
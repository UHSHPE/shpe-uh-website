from datetime import datetime
from sqlmodel import SQLModel, Field
from services.time_services import utcnow

class EmailVerificationToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(index=True)   
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime                  
    used_at: datetime | None = Field(default=None)
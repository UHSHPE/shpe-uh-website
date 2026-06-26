from sqlmodel import Field
from .user_schemas import UserBase
from datetime import datetime

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    # Original filename of the uploaded resume; None means no resume on file.
    # The PDF itself lives on disk keyed by user id (resume_routes.py).
    resume_filename: str | None = Field(default=None)
    password_changed_at: datetime | None = Field(default=None)
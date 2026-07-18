from sqlmodel import Field
from .user_schemas import UserBase
from datetime import datetime

class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str
    email_verified: bool = Field(default=False)
    # Canonical resume name (First_Last_PSID.pdf, set on upload); None means
    # no resume on file. The PDF lives on disk keyed by user id (resume_routes.py).
    resume_filename: str | None = Field(default=None)
    # Google Drive file id of the synced resume copy (drive_services.py);
    # None when Drive sync is off or the last upload never reached Drive.
    resume_drive_file_id: str | None = Field(default=None)
    password_changed_at: datetime | None = Field(default=None)
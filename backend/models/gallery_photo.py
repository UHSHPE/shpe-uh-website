from datetime import datetime
from sqlmodel import SQLModel, Field

from enum import Enum

from services.time_services import utcnow

class Semester(str, Enum):
    fall = "fall"
    spring = "spring"
    
class GalleryPhotoStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class GalleryPhoto(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    submitted_by_user_id: int = Field(foreign_key="user.id", index=True)
    image_filename: str
    submitted_at: datetime = Field(default_factory=utcnow)
    semester: Semester
    year: int
    status: GalleryPhotoStatus = Field(default=GalleryPhotoStatus.pending)
    reviewed_by_user_id: int | None = Field(foreign_key="user.id", index=True, default=None)
    reviewed_at: datetime | None = Field(default=None)
    

class GalleryPhotoOut(SQLModel):
    id: int
    submitter_name: str
    submitted_at: datetime
    semester: Semester
    year: int
    status: GalleryPhotoStatus

from datetime import datetime
from sqlmodel import SQLModel, Field

from enum import Enum
from typing import Literal

from services.time_services import utcnow

PHOTO_APPROVAL_POINTS = 1

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
    submitted_at: datetime = Field(default_factory=utcnow)
    image_filename: str
    semester: Semester
    year: int
    status: GalleryPhotoStatus = Field(default=GalleryPhotoStatus.pending)
    reviewed_by_user_id: int | None = Field(foreign_key="user.id", index=True, default=None)
    reviewed_at: datetime | None = Field(default=None)
    is_deleted: bool = Field(default=False, index=True)

class GalleryPhotoOut(SQLModel):
    id: int
    semester: Semester
    year: int

class GalleryPhotoAdminOut(SQLModel):
    id: int
    submitter_name: str
    submitted_at: datetime
    semester: Semester
    year: int
    status: GalleryPhotoStatus
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None

class GalleryPhotoUpdate(SQLModel):
    decision: Literal[GalleryPhotoStatus.approved, GalleryPhotoStatus.rejected]
    semester: Semester | None = None
    year: int | None = None

class GalleryPhotoPoints(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    submitted_by_user_id: int = Field(foreign_key="user.id", index=True)
    points_awarded: int = Field(default=0, ge=0)
    gallery_photo_id: int = Field(index=True, unique=True)

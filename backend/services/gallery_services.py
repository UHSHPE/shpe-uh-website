import asyncio
import secrets

from fastapi import HTTPException
from fastapi.responses import FileResponse

from sqlmodel import select
from sqlalchemy.orm import aliased

import config

from models.user.user import User
from models.gallery_photo import GalleryPhoto, GalleryPhotoStatus, GalleryPhotoPoints, GalleryPhotoOut, PHOTO_APPROVAL_POINTS
from models.gallery_photo import Semester

from services.dependencies import SessionDependencies
from services.time_services import utcnow

GALLERY_IMAGE_DIR = config.GALLERY_IMAGE_DIR
MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB
IMAGE_TYPES = {
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"
    ),
    "image/jpeg": (
        ".jpg", b"\xff\xd8\xff"
    )
}

Submitter = aliased(User)
Reviewer = aliased(User)

def verify_file_is_an_image(file, contents):
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type. Only PNG and JPEG are allowed.")

    _, signature = IMAGE_TYPES[file.content_type]

    if not contents.startswith(signature):
        raise HTTPException(status_code=400, detail="File is not a valid image.")

async def upload_photo_file(file, contents):
    extension, _ = IMAGE_TYPES[file.content_type]
    filename = f"{secrets.token_hex(16)}{extension}"

    await asyncio.to_thread(GALLERY_IMAGE_DIR.mkdir, parents=True, exist_ok=True)
    image_path = GALLERY_IMAGE_DIR / filename
    await asyncio.to_thread(image_path.write_bytes, contents)

    return filename, image_path

def upload_photo_to_db(user, session, semester, year, filename):
    uploaded_photo = GalleryPhoto(
        submitted_by_user_id=user.id,
        image_filename=filename,
        semester=semester,
        year=year
    )

    session.add(uploaded_photo)
    session.commit()
    return uploaded_photo

def get_semester_and_year():
    now = utcnow()
    month = now.month
    year = now.year

    if month >= 8:  # August or later
        semester = Semester.fall
    else:
        semester = Semester.spring

    return semester, year

def get_approved_gallery_photos(session: SessionDependencies) -> list[GalleryPhotoOut]:
    stmt = (
        select(GalleryPhoto)
            .where(
                GalleryPhoto.status == GalleryPhotoStatus.approved,
                GalleryPhoto.is_deleted == False
            )
        )

    photos = session.exec(stmt)

    approved_photos = []
    for photo in photos:
        approved_photos.append(
            GalleryPhotoOut(
                id=photo.id,
                semester=photo.semester,
                year=photo.year
            )
        )

    return approved_photos

def get_photos_submitters_and_reviewers_on_status(status: GalleryPhotoStatus,session: SessionDependencies):
    stmt = (
        select(GalleryPhoto, Submitter, Reviewer)
            .join(Submitter, GalleryPhoto.submitted_by_user_id == Submitter.id)
            .outerjoin(Reviewer, GalleryPhoto.reviewed_by_user_id == Reviewer.id)
            .where(GalleryPhoto.status == status, GalleryPhoto.is_deleted == False)
    )

    return session.exec(stmt)


def all_photos_submitters_and_reviewers(session: SessionDependencies):
    stmt = (
        select(GalleryPhoto, Submitter, Reviewer)
            .join(Submitter, GalleryPhoto.submitted_by_user_id == Submitter.id)
            .outerjoin(Reviewer, GalleryPhoto.reviewed_by_user_id == Reviewer.id)
            .where(GalleryPhoto.is_deleted == False)
    )
    return session.exec(stmt)

def get_active_photo_by_id(photo_id, session: SessionDependencies):
    photo = session.get(GalleryPhoto, photo_id)
    if not photo or photo.is_deleted:
        return None
    return photo

def retrieve_photo_file(photo_info: GalleryPhoto):
    """
    Checks path and raises error if not found
    Returns image file
    """

    path = GALLERY_IMAGE_DIR / photo_info.image_filename
    if path.name != photo_info.image_filename or not path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")

    media_type = next(
        (content_type for content_type, (extension, _) in IMAGE_TYPES.items() if extension == path.suffix.lower()),
        None,
    )
    if media_type is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, no-store"})

def delete_photo_from_db(photo: GalleryPhoto, session: SessionDependencies):
    photo.is_deleted = True
    session.add(photo)
    session.commit()


def delete_photo_file(photo):
    image_path = GALLERY_IMAGE_DIR / photo.image_filename
    if image_path.name != photo.image_filename:
        raise HTTPException(status_code=404, detail="Photo not found.")

    image_path.unlink(missing_ok=True)

def add_gallery_points_to_user(photo: GalleryPhoto, session: SessionDependencies):
    def get_photo_points():
        stmt = (
            select(GalleryPhotoPoints)
                .where(photo.id == GalleryPhotoPoints.gallery_photo_id)
        )
        return session.exec(stmt).first()

    previous_approved_points = get_photo_points()

    if previous_approved_points:
        return

    approved_gallery_points = GalleryPhotoPoints(
        submitted_by_user_id=photo.submitted_by_user_id,
        points_awarded=PHOTO_APPROVAL_POINTS,
        gallery_photo_id=photo.id
    )

    submitter = session.get(User, photo.submitted_by_user_id)
    submitter.points += PHOTO_APPROVAL_POINTS

    session.add(approved_gallery_points)
    session.add(submitter)

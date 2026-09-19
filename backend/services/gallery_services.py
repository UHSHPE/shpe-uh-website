from fastapi import HTTPException
from sqlmodel import select
from models.user.user import User
from models.gallery_photo import GalleryPhoto, GalleryPhotoStatus
from services.time_services import utcnow
from models.gallery_photo import Semester

MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB
IMAGE_TYPES = {
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"
    ),
    "image/jpeg": (
        ".jpg", b"\xff\xd8\xff"
    )
}

def verify_file_is_an_image(file, contents):
    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type. Only PNG and JPEG are allowed.")

    _, signature = IMAGE_TYPES[file.content_type]

    if not contents.startswith(signature):
        raise HTTPException(status_code=400, detail="File is not a valid image.")
    
def get_semester_and_year():
    now = utcnow()
    month = now.month
    year = now.year

    if month >= 8:  # August or later
        semester = Semester.fall
    else:
        semester = Semester.spring

    return semester, year


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


def get_pending_photo_and_submitter(session):
    stmt = select(GalleryPhoto, User).join(User, GalleryPhoto.submitted_by_user_id == User.id).where(GalleryPhoto.status == GalleryPhotoStatus.pending)
    pending_photos = session.exec(stmt)
    return pending_photos

def get_photo_by_id(photo_id, session):
    return session.get(GalleryPhoto, photo_id)

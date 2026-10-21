from models.gallery_photo import (
    GalleryPhoto,
    GalleryPhotoStatus,
    GallerySubmission,
    Semester,
)
from services.time_services import utcnow


def make_submission(session, user, *, submitted_at=None):
    submission = GallerySubmission(
        submitted_by_user_id=user.id,
        submitted_at=submitted_at or utcnow(),
    )
    session.add(submission)
    session.flush()
    return submission


def make_gallery_photo(
    session,
    user,
    *,
    filename="photo.png",
    status=GalleryPhotoStatus.pending,
    semester=Semester.spring,
    year=2026,
    is_deleted=False,
    reviewer_id=None,
    reviewed_at=None,
    submission=None,
):
    submission = submission or make_submission(session, user)
    photo = GalleryPhoto(
        submission_id=submission.id,
        image_filename=filename,
        semester=semester,
        year=year,
        status=status,
        is_deleted=is_deleted,
        reviewed_by_user_id=reviewer_id,
        reviewed_at=reviewed_at,
    )
    session.add(photo)
    session.commit()
    session.refresh(photo)
    return photo

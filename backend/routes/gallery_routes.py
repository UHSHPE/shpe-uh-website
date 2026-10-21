import asyncio
from typing import Annotated

from models.user.user import User
from models.gallery_photo import GalleryPhotoAdminOut, GalleryPhotoStatus, GalleryPhotoUpdate, GalleryPhotoOut, GallerySubmission

from services.dependencies import SessionDependencies, get_current_user, require_gallery_admin
from services.gallery_services import MAX_PHOTOS_PER_SUBMISSION, MAX_SUBMISSIONS_PER_WEEK, get_semester_and_year, get_active_photo_by_id, retrieve_photo_file, get_photos_submitters_and_reviewers_on_status, all_photos_submitters_and_reviewers, upload_photo_file, upload_photo_to_db, delete_photo_from_db, add_gallery_points_to_user, delete_photo_file, get_approved_gallery_photos, count_user_submissions_per_week, validate_files_are_images
from services.rate_limit import limiter, UPLOAD_LIMIT
from services.time_services import utcnow

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from sqlmodel import select

router = APIRouter(prefix="/gallery", tags=["Gallery"])

# Admin routes | Get Photos (All, Accepted, Rejected, Pending) | Retrieve Photo Info |Retrieve Photo File | Updates Photos | Deletes photos
@router.get("/admin/photos", response_model=list[GalleryPhotoAdminOut])
def get_admin_photo_data(user: Annotated[User, Depends(require_gallery_admin)], session: SessionDependencies, status: GalleryPhotoStatus | None = None) -> list[GalleryPhotoAdminOut]:
    photos_submitters_reviewers = get_photos_submitters_and_reviewers_on_status(status, session) if status else all_photos_submitters_and_reviewers(session)

    out = []
    for photo, submission, submitter, reviewer in photos_submitters_reviewers:
        out.append(
            GalleryPhotoAdminOut(
                id=photo.id,
                submitter_name=f"{submitter.first_name} {submitter.last_name}",
                submitted_at=submission.submitted_at,
                semester=photo.semester,
                year=photo.year,
                status=photo.status,
                reviewer_name=f"{reviewer.first_name} {reviewer.last_name}" if reviewer else None,
                reviewed_at=photo.reviewed_at
            )
        )

    return out

@router.get("/admin/photos/{photo_id}/image")
def get_admin_photo_file(photo_id: int, user: Annotated[User, Depends(require_gallery_admin)], session: SessionDependencies):
    photo = get_active_photo_by_id(photo_id, session)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    return retrieve_photo_file(photo)

@router.patch("/admin/photos/{photo_id}/update")
def update_photo_data(photo_id: int, photo_review: GalleryPhotoUpdate, user: Annotated[User, Depends(require_gallery_admin)], session: SessionDependencies):
    photo = get_active_photo_by_id(photo_id, session)

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    if photo.status != photo_review.decision:
        photo.status = photo_review.decision
        photo.reviewed_at = utcnow()
        photo.reviewed_by_user_id = user.id

    if photo_review.semester:
        photo.semester = photo_review.semester
    if photo_review.year:
        photo.year = photo_review.year


    if photo_review.decision == GalleryPhotoStatus.approved:
        add_gallery_points_to_user(photo, session)

    session.add(photo)
    session.commit()
    session.refresh(photo)

    return {
        "id": photo.id,
        "status": photo.status,
        "semester": photo.semester,
        "year": photo.year
    }

@router.delete("/admin/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int, user: Annotated[User, Depends(require_gallery_admin)], session: SessionDependencies):
    photo = get_active_photo_by_id(photo_id, session)

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found.")

    delete_photo_file(photo)
    delete_photo_from_db(photo, session)

    return None

# Public/User Routes
@router.post("/photos", status_code=201)
@limiter.limit(UPLOAD_LIMIT)
async def submit_photo(request: Request, user: Annotated[User, Depends(get_current_user)], session: SessionDependencies, files: list[UploadFile] = File(...)):
    if not 1 <= len(files) <= MAX_PHOTOS_PER_SUBMISSION:
        raise HTTPException(status_code=400, detail="A submission must contain between 1 and 3 photos.")

    session.exec(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
    ).one()

    submission_count = count_user_submissions_per_week(user.id, session)
    if submission_count >= MAX_SUBMISSIONS_PER_WEEK:
        raise HTTPException(status_code=429, detail="You may submit photos up to 5 times per week.")

    validated_files = await validate_files_are_images(files)

    saved_files = []
    try:
        for file, contents in validated_files:
            filename, image_path = await upload_photo_file(file, contents)
            saved_files.append((filename, image_path))

        submission = GallerySubmission(submitted_by_user_id=user.id)
        session.add(submission)
        session.flush()

        semester, year = get_semester_and_year()
        uploaded_photos = []
        for filename, _ in saved_files:
            uploaded_photos.append(
                upload_photo_to_db(submission.id, session, semester, year, filename)
            )

        session.flush()
        photo_ids = [photo.id for photo in uploaded_photos]
        submission_id = submission.id
        session.commit()

    except Exception:
        session.rollback()
        for _, image_path in saved_files:
            await asyncio.to_thread(image_path.unlink, missing_ok=True)
        raise

    return {
        "message": "Photos submitted successfully.",
        "submission_id": submission_id,
        "photo_ids": photo_ids,
        "status": GalleryPhotoStatus.pending,
    }

@router.get("/photos", response_model=list[GalleryPhotoOut])
def get_gallery_photos(session: SessionDependencies) -> list[GalleryPhotoOut]:
    return get_approved_gallery_photos(session)

@router.get("/photos/{photo_id}/image")
def get_photo_image(photo_id: int, session: SessionDependencies):
    photo = get_active_photo_by_id(photo_id, session)

    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found.")

    if photo.status != GalleryPhotoStatus.approved:
        raise HTTPException(status_code=404, detail="Photo is not approved to show.")

    return retrieve_photo_file(photo)

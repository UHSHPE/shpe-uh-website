import asyncio
from typing import Annotated

from models.user.user import User
from models.gallery_photo import GalleryPhotoAdminOut, GalleryPhotoStatus, GalleryPhotoUpdate, GalleryPhotoOut

from services.dependencies import SessionDependencies, get_current_user, require_gallery_admin
from services.gallery_services import MAX_IMAGE_BYTES, verify_file_is_an_image, get_semester_and_year, get_active_photo_by_id, retrieve_photo_file, get_photos_submitters_and_reviewers_on_status, all_photos_submitters_and_reviewers, upload_photo_file, upload_photo_to_db, delete_photo_from_db, add_gallery_points_to_user, delete_photo_file, get_approved_gallery_photos
from services.rate_limit import limiter, UPLOAD_LIMIT
from services.time_services import utcnow

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request

router = APIRouter(prefix="/gallery", tags=["Gallery"])

# Admin routes | Get Photos (All, Accepted, Rejected, Pending) | Retrieve Photo Info |Retrieve Photo File | Updates Photos | Deletes photos
@router.get("/admin/photos", response_model=list[GalleryPhotoAdminOut])
def get_admin_photo_data(user: Annotated[User, Depends(require_gallery_admin)], session: SessionDependencies, status: GalleryPhotoStatus | None = None) -> list[GalleryPhotoAdminOut]:
    photos_submitters_reviewers = get_photos_submitters_and_reviewers_on_status(status, session) if status else all_photos_submitters_and_reviewers(session)

    out = []
    for photo, submitter, reviewer in photos_submitters_reviewers:
        out.append(
            GalleryPhotoAdminOut(
                id=photo.id,
                submitter_name=f"{submitter.first_name} {submitter.last_name}",
                submitted_at=photo.submitted_at,
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
async def submit_photo(request: Request, user: Annotated[User, Depends(get_current_user)], session: SessionDependencies, file: UploadFile = File(...)):
    if file.size is not None and file.size > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 2 MB or smaller.")

    contents = await file.read()
    verify_file_is_an_image(file, contents)
    semester, year = get_semester_and_year()
    filename, image_path = await upload_photo_file(file, contents)

    try:
        uploaded_photo = upload_photo_to_db(user, session, semester, year, filename)
    except Exception:
        session.rollback()
        await asyncio.to_thread(image_path.unlink, missing_ok=True)
        raise

    session.refresh(uploaded_photo)

    return {
        "message": "Photo submitted successfully.",
        "photo_id": uploaded_photo.id,
        "status": uploaded_photo.status,
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

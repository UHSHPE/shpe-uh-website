import asyncio
import secrets
from typing import Annotated

import config

from models.user.user import User
from models.gallery_photo import GalleryPhotoOut, GalleryPhotoStatus

from services.gallery_services import upload_photo_to_db
from services.dependencies import SessionDependencies, get_current_user, require_gallery_admin
from services.gallery_services import IMAGE_TYPES, MAX_IMAGE_BYTES, verify_file_is_an_image, get_semester_and_year, get_pending_photo_and_submitter, get_photo_by_id


from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse

router = APIRouter(prefix="/gallery", tags=["Gallery"])
GALLERY_IMAGE_DIR = config.GALLERY_IMAGE_DIR

@router.post("/photos", status_code=201)
async def submit_photo(user: Annotated[User, Depends(get_current_user)], session: SessionDependencies, file: UploadFile = File(...)):
    if file.size is not None and file.size > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 2 MB or smaller.")
    
    contents = await file.read()
    
    verify_file_is_an_image(file, contents)

    semester, year = get_semester_and_year()    

    extension, _ = IMAGE_TYPES[file.content_type]
    filename = f"{secrets.token_hex(16)}{extension}"
    await asyncio.to_thread(GALLERY_IMAGE_DIR.mkdir, parents=True, exist_ok=True)
    image_path = GALLERY_IMAGE_DIR / filename
    await asyncio.to_thread(image_path.write_bytes, contents)

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


@router.get("/photos/pending", response_model=list[GalleryPhotoOut])
def get_pending_photos(user: Annotated[User, Depends(require_gallery_admin)], session: SessionDependencies):
    pending_photos_and_submitter = get_pending_photo_and_submitter(session)
    
    out = []
    for photo, submitter in pending_photos_and_submitter:
        out.append(
            GalleryPhotoOut(
                id=photo.id,
                submitter_name=f"{submitter.first_name} {submitter.last_name}",
                submitted_at=photo.submitted_at,
                semester=photo.semester,
                year=photo.year,
                status=photo.status
            )
        )
        
    return out

@router.get("/photos/{photo_id}/image")
def get_photo_image(photo_id: int, user: Annotated[User, Depends(require_gallery_admin)], session: SessionDependencies):
    photo = get_photo_by_id(photo_id, session)
    if photo is None or photo.status != GalleryPhotoStatus.pending:
        raise HTTPException(status_code=404, detail="Photo not found")

    path = GALLERY_IMAGE_DIR / photo.image_filename
    if path.name != photo.image_filename or not path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")

    media_type = next(
        (content_type for content_type, (extension, _) in IMAGE_TYPES.items() if extension == path.suffix.lower()),
        None,
    )
    if media_type is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, no-store"})
    

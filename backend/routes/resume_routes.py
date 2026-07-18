import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse

from models.user.user import User
from services.dependencies import SessionDependencies, get_current_user
from services.drive_services import delete_resume_from_drive, upload_resume_to_drive

router = APIRouter(tags=["Resume"])

# Uploaded resumes live on disk, one PDF per user keyed by user id.
RESUME_DIR = Path(__file__).resolve().parent.parent / "uploads" / "resumes"
MAX_RESUME_BYTES = 2 * 1024 * 1024  # 2 MB
PDF_MAGIC = b"%PDF"


def _resume_path(user_id: int) -> Path:
    return RESUME_DIR / f"user_{user_id}.pdf"


def _canonical_resume_name(user: User) -> str:
    """Every resume is renamed to First_Last_PSID.pdf (the uploaded filename
    is discarded) — used for the stored name, the download name, and the
    Drive copy. Multi-word names are joined with underscores too."""
    return "_".join(f"{user.first_name} {user.last_name} {user.psid}".split()) + ".pdf"


@router.post("/me/resume")
async def upload_resume(
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
    file: UploadFile = File(...),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf") or file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")

    contents = await file.read()

    if len(contents) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Resume must be 2 MB or smaller.",
        )

    if not contents.startswith(PDF_MAGIC):
        raise HTTPException(status_code=400, detail="File is not a valid PDF.")

    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    _resume_path(user.id).write_bytes(contents)

    user.resume_filename = _canonical_resume_name(user)

    # Sync to the Google Drive folder: replaces the old copy in place when one
    # exists (same file id), creates it otherwise. Blocking client → thread.
    drive_file_id = await asyncio.to_thread(
        upload_resume_to_drive, user.resume_drive_file_id, user.resume_filename, contents
    )
    if drive_file_id is not None:
        user.resume_drive_file_id = drive_file_id

    session.add(user)
    session.commit()

    return {"resume_filename": user.resume_filename}


@router.get("/me/resume")
async def get_resume(
    user: Annotated[User, Depends(get_current_user)],
):
    path = _resume_path(user.id)
    if not user.resume_filename or not path.exists():
        raise HTTPException(status_code=404, detail="No resume on file.")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=user.resume_filename,
    )


@router.delete("/me/resume", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    _resume_path(user.id).unlink(missing_ok=True)

    # Remove the synced copy from the Drive folder too (already-gone counts as
    # deleted; other failures are logged inside and the local delete proceeds).
    if await asyncio.to_thread(delete_resume_from_drive, user.resume_drive_file_id):
        user.resume_drive_file_id = None

    user.resume_filename = None
    session.add(user)
    session.commit()
    return None

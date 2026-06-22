from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse

from models.user.user import User
from services.dependencies import SessionDependencies, get_current_user

router = APIRouter(tags=["Resume"])

# Uploaded resumes live on disk, one PDF per user keyed by user id.
RESUME_DIR = Path(__file__).resolve().parent.parent / "uploads" / "resumes"
MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB
PDF_MAGIC = b"%PDF"


def _resume_path(user_id: int) -> Path:
    return RESUME_DIR / f"user_{user_id}.pdf"


def _sanitize_filename(name: str | None) -> str:
    """Strip any directory parts and fall back to a safe default."""
    if not name:
        return "resume.pdf"
    base = Path(name).name.strip()
    if not base.lower().endswith(".pdf"):
        base = f"{base}.pdf"
    return base or "resume.pdf"


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
            detail="Resume must be 5 MB or smaller.",
        )

    if not contents.startswith(PDF_MAGIC):
        raise HTTPException(status_code=400, detail="File is not a valid PDF.")

    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    _resume_path(user.id).write_bytes(contents)

    user.resume_filename = _sanitize_filename(filename)
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
    user.resume_filename = None
    session.add(user)
    session.commit()
    return None

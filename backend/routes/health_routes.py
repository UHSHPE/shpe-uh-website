"""
Health endpoints for the deployment platform and for manual checks.
"""

from fastapi import APIRouter
from sqlmodel import text

from services.dependencies import SessionDependencies

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("", include_in_schema=False)
def health():
    """Liveness probe. Deliberately does NOT touch the database — a transient
    lock or a slow query must not make the platform kill a healthy container."""
    return {"status": "ok"}

@router.get("/db", include_in_schema=False)
def health_db(session: SessionDependencies):
    """Readiness check, for manual verification rather than the platform."""
    session.exec(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
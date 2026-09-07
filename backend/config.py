"""
Deployment configuration: where the app writes at runtime, and whether it is the live deployment.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from services.body_limit import DEFAULT_MAX_BODY_BYTES

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = Path(os.getenv("DATA_DIR") or BASE_DIR).resolve()

UPLOAD_DIR = DATA_DIR / "uploads"
RESUME_DIR = UPLOAD_DIR / "resumes"
PRODUCT_IMAGE_DIR = UPLOAD_DIR / "products"

def is_production() -> bool:
    """True when this process is the live deployment."""
    return os.getenv("ENVIRONMENT", "").strip().lower() == "production"


def square_is_production() -> bool:
    """True when Square should hit the live API rather than sandbox."""
    return os.getenv("SQUARE_ENVIRONMENT", "sandbox").strip().lower() == "production"


def cors_origins() -> list[str]:
    """Browser origins allowed to call the API."""
    raw = (
        os.getenv("CORS_ORIGINS")
        or os.getenv("FRONTEND_URL")
        or "http://localhost:5173"
    )
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def docs_urls() -> dict[str, str | None]:
    """Paths for the interactive API docs, switched off in production."""
    if is_production():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


def max_body_bytes() -> int:
    """The cap for BodyLimitMiddleware, from MAX_REQUEST_BODY_BYTES."""
    try:
        return max(1, int(os.getenv("MAX_REQUEST_BODY_BYTES", DEFAULT_MAX_BODY_BYTES)))
    except ValueError:
        return DEFAULT_MAX_BODY_BYTES

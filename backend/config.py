"""Resolve runtime paths and deployment configuration."""
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

# Deliberately no mkdir here. Importing config must stay free of side effects
# so tests (which monkeypatch these paths to tmp_path) never touch real dirs;
# creation happens in database.create_db() at startup instead.


def is_production() -> bool:
    """Return whether ENVIRONMENT specifies production, normalized at call time."""
    return os.getenv("ENVIRONMENT", "").strip().lower() == "production"


def square_is_production() -> bool:
    """Return whether Square uses production, defaulting to sandbox."""
    return os.getenv("SQUARE_ENVIRONMENT", "sandbox").strip().lower() == "production"


def cors_origins() -> list[str]:
    """Read allowed browser origins, falling back to FRONTEND_URL or local Vite."""
    raw = (
        os.getenv("CORS_ORIGINS")
        or os.getenv("FRONTEND_URL")
        or "http://localhost:5173"
    )
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def docs_urls() -> dict[str, str | None]:
    """Disable all API documentation and schema URLs in production."""
    if is_production():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


def max_body_bytes() -> int:
    """Read the request body cap, which must exceed the per-route upload limits."""
    try:
        return max(1, int(os.getenv("MAX_REQUEST_BODY_BYTES", DEFAULT_MAX_BODY_BYTES)))
    except ValueError:
        return DEFAULT_MAX_BODY_BYTES

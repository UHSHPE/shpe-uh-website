"""Filesystem layout for everything the app writes at runtime.

One knob — DATA_DIR — decides where uploaded files live. On a container host
that is the mounted volume (ours is /data); anywhere else it defaults to the
backend/ directory, which is byte-for-byte the layout the project used before
deployment existed.

The database is NOT here: it moved to Postgres, addressed by DATABASE_URL in
database.py. Uploads are the only durable state left on disk, so a volume is
still required — losing it loses every resume and product image.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = Path(os.getenv("DATA_DIR") or BASE_DIR).resolve()

UPLOAD_DIR = DATA_DIR / "uploads"
RESUME_DIR = UPLOAD_DIR / "resumes"
PRODUCT_IMAGE_DIR = UPLOAD_DIR / "products"

# Deliberately no mkdir here. Importing config must stay free of side effects
# so tests (which monkeypatch these paths to tmp_path) never touch real dirs;
# creation happens in database.create_db() at startup instead.

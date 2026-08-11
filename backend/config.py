"""Deployment configuration: where the app writes at runtime, and whether it
is the live deployment.

One knob — DATA_DIR — decides where uploaded files live. On a container host
that is the mounted volume (ours is /data); anywhere else it defaults to the
backend/ directory, which is byte-for-byte the layout the project used before
deployment existed.

The database is NOT here: it moved to Postgres, addressed by DATABASE_URL in
database.py. Uploads are the only durable state left on disk, so a volume is
still required — losing it loses every resume and product image.

is_production() / square_is_production() are the OTHER reason this module
exists: they are the single normalized answer to "am I in production?", so
that two call sites can never disagree about it. See their docstrings.
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


def is_production() -> bool:
    """True when this process is the live deployment.

    Every production decision in the app routes through here, and that is the
    point. Four call sites used to read ENVIRONMENT themselves and two of them
    forgot to .strip(), which split the app in half: with ENVIRONMENT set to
    "production " (a pasted dashboard value with a trailing space) docs_urls()
    and seed.py read production while assert_production_config() and
    charge_card() read dev — so the app booted green with no Square
    credentials and every checkout completed without charging a card, while
    both signals an operator would check still reported production. Strip and
    lowercase in ONE place so that cannot recur.

    Read at CALL time, never cached in a module constant: docs_urls() runs at
    import (FastAPI() is constructed at import) and the test suite
    monkeypatches ENVIRONMENT.
    """
    return os.getenv("ENVIRONMENT", "").strip().lower() == "production"


def square_is_production() -> bool:
    """True when Square should hit the live API rather than sandbox.

    Same split as is_production() had, in the milder direction: a padded value
    made the app refuse to boot complaining SQUARE_ENVIRONMENT=production was
    missing when it had in fact been set. Defaults to sandbox — an unset value
    must never mean live charges.
    """
    return os.getenv("SQUARE_ENVIRONMENT", "sandbox").strip().lower() == "production"

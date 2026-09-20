import os

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlmodel import create_engine, Session

from config import PRODUCT_IMAGE_DIR, RESUME_DIR

# Registers every model in SQLModel's metadata for alembic/env.py (--autogenerate)
# and tests/conftest.py. Dropping an import here silently removes that table from
# migrations and from the test database.
import models.user.user  # noqa: F401
import models.dues_import  # noqa: F401
import models.user.multi_selections.user_race_ethnicity  # noqa: F401
import models.user.multi_selections.user_prof_dev  # noqa: F401
import models.user.multi_selections.user_interested_industries  # noqa: F401
import models.user.multi_selections.user_country_origin  # noqa: F401
import models.user.pw_reset_token  # noqa: F401
import models.user.email_verification  # noqa: F401
import models.event      # noqa: F401
import models.event_reminder  # noqa: F401
import models.event_host  # noqa: F401
import models.event_attendance  # noqa: F401
import models.committee  # noqa: F401
import models.role_report  # noqa: F401
import models.committee_message  # noqa: F401
import models.notification  # noqa: F401
import models.shop.product  # noqa: F401
import models.shop.order  # noqa: F401
import models.shop.shop_settings  # noqa: F401

load_dotenv()

# Default is the local docker-compose container (host port 5433, not 5432).
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/shpe",
)

engine = create_engine(
    DATABASE_URL,
    # Echo logs member emails and PSIDs — opt in locally, never in production.
    echo=os.getenv("SQL_ECHO", "").strip().lower() in ("1", "true", "yes"),
    # Recycles connections the database dropped (container restart, idle timeout).
    pool_pre_ping=True,
)

# The only databases a destructive local script (seed.py) may write to. The host
# set is the load-bearing half: a managed instance is never reachable on loopback.
LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}
LOCAL_DB_NAMES = {"shpe", "shpe_test"}


def assert_local_database(url: str | None = None):
    """Raise unless the URL points at the local dev Postgres.

    seed.py's other guard keys on ENVIRONMENT, which says nothing about which
    database is being written; this one checks the target itself. Known limit:
    an SSH tunnel forwarding production to localhost satisfies both checks.
    """
    parsed = make_url(url or DATABASE_URL)

    host = parsed.host
    if not host:
        # No host means a unix socket, but libpq also accepts a hostname in
        # ?host=, which would otherwise slip through as if it were a socket.
        socket_host = parsed.query.get("host")
        if isinstance(socket_host, (tuple, list)):
            socket_host = socket_host[0] if socket_host else None
        host = socket_host or "localhost"

    problems = []
    if not (host.startswith("/") or host.lower() in LOCAL_DB_HOSTS):
        problems.append(f"host {host!r} is not local")
    if parsed.database not in LOCAL_DB_NAMES:
        problems.append(
            f"database {parsed.database!r} is not one of {sorted(LOCAL_DB_NAMES)}"
        )

    if problems:
        raise RuntimeError(
            "refusing to run against a non-local database — "
            + " and ".join(problems)
            + ". Seed data must never enter a deployed database; check DATABASE_URL."
        )


def create_db():
    # Uploads still live on a mounted volume (DATA_DIR in config.py).
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    # No create_all() — Alembic owns the schema, and tests build theirs in conftest.

def get_session():
    with Session(engine) as session:
        yield session

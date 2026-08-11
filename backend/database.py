import os

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlmodel import create_engine, Session

from config import PRODUCT_IMAGE_DIR, RESUME_DIR

# Import all models so they register in SQLModel's shared metadata. Nothing in
# this module reads that registry any more, but two things depend on importing
# this module to populate it: alembic/env.py (--autogenerate diffs against it)
# and tests/conftest.py (builds the test schema from it). Dropping an import
# here silently removes that table from migrations and from the test database.
import models.user.user  # noqa: F401
import models.user.multi_selections.user_race_ethnicity  # noqa: F401
import models.user.multi_selections.user_prof_dev  # noqa: F401
import models.user.multi_selections.user_interested_industries  # noqa: F401
import models.user.multi_selections.user_country_origin  # noqa: F401
import models.user.pw_reset_token
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

# The default points at the local docker-compose container (see
# docker-compose.yml — note host port 5433, not 5432). In production this is
# set to the managed Postgres instance.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/shpe",
)

engine = create_engine(
    DATABASE_URL,
    # Off by default: echo logs every statement, including member emails and
    # PSIDs, which in production is both a log-volume and a privacy problem.
    # SQL_ECHO=1 turns it on for local debugging without a code change.
    echo=os.getenv("SQL_ECHO", "").strip().lower() in ("1", "true", "yes"),
    # Recycles a connection the database dropped (container restart, idle
    # timeout) instead of failing the next request with a stale socket.
    pool_pre_ping=True,
)

# The only databases a destructive local script (seed.py) may write to. The
# host set is the load-bearing half: a managed instance is never reachable on
# loopback, so a production DATABASE_URL cannot satisfy it no matter what else
# is set. The name set is a second layer for what the host check misses.
LOCAL_DB_HOSTS = {"localhost", "127.0.0.1", "::1"}
LOCAL_DB_NAMES = {"shpe", "shpe_test"}


def assert_local_database(url: str | None = None):
    """Raise unless the URL points at the local dev Postgres.

    seed.py's other guard keys on ENVIRONMENT, which says nothing about which
    database is being written — the target comes from DATABASE_URL, resolved
    above and read independently of that flag. Export a production
    DATABASE_URL in a shell where ENVIRONMENT is unset (the documented
    local-dev default) and that guard passes while seed.py mints ~30 accounts
    sharing password123, including an email_verified president. This one
    guards the causal property instead, mirroring the `_test` suffix check in
    tests/conftest.py.

    Known limit, accepted: an SSH tunnel forwarding a production Postgres to
    localhost satisfies both checks. That's a deliberate act rather than the
    muscle-memory mistake this exists to stop, and closing it would mean
    authenticating the far end.
    """
    parsed = make_url(url or DATABASE_URL)

    host = parsed.host
    if not host:
        # No host means a unix socket — local by construction when it's a path
        # like /tmp, but libpq also accepts a hostname in ?host=, which would
        # otherwise slip through as if it were a socket.
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
    # Uploads still live on a mounted volume even though the database no
    # longer does — DATA_DIR (config.py) is what points them at it.
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    # The schema is owned by Alembic — run `alembic upgrade head`. A
    # create_all() here would be a second, competing schema authority: on a
    # fresh database whichever ran first would win, and an app boot that beat
    # the migration would leave Alembic trying to create tables that already
    # exist. Tests build their schema directly (tests/conftest.py), not here.

def get_session():
    with Session(engine) as session:
        yield session

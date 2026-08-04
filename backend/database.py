import os

from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session

from config import PRODUCT_IMAGE_DIR, RESUME_DIR

# Import all models so SQLModel registers their tables before create_all runs
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

def create_db():
    # Uploads still live on a mounted volume even though the database no
    # longer does — DATA_DIR (config.py) is what points them at it.
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

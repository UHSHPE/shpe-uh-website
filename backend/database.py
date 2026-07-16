from sqlmodel import SQLModel, create_engine, Session

# Import all models so SQLModel registers their tables before create_all runs
import models.user.user  # noqa: F401
import models.user.multi_selections.user_race_ethnicity  # noqa: F401
import models.user.multi_selections.user_prof_dev  # noqa: F401
import models.user.multi_selections.user_interested_industries  # noqa: F401
import models.user.multi_selections.user_country_origin  # noqa: F401
import models.user.pw_reset_token
import models.event      # noqa: F401
import models.event_reminder  # noqa: F401
import models.committee  # noqa: F401
import models.committee_message  # noqa: F401
import models.notification  # noqa: F401
import models.shop.product  # noqa: F401
import models.shop.order  # noqa: F401
import models.shop.shop_settings  # noqa: F401

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

def create_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

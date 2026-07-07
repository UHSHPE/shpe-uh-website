import pytest
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from database import get_session
from services.dependencies import get_current_user
from services.time_services import utcnow
from models.event import Event
from models.user.user import User
from models.user.user_enums import (
    Classification,
    Colleges,
    ExpGradDate,
    Gender,
    GPA,
    MembershipStatus,
    Role,
    ShirtSize,
)


# slowapi's in-memory counters persist across tests in the same process —
# reset them so rate-limited endpoints (/login, /password-reset/request)
# don't 429 unrelated tests.
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from services.rate_limit import limiter

    limiter.reset()
    yield


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def make_user(session, **overrides):
    fields = dict(
        first_name="Test",
        last_name="User",
        cougarnet_email="test@cougarnet.uh.edu",
        personal_email="test@gmail.com",
        role=Role.member,
        points=0,
        phone_num="713-555-1234",
        psid="1234567",
        birthday=date(2000, 1, 1),
        gender=Gender.male,
        first_gen=True,
        college=Colleges.nsm,
        major="Computer Science",
        classification=Classification.senior,
        gpa=GPA.gpa_350_400,
        exp_grad_date=ExpGradDate.spring_2027,
        in_slack=True,
        is_returning=MembershipStatus.new,
        is_national_member=True,
        shirt_size=ShirtSize.m,
        hashed_password="not-a-real-hash",
    )
    fields.update(overrides)
    user = User(**fields)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def make_event(session, *, start_in=timedelta(days=7), **overrides):
    fields = dict(
        title="General Meeting",
        description="A test event",
        location="PGH 232",
        start_time=utcnow() + start_in,
        end_time=None,
        points_value=10,
        event_type="General Meeting",
    )
    fields.update(overrides)
    event = Event(**fields)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@pytest.fixture
def user(session):
    return make_user(session)


@pytest.fixture
def client(session, user):
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client(session):
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()

import pytest
from fastapi.testclient import TestClient

from database import get_session
from models.committee import Committee, CommitteeMembership
from models.event_host import EventHost
from models.user.user_enums import Role
from services.dependencies import get_current_user
from tests.admin_tests.conftest import make_president
from tests.conftest import make_event, make_user


def make_committee(session, **overrides):
    fields = dict(
        name="Social",
        description="Test committee",
        chair_role=Role.social_chair,
        joinable=True,
    )
    fields.update(overrides)
    committee = Committee(**fields)
    session.add(committee)
    session.commit()
    session.refresh(committee)
    return committee


def make_chair(session, committee, **overrides):
    """A user who chairs `committee` -- both halves required, mirroring
    committee_services.require_chair: the User.role AND an active is_chair
    CommitteeMembership row."""
    fields = dict(
        cougarnet_email="chair@cougarnet.uh.edu",
        personal_email="chair@gmail.com",
        psid="5555555",
        role=committee.chair_role,
    )
    fields.update(overrides)
    user = make_user(session, **fields)
    session.add(CommitteeMembership(
        user_id=user.id,
        committee_id=committee.id,
        status=True,
        is_chair=True,
    ))
    session.commit()
    return user


def link_host(session, event, committee):
    session.add(EventHost(event_id=event.id, committee_id=committee.id))
    session.commit()


def make_meeting(session, committee, **overrides):
    """A chair-created committee meeting as the create route will store it."""
    fields = dict(
        title=f"{committee.name} Meeting",
        event_type=committee.name.lower(),
        sheet_row=None,
        sign_out_code=None,
        is_committee_meeting=True,
    )
    fields.update(overrides)
    meeting = make_event(session, **fields)
    link_host(session, meeting, committee)
    return meeting


@pytest.fixture
def committee(session):
    return make_committee(session)


@pytest.fixture
def chair(session, committee):
    return make_chair(session, committee)


@pytest.fixture
def chair_client(session, chair):
    """Auth'd as a committee chair. Same rule as manager_client/president_client
    in the other test suites: don't mix with `client`/other *_client fixtures
    in one test -- they all override get_current_user on the same app and the
    last one wins."""
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: chair
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def president(session):
    return make_president(session)


@pytest.fixture
def president_client(session, president):
    """Auth'd as the president -- full bypass in host_scoped_events."""
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: president
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def officer(session):
    """An E-Board officer who chairs nothing — the case code_scoped_events
    widens (every event's QR) while host_scoped_events stays narrow (no
    roster). Treasurer specifically: an EBOARD_ROLES member with no
    CommitteeMembership rows and no president bypass."""
    return make_user(
        session,
        cougarnet_email="treasurer@cougarnet.uh.edu",
        personal_email="treasurer@gmail.com",
        psid="7777777",
        role=Role.treasurer,
    )


@pytest.fixture
def officer_client(session, officer):
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: officer
    yield TestClient(app)
    app.dependency_overrides.clear()

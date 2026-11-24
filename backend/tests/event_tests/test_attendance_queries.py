# Unit tests for services/attendance_queries.py -- the committee-meeting queries.

from sqlmodel import select

from models.event import Event
from models.event_host import EventHost
from models.user.user_enums import Role
from services.attendance_queries import add_event_with_host, chair_committee, committee_meetings
from services.time_services import utcnow
from tests.conftest import make_event
from tests.event_tests.conftest import link_host, make_committee, make_meeting


# --- chair_committee ---

def test_chair_committee_finds_the_committee_for_the_role(session, committee):
    make_committee(session, name="Outreach", chair_role=Role.outreach_chair)
    assert chair_committee(session, Role.social_chair).id == committee.id


def test_chair_committee_is_none_for_a_role_that_chairs_nothing(session, committee):
    assert chair_committee(session, Role.member) is None


# --- add_event_with_host ---

def test_add_event_with_host_links_the_host_without_committing(session, committee):
    event = Event(title="Social Meeting", start_time=utcnow(), is_committee_meeting=True)

    add_event_with_host(session, event, committee.id)

    assert event.id is not None
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert [h.committee_id for h in hosts] == [committee.id]
    session.rollback()   # nothing was committed, so both rows go
    assert session.get(Event, event.id) is None


# --- committee_meetings ---

def test_committee_meetings_returns_only_this_committees_live_meetings(session, committee):
    outreach = make_committee(session, name="Outreach", chair_role=Role.outreach_chair)
    mine = make_meeting(session, committee)
    make_meeting(session, committee, deleted_at=utcnow())
    make_meeting(session, outreach)
    regular = make_event(session, title="Mixer", event_type="social")
    link_host(session, regular, committee)

    assert [m.id for m in committee_meetings(session, committee.id)] == [mine.id]

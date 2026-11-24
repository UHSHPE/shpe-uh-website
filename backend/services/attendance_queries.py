"""Database reads and writes for committee meetings. No rules, no commits --
the caller decides what to store and commits it as one unit."""

from sqlmodel import select

from models.committee import Committee
from models.event import Event
from models.event_host import EventHost
from models.user.user_enums import Role
from services.event_services import live_events


def chair_committee(session, role: Role) -> Committee | None:
    """Keyed on the live role, so a demoted chair's stale is_chair row grants nothing."""
    return session.exec(select(Committee).where(Committee.chair_role == role)).first()


def add_event_with_host(session, event: Event, committee_id: int) -> Event:
    # flush, not commit: assigns event.id for the host row while both stay one transaction.
    session.add(event)
    session.flush()
    session.add(EventHost(event_id=event.id, committee_id=committee_id))
    return event


def committee_meetings(session, committee_id: int) -> list[Event]:
    return session.exec(
        live_events()
        .join(EventHost, EventHost.event_id == Event.id)
        .where(
            EventHost.committee_id == committee_id,
            Event.is_committee_meeting == True,  # noqa: E712
        )
        .order_by(Event.start_time)
    ).all()

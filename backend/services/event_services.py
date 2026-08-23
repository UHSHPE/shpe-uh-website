"""Read helpers for Event, centralizing the soft-delete filter.

Event is soft-deleted (models/event.py's deleted_at), and a soft-deleted event
must be invisible to the whole app -- the public calendar, the member
dashboard, the chair views, QR check-in and the reminder dispatcher. That's ten
call sites across three modules, which is exactly the shape where sprinkling
`.where(Event.deleted_at == None)` by hand eventually misses the eleventh.

Everything that reads events goes through these two helpers instead, so the
filter lives in one place and a query that bypasses it is visible in review.
"""

from sqlmodel import select

from models.event import Event


def not_deleted():
    """The soft-delete predicate on its own, for statements that can't start
    from live_events() -- a multi-entity select (e.g. the reminder dispatcher's
    EventReminder/Event/User join) has to be built with select(...) directly, so
    it takes the predicate rather than the statement. Same single definition
    either way."""
    return Event.deleted_at == None  # noqa: E711


def live_events():
    """Base SELECT for events that still exist as far as the app is concerned.

    Returns a statement, not rows -- callers add their own .where()/.order_by()
    and execute it:

        session.exec(live_events().order_by(Event.start_time)).all()
    """
    return select(Event).where(not_deleted())


def get_live_event(session, event_id: int) -> Event | None:
    """session.get(Event, id) that returns None for a soft-deleted event.

    The by-id counterpart to live_events(); routes turn the None into their
    usual 404, so a hidden event is indistinguishable from one that never
    existed.
    """
    return session.exec(live_events().where(Event.id == event_id)).first()

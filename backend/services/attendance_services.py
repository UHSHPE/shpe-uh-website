import secrets
from datetime import datetime, time, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from models.committee import Committee, CommitteeMembership
from models.event import Event
from models.event_attendance import EventAttendance
from models.event_host import EventHost
from models.user.user import User
from models.user.user_enums import EBOARD_ROLES, Role
from services.event_tracker_services import SHEET_TZ, to_utc
from services.time_services import utcnow

# "Did you bring a new member?" bonus — capped at once per event by the
# EventAttendance composite PK (user_id, event_id).
NEW_MEMBER_BONUS = 2


def default_points(event: Event) -> tuple[int, int]:
    """(sign_in, sign_out) points for an event, from the rule alone — there
    are no per-event overrides, so nothing is stored on Event itself.

    GBM detection is deliberately case-sensitive ("GM" in event.title, not
    .lower()) — a case-insensitive check would also match ordinary words
    that merely contain "gm" (e.g. "Segment"). Verified against the live DB:
    eboard + "GM" selects exactly the 5 real GBMs and correctly excludes
    both Cat's Back Day (eboard, not a GM) and SHPE JR 1ST GM (a GM title,
    but event_type is shpe_jr, not eboard).
    """
    if event.event_type == "eboard" and "GM" in event.title:
        return (3, 2)
    return (2, 2)


def ensure_event_codes(session, event: Event) -> None:
    """Mint sign-in/out codes the first time an event's codes are needed.
    Idempotent — a no-op once both columns are already set."""
    changed = False
    if not event.sign_in_code:
        event.sign_in_code = secrets.token_urlsafe(16)
        changed = True
    if not event.sign_out_code:
        event.sign_out_code = secrets.token_urlsafe(16)
        changed = True
    if changed:
        session.add(event)
        session.commit()
        session.refresh(event)


def resolve_code(session, code: str) -> tuple[Event, str] | None:
    """(event, "in" | "out") for a scanned code, or None if it matches
    neither column. Both columns are unique-indexed, so each branch is an
    index hit; because the action rides on *which code was scanned*, a
    mislabeled QR can't happen."""
    event = session.exec(select(Event).where(Event.sign_in_code == code)).first()
    if event:
        return event, "in"
    event = session.exec(select(Event).where(Event.sign_out_code == code)).first()
    if event:
        return event, "out"
    return None


def _end_of_local_day(start_time: datetime) -> datetime:
    """23:59:59.999999 of start_time's Central calendar day, converted back
    to UTC via the same to_utc() the sheet sync uses. event.start_time is
    naive UTC; plenty of events have no end_time at all, and blank /
    "All Day" / "TBD" sheet times already fell back to local midnight — so
    keying expiry on UTC midnight (instead of the Central day) would expire
    those events before they even started."""
    central_date = start_time.replace(tzinfo=timezone.utc).astimezone(SHEET_TZ).date()
    return to_utc(datetime.combine(central_date, time(23, 59, 59, 999999)))


def is_expired(event: Event, now: datetime | None = None) -> bool:
    """A code stops working once the event is over — the whole replacement
    for revocation. No regeneration, no revocation."""
    now = now or utcnow()
    deadline = event.end_time or _end_of_local_day(event.start_time)
    return now > deadline


NOT_STARTED_GRACE_MINUTES = 60


def is_not_started(event: Event, now: datetime | None = None) -> bool:
    """True until 60 minutes before event.start_time.

    A hard `now < start_time` would reject nobody for the many events whose
    start_time is a blank/"All Day"/"TBD" sheet-sync fallback to local
    midnight (midnight is early, not late) — but it WOULD reject a member
    who shows up 10 minutes early to a real timed event. The 60-minute grace
    absorbs early arrivals while still blocking someone who scans a QR a
    chair posted days in advance, which is the case this state exists for.
    Deliberately asymmetric with is_expired's end-of-local-day fallback, for
    the same reason: both err toward letting a real attendee through.
    """
    now = now or utcnow()
    return now < event.start_time - timedelta(minutes=NOT_STARTED_GRACE_MINUTES)


def record_sign_in(
    session,
    user: User,
    event: Event,
    brought_new_member: bool = False,
    new_member_name: str | None = None,
) -> tuple[EventAttendance, int]:
    """Create the EventAttendance row for a sign-in scan and award points.

    Returns (row, points_awarded_by_this_call). points is 0 on a repeat scan
    (row already existed) — callers should treat that as a success ("already
    signed in"), not a failure. User.points is a running total, so this must
    never double-award: the .get() check covers the common case, and the
    IntegrityError catch covers two simultaneous scans racing past it.
    """
    existing = session.get(EventAttendance, (user.id, event.id))
    if existing:
        return existing, 0

    name = (new_member_name or "").strip() or None if brought_new_member else None
    sign_in_points, _ = default_points(event)
    points = sign_in_points + (NEW_MEMBER_BONUS if brought_new_member else 0)

    attendance = EventAttendance(
        user_id=user.id,
        event_id=event.id,
        signed_in_at=utcnow(),
        brought_new_member=brought_new_member,
        new_member_name=name,
        points_awarded=points,
    )
    session.add(attendance)
    user.points += points
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # Two simultaneous scans raced past the .get() check above — the
        # loser rolls back and reports the same "already signed in" outcome.
        session.rollback()
        existing = session.get(EventAttendance, (user.id, event.id))
        return existing, 0

    session.refresh(attendance)
    return attendance, points


def record_sign_out(session, user: User, event: Event) -> tuple[EventAttendance | None, int]:
    """Stamp signed_out_at and award sign-out points.

    Returns (row, points_awarded_by_this_call). Row is None when the member
    never signed in at all (nothing to stamp) — the route turns that into a
    400. points is 0 when they already signed out (no-op, no double award).
    """
    attendance = session.get(EventAttendance, (user.id, event.id))
    if attendance is None:
        return None, 0
    if attendance.signed_out_at is not None:
        return attendance, 0

    _, sign_out_points = default_points(event)
    attendance.signed_out_at = utcnow()
    attendance.points_awarded += sign_out_points
    session.add(attendance)
    user.points += sign_out_points
    session.add(user)
    session.commit()
    session.refresh(attendance)
    return attendance, sign_out_points


def scan_counts(session, event_id: int) -> tuple[int, int]:
    """(signed_in, signed_out) counts for one event. A dedicated helper
    instead of re-fetching /events/mine (which would re-mint codes and ship
    every event's secrets over the wire on each poll) or reusing
    EventChairOut.attendee_count (sign-ins only -- wrong number in sign-out
    QR mode)."""
    rows = session.exec(
        select(EventAttendance).where(EventAttendance.event_id == event_id)
    ).all()
    signed_in = len(rows)
    signed_out = sum(1 for row in rows if row.signed_out_at is not None)
    return signed_in, signed_out


def host_scoped_events(session, user: User) -> list[Event]:
    """Events the caller may mint QR codes for / view the roster of.

    The president bypasses entirely — full admin, consistent with
    require_chair. Everyone else gets: committees they actively chair, PLUS
    — if they hold an E-Board role — every E-Board committee (joinable=False,
    see models/committee.py), because officers run GBMs collectively and
    keying on the live role means access self-corrects after an election
    instead of drifting with stale membership rows. Access must go through
    EventHost — an unscoped is_chair check would hand every chair every
    event's codes.
    """
    if user.role == Role.president:
        return session.exec(select(Event).order_by(Event.start_time)).all()

    committee_ids = set(session.exec(
        select(CommitteeMembership.committee_id).where(
            CommitteeMembership.user_id == user.id,
            CommitteeMembership.is_chair == True,  # noqa: E712
            CommitteeMembership.status == True,  # noqa: E712
        )
    ).all())

    if user.role in EBOARD_ROLES:
        committee_ids |= set(session.exec(
            select(Committee.id).where(Committee.joinable == False)  # noqa: E712
        ).all())

    if not committee_ids:
        return []

    return session.exec(
        select(Event)
        .join(EventHost, EventHost.event_id == Event.id)
        .where(EventHost.committee_id.in_(committee_ids))
        .distinct()
        .order_by(Event.start_time)
    ).all()

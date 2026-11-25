import secrets
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from models.committee import Committee, CommitteeMembership
from models.event import Event
from models.event_attendance import EventAttendance
from models.event_host import EventHost
from models.user.user import User
from models.user.user_enums import EBOARD_ROLES, Role
from services.attendance_queries import add_event_with_host, chair_committee, committee_meetings
from services.event_services import live_events
from services.event_tracker_services import SHEET_TZ, to_utc
from services.points import POINT_VALUES, sign_in_points
from services.time_services import utcnow

# "Did you bring a new member?" bonus — capped at once per event by the
# EventAttendance composite PK (user_id, event_id).
NEW_MEMBER_BONUS = POINT_VALUES["new_member"]


def _qr_special_type(event: Event) -> str | None:
    """Stand-in for the points sheet's Special Event Type dropdown, which QR
    events don't have. GM stays case-sensitive: .lower() would also match
    ordinary words like "Segment". Meetings first: a flat 2 whatever the title."""
    if event.is_committee_meeting:
        return "committee meeting"
    if event.event_type == "eboard" and "GM" in event.title:
        return "gm"
    if "study red" in event.title.lower():
        return "study red"
    return None


def is_gm(event: Event) -> bool:
    """The new-member and shirt questions are asked at GMs only."""
    return _qr_special_type(event) == "gm"


def default_points(event: Event) -> tuple[int, int]:
    """(sign_in, sign_out) points for an event, from services/points.py.

    Computed on read for the badge, but what a member banked is frozen in
    EventAttendance.points_awarded at scan time -- changing the rule only
    reprices future scans.
    """
    return (
        sign_in_points(event.event_type, _qr_special_type(event)),
        0 if event.is_committee_meeting else POINT_VALUES["sign_out"],
    )


def resolve_code(session, code: str) -> tuple[Event, str] | None:
    """(event, "in" | "out") for a scanned code, or None if it matches
    neither column. Both columns are unique-indexed, so each branch is an
    index hit; because the action rides on *which code was scanned*, a
    mislabeled QR can't happen.

    Goes through live_events() so a soft-deleted event's code stops working --
    an event pulled from the sheet is off the calendar, and its QR must not
    keep awarding points."""
    event = session.exec(live_events().where(Event.sign_in_code == code)).first()
    if event:
        return event, "in"
    event = session.exec(live_events().where(Event.sign_out_code == code)).first()
    if event:
        return event, "out"
    return None


def _end_of_local_day(start_time: datetime) -> datetime:
    """23:59:59.999999 of the given time's Central calendar day, converted back
    to UTC via the same to_utc() the sheet sync uses. event.start_time is
    naive UTC; plenty of events have no end_time at all, and blank /
    "All Day" / "TBD" sheet times already fell back to local midnight — so
    keying expiry on UTC midnight (instead of the Central day) would expire
    those events before they even started."""
    central_date = start_time.replace(tzinfo=timezone.utc).astimezone(SHEET_TZ).date()
    return to_utc(datetime.combine(central_date, time(23, 59, 59, 999999)))


def is_expired(event: Event, now: datetime | None = None) -> bool:
    """A code stops working at Central midnight of the day the event ends
    (end_time's day, else start_time's) — the whole replacement for
    revocation. No regeneration, no revocation."""
    now = now or utcnow()
    deadline = _end_of_local_day(event.end_time or event.start_time)
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
    wore_shirt: bool = False,
    _retry: bool = True,
) -> tuple[EventAttendance, int]:
    """Stamp signed_in_at -- on a new row, or a sign-out-only one -- and award points.

    Returns (row, points_awarded_by_this_call). points is 0 when already
    signed in -- a success ("already signed in"), not a failure. GM-only
    answers are dropped elsewhere: wore_shirt stays NULL, the new-member claim False.
    """
    attendance = _locked_attendance(session, user, event)
    if attendance is not None and attendance.signed_in_at is not None:
        return attendance, 0

    gm = is_gm(event)
    brought_new_member = brought_new_member and gm
    points = sign_in_points(
        event.event_type, _qr_special_type(event),
        brought_new_member=brought_new_member, wore_shirt=wore_shirt,
    )

    if attendance is None:
        attendance = EventAttendance(user_id=user.id, event_id=event.id)
    attendance.signed_in_at = utcnow()
    attendance.brought_new_member = brought_new_member
    attendance.new_member_name = (new_member_name or "").strip() or None if brought_new_member else None
    attendance.wore_shirt = wore_shirt if gm else None
    attendance.points_awarded += points
    if not _commit_award(session, user, attendance, points):
        if not _retry:
            raise RuntimeError("attendance insert conflicted twice")
        return record_sign_in(
            session, user, event, brought_new_member, new_member_name, wore_shirt, _retry=False,
        )
    return attendance, points


def record_sign_out(session, user: User, event: Event, _retry: bool = True) -> tuple[EventAttendance, int]:
    """Stamp signed_out_at -- on a new row if the member never signed in -- and
    award sign-out points. points is 0 when they already signed out."""
    attendance = _locked_attendance(session, user, event)
    if attendance is not None and attendance.signed_out_at is not None:
        return attendance, 0

    _, sign_out_points = default_points(event)
    if attendance is None:
        attendance = EventAttendance(user_id=user.id, event_id=event.id)
    attendance.signed_out_at = utcnow()
    attendance.points_awarded += sign_out_points
    if not _commit_award(session, user, attendance, sign_out_points):
        if not _retry:
            raise RuntimeError("attendance insert conflicted twice")
        return record_sign_out(session, user, event, _retry=False)
    return attendance, sign_out_points


def _locked_attendance(session, user: User, event: Event) -> EventAttendance | None:
    # FOR UPDATE: a simultaneous scan waits here until this one commits, then
    # sees the stamped row -- so the "already recorded" checks can't double-award.
    return session.get(EventAttendance, (user.id, event.id), with_for_update=True)


def _commit_award(session, user: User, attendance: EventAttendance, points: int) -> bool:
    """Commit the row and the points together. False when a simultaneous first
    scan inserted the row first (no row existed to lock); the caller retries."""
    session.add(attendance)
    user.points += points
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return False
    session.refresh(attendance)
    return True


def scan_counts(session, event_id: int) -> tuple[int, int]:
    """(signed_in, signed_out) counts for one event. A dedicated helper
    instead of re-fetching /events/mine (which would re-mint codes and ship
    every event's secrets over the wire on each poll) or reusing
    EventChairOut.attendee_count (sign-ins only -- wrong number in sign-out
    QR mode). COUNT(column) skips NULLs, so a sign-out-only row isn't a sign-in."""
    signed_in, signed_out = session.exec(
        select(func.count(EventAttendance.signed_in_at), func.count(EventAttendance.signed_out_at))
        .where(EventAttendance.event_id == event_id)
    ).one()
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
        return session.exec(live_events().order_by(Event.start_time)).all()

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
        live_events()
        .join(EventHost, EventHost.event_id == Event.id)
        .where(EventHost.committee_id.in_(committee_ids))
        .distinct()
        .order_by(Event.start_time)
    ).all()


def ensure_event_codes(session, events: list[Event]) -> None:
    """Mint sign-in/sign-out codes for any event that doesn't have them yet.

    sync_events mints codes at creation time, but that only covers events
    that came from the tracker sheet -- seeded and hand-added rows have NULL
    in both columns, and EventChairOut declares them non-optional, so a
    president (who is scoped to every event) loading /events/mine used to get
    a 500 from response validation rather than a card. Idempotent: an event
    that already has both codes is untouched, and the commit is skipped
    entirely when nothing was minted, so the read paths stay read-only in the
    common case.
    """
    minted = False
    for event in events:
        missing_out = not event.sign_out_code and not event.is_committee_meeting  # meetings are sign-in only
        if event.sign_in_code and not missing_out:
            continue
        event.sign_in_code = event.sign_in_code or secrets.token_urlsafe(nbytes=16)
        if missing_out:
            event.sign_out_code = secrets.token_urlsafe(nbytes=16)
        session.add(event)
        minted = True
    if minted:
        session.commit()


def attendee_counts(session, event_ids: list[int]) -> dict[int, int]:
    """{event_id: attendee count} for a batch of events, in ONE query. An
    attendee is anyone with a row -- signed in, signed out, or both.

    The chair Events page lists every chapter event, so a per-event count
    (what /events/mine originally did) is an N+1 that grows with the
    semester. Events with no attendance simply don't appear in the result --
    callers should read it with .get(id, 0)."""
    if not event_ids:
        return {}
    rows = session.exec(
        select(EventAttendance.event_id, func.count())
        .where(EventAttendance.event_id.in_(event_ids))
        .group_by(EventAttendance.event_id)
    ).all()
    return {event_id: count for event_id, count in rows}


def code_scoped_events(session, user: User) -> list[Event]:
    """Events whose QR codes the caller may PRESENT, which is a wider set
    than host_scoped_events.

    An E-Board member gets every live event: officers cover the door at
    events they didn't organize, and an officer who can't pull up the sign-in
    QR is a member who can't earn points. Everyone else (a committee chair)
    gets exactly what they host.

    Deliberately separate from host_scoped_events, which stays narrow and
    still gates GET /events/{id}/attendance: a roster carries names and
    personal emails, while a QR code and its scan counter carry neither. The
    two questions are "may you open the door" and "may you read who came
    through it", and only the second is a privacy boundary.
    """
    if user.role in EBOARD_ROLES:
        return session.exec(live_events().order_by(Event.start_time)).all()
    return host_scoped_events(session, user)


def create_committee_meeting(session, user: User, start_time: datetime) -> Event | None:
    """A sign-in-only meeting for the caller's own committee, or None when they
    chair no committee (the route's 403). start_time must be timezone-aware."""
    committee = chair_committee(session, user.role)
    if committee is None:
        return None
    meeting = Event(
        title=f"{committee.name} Meeting",
        start_time=start_time.astimezone(timezone.utc).replace(tzinfo=None),
        # Same host slug the sheet sync stores: social_chair -> "social".
        event_type=committee.chair_role.name.removesuffix("_chair"),
        sign_in_code=secrets.token_urlsafe(nbytes=16),
        is_committee_meeting=True,
    )
    add_event_with_host(session, meeting, committee.id)
    session.commit()
    session.refresh(meeting)
    return meeting


def list_committee_meetings(session, user: User) -> list[Event] | None:
    """The caller's committee's live meetings, or None when they chair no committee."""
    committee = chair_committee(session, user.role)
    if committee is None:
        return None
    return committee_meetings(session, committee.id)

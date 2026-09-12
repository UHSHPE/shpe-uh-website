from models.event import Event, EventAllOut, EventChairOut, EventOut
from models.event_attendance import (
    AttendanceOut,
    AttendRequest,
    AttendResult,
    CodePreviewOut,
    EventAttendance,
)
from models.event_reminder import EventReminder, EventReminderOut
from models.event_stats import EventStatsOut
from models.user.user import User
from services import attendance_services, event_stats_services
from services.event_services import get_live_event, live_events
from services.dependencies import (
    SessionDependencies,
    get_current_user,
    get_optional_user,
    require_event_host,
)
from services.rate_limit import limiter, ATTEND_LIMIT, CODE_PREVIEW_LIMIT
from services.reminder_services import compute_remind_at
from services.time_services import utcnow


from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import select


from datetime import timedelta
from typing import Annotated

router = APIRouter(prefix="/events", tags=["Events"])


def _event_out(event: Event) -> EventOut:
    """EventOut with points_value computed from the rule (no per-event
    overrides, nothing new stored on Event) instead of the raw, always-0 DB
    column."""
    sign_in_points, _ = attendance_services.default_points(event)
    return EventOut(
        id=event.id,
        title=event.title,
        description=event.description,
        location=event.location,
        start_time=event.start_time,
        end_time=event.end_time,
        points_value=sign_in_points,
        event_type=event.event_type,
    )


@router.get('/upcoming', response_model=list[EventOut])
async def get_upcoming_events(
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
    days: int = 7,
):
    now = utcnow()
    cutoff = now + timedelta(days=days)
    stmt = (
        live_events()
        .where(Event.start_time >= now, Event.start_time <= cutoff)
        .order_by(Event.start_time)
    )
    return [_event_out(e) for e in session.exec(stmt).all()]


# Path is '' (not '/') so the full path is exactly /events, which is what every
# caller uses. With '/' the router serves /events/ and answers /events with a
# 307 — and behind Railway that Location comes back as http://, which the
# browser blocks as mixed content on an https page. See "What NOT to do".
@router.get('', response_model=list[EventOut])
async def get_all_events(session: SessionDependencies):
    return [_event_out(e) for e in session.exec(live_events().order_by(Event.start_time)).all()]


# --- QR attendance & points ---

@router.post('/attend', response_model=AttendResult)
@limiter.limit(ATTEND_LIMIT)
async def attend_event(
    request: Request,
    payload: AttendRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    resolved = attendance_services.resolve_code(session, payload.code)
    if resolved is None:
        # Generic 404 -- don't distinguish "no such code" from anything else.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid code")
    event, action = resolved

    if attendance_services.is_expired(event):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This code has expired")

    # The frontend normally never hits this -- the preview endpoint reports
    # state: "not_started" and the page renders a screen without POSTing.
    # This is the backstop against a direct POST.
    if attendance_services.is_not_started(event):
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Check-in hasn't opened yet",
        )

    if action == "in":
        attendance, points = attendance_services.record_sign_in(
            session,
            user,
            event,
            brought_new_member=payload.brought_new_member,
            new_member_name=payload.new_member_name,
        )
    else:
        attendance, points = attendance_services.record_sign_out(session, user, event)
        if attendance is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sign in before signing out",
            )

    session.refresh(user)
    return AttendResult(
        action="sign_in" if action == "in" else "sign_out",
        status="recorded" if points > 0 else "already_recorded",
        event_id=event.id,
        event_title=event.title,
        points_awarded=points,
        total_points=user.points,
        signed_in_at=attendance.signed_in_at,
        signed_out_at=attendance.signed_out_at,
    )


@router.get('/mine', response_model=list[EventChairOut])
async def get_my_hosted_events(
    user: Annotated[User, Depends(require_event_host)],
    session: SessionDependencies,
):
    """Events this chair/E-Board member hosts, WITH sign-in/out codes. Codes
    are minted when the event is created, or lazily here for an event that
    predates that (seeded/hand-added rows)."""
    events = attendance_services.host_scoped_events(session, user)
    # Seeded and hand-added events have no codes (only sync_events mints
    # them at creation), and EventChairOut declares both non-optional -- so
    # without this a president, who is scoped to every event, 500s here on
    # response validation.
    attendance_services.ensure_event_codes(session, events)
    counts = attendance_services.attendee_counts(session, [e.id for e in events])

    out = []
    for event in events:
        sign_in_points, _ = attendance_services.default_points(event)
        attendee_count = counts.get(event.id, 0)
        out.append(EventChairOut(
            id=event.id,
            title=event.title,
            description=event.description,
            location=event.location,
            start_time=event.start_time,
            end_time=event.end_time,
            points_value=sign_in_points,
            event_type=event.event_type,
            sign_in_code=event.sign_in_code,
            sign_out_code=event.sign_out_code,
            attendee_count=attendee_count,
        ))
    return out


@router.get('/all', response_model=list[EventAllOut])
async def get_all_events_for_chairs(
    user: Annotated[User, Depends(require_event_host)],
    session: SessionDependencies,
):
    """Every chapter event for a chair/E-Board member — same gate as
    /events/mine, but each row also reports what this caller may do with it.

    An E-Board member gets the sign-in/out codes for every event (officers
    cover the door at events they didn't organize; see
    attendance_services.code_scoped_events), a chair gets them only for what
    they host, and everyone else on a given row gets nulls. can_view_roster
    tracks the narrower host_scoped_events set, since a roster carries names
    and emails while a code doesn't. Both are advisory for the UI — every
    downstream endpoint re-checks.
    """
    events = session.exec(live_events().order_by(Event.start_time)).all()
    coded = attendance_services.code_scoped_events(session, user)
    attendance_services.ensure_event_codes(session, coded)
    coded_ids = {e.id for e in coded}
    roster_ids = {e.id for e in attendance_services.host_scoped_events(session, user)}
    counts = attendance_services.attendee_counts(session, [e.id for e in events])

    out = []
    for event in events:
        base = _event_out(event)
        may_see_codes = event.id in coded_ids
        out.append(EventAllOut(
            **base.model_dump(),
            sign_in_code=event.sign_in_code if may_see_codes else None,
            sign_out_code=event.sign_out_code if may_see_codes else None,
            attendee_count=counts.get(event.id, 0),
            can_view_roster=event.id in roster_ids,
        ))
    return out


@router.get('/code/{code}', response_model=CodePreviewOut)
@limiter.limit(CODE_PREVIEW_LIMIT)
async def get_code_preview(
    request: Request,
    code: str,
    session: SessionDependencies,
    user: Annotated[User | None, Depends(get_optional_user)],
):
    """Public, read-only preview of a scanned code -- the mobile flow needs
    to show event name/time/location BEFORE recording anything, since
    POST /events/attend records immediately. Anonymous callers get the
    event; a bearer token additionally fills the caller's own timestamps so
    the page can jump straight to "Already checked in" without a wasted
    confirm tap.

    Security: this is a public code oracle, but the only fields it leaks to
    someone already holding a code (title/time/location) are already public
    via GET /events -- the incremental leak is zero. Codes are 128-bit
    secrets.token_urlsafe(16), so enumeration is infeasible; the rate limit
    is belt-and-braces. Declared BEFORE /{event_id}/attendance for route-
    ordering discipline, same as /shop/orders/me before /shop/orders/{code}.
    """
    resolved = attendance_services.resolve_code(session, code)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid code")
    event, action = resolved

    sign_in_points, sign_out_points = attendance_services.default_points(event)
    points_value = sign_in_points if action == "in" else sign_out_points

    if attendance_services.is_expired(event):
        state = "ended"
    elif attendance_services.is_not_started(event):
        state = "not_started"
    else:
        state = "ok"

    signed_in_at = None
    signed_out_at = None
    if user is not None:
        attendance = session.get(EventAttendance, (user.id, event.id))
        if attendance is not None:
            signed_in_at = attendance.signed_in_at
            signed_out_at = attendance.signed_out_at

    return CodePreviewOut(
        action="sign_in" if action == "in" else "sign_out",
        event_id=event.id,
        title=event.title,
        location=event.location,
        start_time=event.start_time,
        end_time=event.end_time,
        event_type=event.event_type,
        points_value=points_value,
        state=state,
        signed_in_at=signed_in_at,
        signed_out_at=signed_out_at,
    )


@router.get('/{event_id}/scan-count')
async def get_event_scan_count(
    event_id: int,
    user: Annotated[User, Depends(require_event_host)],
    session: SessionDependencies,
):
    """Live scan counter for the QR modal / present view. Re-fetching
    /events/mine would re-mint codes and ship every event's secrets over
    the wire on each poll, and EventChairOut.attendee_count only counts
    sign-ins (wrong number in sign-out QR mode) -- hence this dedicated,
    per-event endpoint. Same two-layer guard as /events/{id}/attendance:
    require_event_host (coarse role gate) plus host_scoped_events
    (per-event scoping)."""
    event = get_live_event(session, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    # Scoped to code_scoped_events, NOT host_scoped_events: this counter is
    # the readout beside a presented QR, so anyone who may present the code
    # must be able to poll it, and two integers identify nobody. The roster
    # endpoint below keeps the narrower scope.
    coded_ids = {e.id for e in attendance_services.code_scoped_events(session, user)}
    if event_id not in coded_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this event's attendance",
        )

    signed_in, signed_out = attendance_services.scan_counts(session, event_id)
    return {"signed_in": signed_in, "signed_out": signed_out}


@router.get('/{event_id}/stats', response_model=EventStatsOut)
async def get_event_stats(
    event_id: int,
    user: Annotated[User, Depends(require_event_host)],
    session: SessionDependencies,
):
    """Aggregate attendance statistics for one event — turnout, dwell time,
    classification / college / major / membership breakdowns.

    Gated on require_event_host alone, with NO per-event scoping, which is
    the deliberate difference from /attendance below. Everything here is a
    count or an average: there is no name, email, PSID or user id anywhere in
    EventStatsOut, so a chair reading another committee's numbers learns how
    many juniors showed up, never who. That is also the constraint to keep —
    a field that identifies an attendee belongs on AttendanceOut, behind the
    host scoping, not here.
    """
    event = get_live_event(session, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    return event_stats_services.build_event_stats(session, event)


@router.get('/{event_id}/attendance', response_model=list[AttendanceOut])
async def get_event_attendance(
    event_id: int,
    user: Annotated[User, Depends(require_event_host)],
    session: SessionDependencies,
):
    """Roster for one event, plus who claimed a new member and their names.
    Scoped through EventHost (attendance_services.host_scoped_events) —
    same as /events/mine — so a chair can't read another committee's
    roster. The president bypasses, same as everywhere else."""
    event = get_live_event(session, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    hosted_ids = {e.id for e in attendance_services.host_scoped_events(session, user)}
    if event_id not in hosted_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this event's attendance",
        )

    rows = session.exec(
        select(EventAttendance, User)
        .join(User, User.id == EventAttendance.user_id)
        .where(EventAttendance.event_id == event_id)
        .order_by(EventAttendance.signed_in_at)
    ).all()

    return [
        AttendanceOut(
            user_id=attendee.id,
            first_name=attendee.first_name,
            last_name=attendee.last_name,
            personal_email=attendee.personal_email,
            signed_in_at=att.signed_in_at,
            signed_out_at=att.signed_out_at,
            brought_new_member=att.brought_new_member,
            new_member_name=att.new_member_name,
            points_awarded=att.points_awarded,
        )
        for att, attendee in rows
    ]


def get_active_reminder(session, user_id: int, event_id: int) -> EventReminder | None:
    stmt = select(EventReminder).where(
        EventReminder.user_id == user_id,
        EventReminder.event_id == event_id,
        EventReminder.sent_at == None,  # noqa: E711
    )
    return session.exec(stmt).first()


@router.get('/reminders/me', response_model=list[EventReminderOut])
async def get_my_reminders(
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    stmt = select(EventReminder).where(
        EventReminder.user_id == user.id,
        EventReminder.sent_at == None,  # noqa: E711
    )
    return session.exec(stmt).all()


@router.post('/{event_id}/remind', response_model=EventReminderOut, status_code=status.HTTP_201_CREATED)
async def set_event_reminder(
    event_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    event = get_live_event(session, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if get_active_reminder(session, user.id, event_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reminder already set for this event")

    reminder = EventReminder(
        user_id=user.id,
        event_id=event_id,
        remind_at=compute_remind_at(event.start_time),
    )
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder


@router.delete('/{event_id}/remind')
async def cancel_event_reminder(
    event_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    reminder = get_active_reminder(session, user.id, event_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active reminder for this event")

    session.delete(reminder)
    session.commit()
    return {"detail": "Reminder cancelled"}

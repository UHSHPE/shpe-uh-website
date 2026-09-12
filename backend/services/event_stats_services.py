"""Aggregate attendance statistics for one event.

Deliberately aggregate-ONLY: counts and averages, never a name, email, PSID
or user id. That is what lets GET /events/{id}/stats sit behind the coarse
require_event_host gate (any chair or E-Board member, any event) while
GET /events/{id}/attendance stays scoped through EventHost -- a roster
identifies people, a histogram doesn't. Don't add a field here that names
someone; add it to AttendanceOut instead, where the scoping already exists.
"""

from collections import Counter

from sqlalchemy import func
from sqlmodel import select

from models.event import Event
from models.event_attendance import EventAttendance
from models.event_stats import EventStatsOut, StatCount
from models.user.user import User
from models.user.user_enums import Classification, Colleges, MembershipStatus

# How many majors the breakdown names before collapsing the tail into
# `other_majors`. The chapter spans ~40 majors across three colleges, so a
# full list is a wall of ones; five is what the Events page charts.
TOP_MAJORS = 5


def _ordered_counts(counter: Counter, order) -> list[StatCount]:
    """Counts in a fixed canonical order, INCLUDING zeros.

    Classification/college/membership are small closed sets and the frontend
    draws them as a bar row, so a missing bucket has to read as "nobody",
    not as "this category doesn't exist" -- an event with no freshmen should
    show an empty Freshman bar rather than silently dropping the column.
    """
    return [StatCount(label=value.value, count=counter.get(value, 0)) for value in order]


def _top_counts(counter: Counter, limit: int) -> tuple[list[StatCount], int]:
    """(top `limit` entries desc, total count in the collapsed tail).

    Ties break alphabetically so the order is stable across reloads -- a
    Counter's insertion order would otherwise reshuffle the chart whenever
    the roster query came back in a different order.
    """
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    top = [StatCount(label=label, count=count) for label, count in ranked[:limit]]
    tail = sum(count for _, count in ranked[limit:])
    return top, tail


def _first_time_attendee_count(session, event: Event, attendee_ids: list[int]) -> int:
    """How many of this event's attendees had never checked in anywhere before.

    Compares each attendee's earliest sign-in across ALL events against this
    event's id. Deliberately NOT filtered on Event.deleted_at, for the same
    reason leaderboard_services._points_by_user_and_type isn't: an event
    later cleared out of the tracker sheet was still someone's first event,
    and hiding it would promote their second event to "first" retroactively.
    """
    if not attendee_ids:
        return 0

    rows = session.exec(
        select(EventAttendance.user_id, func.min(EventAttendance.signed_in_at))
        .where(EventAttendance.user_id.in_(attendee_ids))
        .group_by(EventAttendance.user_id)
    ).all()
    earliest = dict(rows)

    first_timers = 0
    for attendance in session.exec(
        select(EventAttendance).where(
            EventAttendance.event_id == event.id,
            EventAttendance.user_id.in_(attendee_ids),
        )
    ).all():
        if earliest.get(attendance.user_id) == attendance.signed_in_at:
            first_timers += 1
    return first_timers


def build_event_stats(session, event: Event) -> EventStatsOut:
    """Everything the Events page's statistics panel renders, in 3 queries.

    Demographics are read LIVE off the User row rather than snapshotted at
    scan time, so a member who advances from junior to senior moves buckets
    in every past event's chart. That's the cheaper and more useful reading
    for a chapter ("who comes to outreach events") -- but it does mean these
    numbers are a picture of the roster today, not of the room that night.
    """
    rows = session.exec(
        select(EventAttendance, User)
        .join(User, User.id == EventAttendance.user_id)
        .where(EventAttendance.event_id == event.id)
    ).all()

    classifications: Counter = Counter()
    colleges: Counter = Counter()
    majors: Counter = Counter()
    membership: Counter = Counter()
    national_members = 0
    guests_brought = 0
    total_points = 0
    signed_out = 0
    durations: list[float] = []

    for attendance, attendee in rows:
        classifications[attendee.classification] += 1
        colleges[attendee.college] += 1
        majors[attendee.major.strip()] += 1
        membership[attendee.is_returning] += 1
        if attendee.is_national_member:
            national_members += 1
        if attendance.brought_new_member:
            guests_brought += 1
        total_points += attendance.points_awarded
        if attendance.signed_out_at is not None:
            signed_out += 1
            durations.append((attendance.signed_out_at - attendance.signed_in_at).total_seconds() / 60)

    top_majors, other_majors = _top_counts(majors, TOP_MAJORS)
    attendee_ids = [attendee.id for _, attendee in rows]
    first_time = _first_time_attendee_count(session, event, attendee_ids)

    return EventStatsOut(
        event_id=event.id,
        title=event.title,
        signed_in=len(rows),
        signed_out=signed_out,
        still_signed_in=len(rows) - signed_out,
        guests_brought=guests_brought,
        total_points_awarded=total_points,
        # Averaged over completed visits only -- someone who never scanned
        # out has no duration, and counting them as 0 would drag the average
        # toward "nobody stayed" on exactly the events where sign-out was
        # never announced.
        average_minutes=round(sum(durations) / len(durations)) if durations else None,
        first_time_attendees=first_time,
        returning_attendees=len(rows) - first_time,
        national_members=national_members,
        classifications=_ordered_counts(classifications, list(Classification)),
        colleges=_ordered_counts(colleges, list(Colleges)),
        membership=_ordered_counts(membership, list(MembershipStatus)),
        top_majors=top_majors,
        other_majors=other_majors,
        distinct_majors=len(majors),
    )

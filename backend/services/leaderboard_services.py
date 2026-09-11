"""Chapter points leaderboard: every member's total, broken down by pillar.

The breakdown reconciles with the totals because User.points is mutated in
exactly two places, both in attendance_services (record_sign_in and
record_sign_out), and both write the same figure to
EventAttendance.points_awarded. So summing points_awarded per member equals
their User.points, and grouping that sum by the event's pillar splits the
total without inventing anything. If a third writer of User.points is ever
added it MUST also write an EventAttendance row, or the columns silently stop
adding up to the total and there is no error to notice.

Note the membershpe page advertises point sources this app does not implement
(wearing a shirt to a GBM, submitting pictures, elections). Those are awarded
off-system and never reach User.points, so they appear nowhere here.
"""

from sqlmodel import Session, func, select

from models.event import Event
from models.event_attendance import EventAttendance
from models.user.user import User
from services.pillars import (
    PILLAR_KEYS,
    PILLAR_POINTS,
    PILLARS,
    deserialize_pillars,
)

# FALLBACK ONLY: event_type slug -> pillar key, used when the sheet's
# PILLAR(S) cell was blank or unrecognized (40 of 108 live rows). The real
# pillar on Event.pillars always wins; without this fallback those rows
# would all land in "Other" and the breakdown would be mostly noise.
# event_type slug -> pillar key. Keys are the slugs produced by
# event_tracker_services.get_event_type() (a Role name minus "_chair", plus
# the "eboard" catch-all) -- the same set frontend/src/utils/events.js labels.
#
# This mapping is a chapter judgement call, not a fact derivable from the
# code: nothing in the sheet or the Role enum records which pillar an event
# serves. Editing a row here silently reclassifies every past event of that
# type, since the breakdown is computed on read rather than stored.
EVENT_TYPE_PILLAR = {
    # Chapter Development -- internal community and member experience
    "member_relations": "chapter",
    "marketing": "chapter",
    "social": "chapter",
    "athletic": "chapter",
    "shpetina": "chapter",
    # Academic Development
    "academic": "academic",
    "mentorshpe": "academic",
    # Community Development -- outward-facing service
    "outreach": "community",
    "shpe_jr": "community",
    # Professional Development
    "professional": "professional",
    "career_fair": "professional",
    "eec": "professional",
    # Leadership Development
    "eboard": "leadership",
    "projects": "leadership",
    "web_dev": "leadership",
}

# Points from an event whose type is missing or unrecognised (a new dropdown
# option in the tracker sheet, a hand-added event with no type) still count
# toward the member's total -- they just have no column to land in. Surfaced
# as its own field so the UI can show the total honestly rather than
# displaying five columns that quietly fail to add up.
UNCATEGORIZED = "uncategorized"


def pillar_for_event_type(event_type: str | None) -> str:
    """Pillar key inferred from an event_type slug, or UNCATEGORIZED.

    The inference fallback -- see EVENT_TYPE_PILLAR above.
    """
    if not event_type:
        return UNCATEGORIZED
    return EVENT_TYPE_PILLAR.get(event_type.strip().lower(), UNCATEGORIZED)


def _winning_pillar(keys: list[str]) -> str:
    """The pillar a multi-pillar event's points are filed under.

    Must be the SAME pillar attendance_services.default_points scored the
    event on (highest points wins), or a member's row would show points in a
    column that isn't where they came from. Ties break on PILLAR_KEYS order
    so the choice is deterministic rather than dict-insertion order.
    """
    return max(keys, key=lambda k: (PILLAR_POINTS[k], -PILLAR_KEYS.index(k)))


def pillar_for_event(event_type: str | None, pillars: str | None) -> str:
    """Which breakdown column an event's points belong in.

    The sheet's own PILLAR(S) value wins; the event_type inference is only
    consulted when the sheet said nothing recognizable.
    """
    keys = deserialize_pillars(pillars)
    if keys:
        return _winning_pillar(keys)
    return pillar_for_event_type(event_type)


def _points_by_user_and_type(session: Session) -> dict[int, dict[str, int]]:
    """{user_id: {pillar_key: points}} in ONE grouped query.

    Deliberately does NOT filter Event.deleted_at. Every other event read path
    hides soft-deleted events, but points already awarded were really earned:
    clearing a row out of the tracker sheet must not retroactively rewrite a
    member's history, and User.points still includes them, so filtering here
    is exactly what would make the columns stop summing to the total.
    """
    stmt = (
        select(
            EventAttendance.user_id,
            Event.event_type,
            Event.pillars,
            func.sum(EventAttendance.points_awarded),
        )
        .join(Event, Event.id == EventAttendance.event_id)
        .group_by(EventAttendance.user_id, Event.event_type, Event.pillars)
    )
    out: dict[int, dict[str, int]] = {}
    for user_id, event_type, pillars, total in session.exec(stmt).all():
        bucket = out.setdefault(user_id, {})
        key = pillar_for_event(event_type, pillars)
        bucket[key] = bucket.get(key, 0) + int(total or 0)
    return out


def build_leaderboard(session: Session) -> list[dict]:
    """Every verified member, ranked by points desc then name.

    Unverified accounts are excluded: they cannot log in, always hold 0
    points, and listing them would publish pending signups on a public page.

    Ties share a rank (two members on 40 points are both #3) and the next
    member takes the rank their position implies -- standard competition
    ranking, so the numbers match how the chapter announces its top members.
    """
    members = session.exec(
        select(User)
        .where(User.email_verified == True)  # noqa: E712 -- SQL, not Python
        .order_by(User.points.desc(), User.first_name, User.last_name)
    ).all()
    by_user = _points_by_user_and_type(session)

    entries: list[dict] = []
    previous_points: int | None = None
    previous_rank = 0
    for position, member in enumerate(members, start=1):
        buckets = by_user.get(member.id, {})
        rank = previous_rank if member.points == previous_points else position
        previous_points, previous_rank = member.points, rank
        entries.append({
            "rank": rank,
            "name": f"{member.first_name} {member.last_name}".strip(),
            "total_points": member.points,
            "points_by_pillar": {key: buckets.get(key, 0) for key in PILLAR_KEYS},
            "uncategorized_points": buckets.get(UNCATEGORIZED, 0),
        })
    return entries

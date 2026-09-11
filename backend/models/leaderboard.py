"""Response schemas for GET /leaderboard. No table -- the leaderboard is
computed on read from User.points and EventAttendance.points_awarded, so
there is nothing to register in database.py.

PUBLIC ENDPOINT. Every field here is visible to anonymous visitors, so this
carries name and points and nothing else -- no id, no email, no PSID, no
classification. Adding a field to help the UI is how a public roster turns
into a public directory; test_leaderboard_exposes_no_personal_details pins
the shape.
"""

from sqlmodel import SQLModel


class PillarOut(SQLModel):
    key: str
    label: str
    short: str


class LeaderboardEntry(SQLModel):
    rank: int
    name: str
    total_points: int
    # pillar key -> points earned under it. Always carries every key in
    # PILLAR_KEYS (zero-filled) so the frontend can render columns without
    # per-cell existence checks.
    points_by_pillar: dict[str, int]
    # Points from events whose type is unrecognised or unset. Usually 0; kept
    # separate so the five columns never have to silently absorb them, and
    # the UI can explain a row whose columns don't sum to its total.
    uncategorized_points: int


class LeaderboardOut(SQLModel):
    """Pillar definitions ride along with the rows so the column set has ONE
    source of truth (services/leaderboard_services.PILLARS) instead of a
    mirrored copy in the frontend that drifts the day a pillar is renamed."""
    pillars: list[PillarOut]
    entries: list[LeaderboardEntry]

"""Response schemas for GET /leaderboard. No table -- the leaderboard is
computed on read from User.points, so there is nothing to register in
database.py.

PUBLIC ENDPOINT. Every field here is visible to anonymous visitors, so this
carries name and points and nothing else -- no id, no email, no PSID, no
classification. Adding a field to help the UI is how a public roster turns
into a public directory; test_leaderboard_exposes_no_personal_details pins
the shape.
"""

from sqlmodel import SQLModel


class LeaderboardEntry(SQLModel):
    rank: int
    name: str
    total_points: int


class LeaderboardOut(SQLModel):
    entries: list[LeaderboardEntry]

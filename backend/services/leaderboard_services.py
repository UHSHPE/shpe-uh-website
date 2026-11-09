"""Chapter points leaderboard: every member ranked by their total.

The total is User.points, which every source writes to -- QR attendance
(attendance_services), Google Forms (forms_import_services) and approved
gallery photos (gallery_services) -- so no per-source breakdown is needed.

Submitting pictures and elections are still awarded off-system and never
reach User.points.
"""

from sqlmodel import Session, select

from models.user.user import User


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

    entries: list[dict] = []
    previous_points: int | None = None
    previous_rank = 0
    for position, member in enumerate(members, start=1):
        rank = previous_rank if member.points == previous_points else position
        previous_points, previous_rank = member.points, rank
        entries.append({
            "rank": rank,
            "name": f"{member.first_name} {member.last_name}".strip(),
            "total_points": member.points,
        })
    return entries

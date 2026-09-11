from fastapi import APIRouter

from models.leaderboard import LeaderboardOut
from services import leaderboard_services
from services.dependencies import SessionDependencies

router = APIRouter(tags=["Leaderboard"])


@router.get("/leaderboard", response_model=LeaderboardOut)
async def get_leaderboard(session: SessionDependencies):
    """Public chapter points leaderboard -- every verified member, ranked,
    with a per-pillar breakdown of where their points came from.

    Public by explicit choice (it renders on /membershpe, an unauthenticated
    page), which is why the schema carries names and points only. Two queries
    total regardless of chapter size: one for members, one grouped aggregate
    for the breakdown -- do not turn this into a per-member points lookup.
    """
    return LeaderboardOut(
        pillars=leaderboard_services.PILLARS,
        entries=leaderboard_services.build_leaderboard(session),
    )

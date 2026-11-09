from fastapi import APIRouter

from models.leaderboard import LeaderboardOut
from services import leaderboard_services
from services.dependencies import SessionDependencies

router = APIRouter(tags=["Leaderboard"])


@router.get("/leaderboard", response_model=LeaderboardOut)
async def get_leaderboard(session: SessionDependencies):
    """Public chapter points leaderboard -- every verified member, ranked by
    total points.

    Public by explicit choice (it renders on /membershpe, an unauthenticated
    page), which is why the schema carries names and points only. One query
    regardless of chapter size -- do not turn this into a per-member lookup.
    """
    return LeaderboardOut(entries=leaderboard_services.build_leaderboard(session))

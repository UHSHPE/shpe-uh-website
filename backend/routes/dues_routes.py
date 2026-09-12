"""Let chapter administrators trigger the membership-sheet dues import."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from models.dues_import import DuesSyncResult
from models.user.user import User
from services import dues_import_services
from services.dependencies import SessionDependencies, require_role_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/dues", tags=["Dues"])


@router.post("/sync", response_model=DuesSyncResult)
def sync_membership_dues(
    actor: Annotated[User, Depends(require_role_admin)],
    session: SessionDependencies,
) -> DuesSyncResult:
    """Run the dues import for an authorized chapter administrator.

    Args:
        actor: President or vice president requesting the sync.
        session: Database session for the import.
    Returns:
        An aggregate import summary, or an HTTP error when the import cannot run.
    """
    try:
        result = dues_import_services.sync_dues(session)
    except Exception:
        logger.exception("Admin dues sync failed")
        raise HTTPException(status_code=503, detail="Dues sync failed; please try again later.") from None
    errors = {
        "unconfigured": (503, "Dues sheet integration is not configured."),
        "invalid_sheet": (422, result.message),
        "busy": (409, "A dues sync is already running."),
    }
    if result.status in errors:
        status_code, message = errors[result.status]
        raise HTTPException(status_code=status_code, detail=message)
    logger.info("Dues sync requested by administrator %s", actor.id)
    return result

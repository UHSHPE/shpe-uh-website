from models.notification import Notification, NotificationOut
from models.user.user import User
from services.dependencies import SessionDependencies, get_current_user


from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select


from typing import Annotated

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get('', response_model=list[NotificationOut])
async def get_notifications(
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    return session.exec(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    ).all()


@router.post('/{notification_id}/read')
async def mark_notification_read(
    notification_id: int,
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDependencies,
):
    notification = session.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    session.add(notification)
    session.commit()
    return {"ok": True}
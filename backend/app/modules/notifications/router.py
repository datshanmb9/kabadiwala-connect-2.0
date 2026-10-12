from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_role
from app.modules.notifications import service
from app.modules.notifications.schemas import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications_route(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_role("HOME_USER", "RECYCLER", "COLLECTOR")),
):
    result = await service.list_notifications(current_user["user_id"], limit=limit, offset=offset)
    return NotificationListResponse(**result)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count_route(
    current_user: dict = Depends(require_role("HOME_USER", "RECYCLER", "COLLECTOR")),
):
    return UnreadCountResponse(unread_count=await service.unread_count(current_user["user_id"]))


@router.patch("/read-all", response_model=MarkAllReadResponse)
async def mark_all_read_route(
    current_user: dict = Depends(require_role("HOME_USER", "RECYCLER", "COLLECTOR")),
):
    return MarkAllReadResponse(**await service.mark_all_read(current_user["user_id"]))


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read_route(
    notification_id: str,
    current_user: dict = Depends(require_role("HOME_USER", "RECYCLER", "COLLECTOR")),
):
    result = await service.mark_read(
        user_id=current_user["user_id"],
        notification_id=notification_id,
    )
    return NotificationResponse(**result)

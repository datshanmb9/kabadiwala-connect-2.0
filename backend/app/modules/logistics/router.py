from fastapi import APIRouter, Depends, Header

from app.core.rbac import require_role
from app.modules.logistics import service
from app.modules.logistics.schemas import LogisticsBookingResponse, LogisticsBookRequest

router = APIRouter(prefix="/api/v1/logistics", tags=["logistics"])


@router.post("/{lot_id}/book", response_model=LogisticsBookingResponse)
async def book_logistics_route(
    lot_id: str,
    body: LogisticsBookRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RECYCLER")),
):
    result = await service.book_logistics(
        current_user=current_user, lot_id=lot_id, slot_time=body.slot_time, idempotency_key=idempotency_key
    )
    return LogisticsBookingResponse(**result)


@router.get("/lot/{lot_id}")
async def get_booking_for_lot_route(
    lot_id: str,
    current_user: dict = Depends(require_role("RECYCLER")),
):
    booking = await service.get_booking_for_lot(current_user=current_user, lot_id=lot_id)
    return {"success": True, "booking": booking}


@router.post("/{booking_id}/confirm-collection", response_model=LogisticsBookingResponse)
async def confirm_collection_route(
    booking_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RECYCLER")),
):
    result = await service.confirm_collection(
        current_user=current_user, booking_id=booking_id, idempotency_key=idempotency_key
    )
    return LogisticsBookingResponse(**result)

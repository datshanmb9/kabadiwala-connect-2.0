from fastapi import APIRouter, Depends, Header, Query

from app.core.rbac import require_role
from app.modules.payments import service
from app.modules.payments.schemas import PaymentResponse

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post("/{lot_id}/initiate", response_model=PaymentResponse)
async def initiate_payment_route(
    lot_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RECYCLER")),
):
    result = await service.initiate_payment(current_user=current_user, lot_id=lot_id, idempotency_key=idempotency_key)
    return PaymentResponse(**result)


@router.get("/lot/{lot_id}")
async def list_payments_for_lot_route(
    lot_id: str,
    current_user: dict = Depends(require_role("RECYCLER", "GOVERNMENT_ADMIN")),
):
    docs = await service.list_payments_for_lot(current_user=current_user, lot_id=lot_id)
    return {"success": True, "payments": docs}


admin_router = APIRouter(tags=["payments-admin"])


@admin_router.get("/api/v1/admin/payments")
async def admin_list_payments_route(
    status: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    docs = await service.list_all_for_admin(status=status)
    return {"success": True, "payments": docs}

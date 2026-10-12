from fastapi import APIRouter, Depends, Header, Query

from app.core.rbac import require_role
from app.modules.bids import service
from app.modules.bids.schemas import BidPlaceRequest, BidResponse

router = APIRouter(prefix="/api/v1/bids", tags=["bids"])

# Unprefixed sibling router (Phase 7), same reason as ewaste/lots admin_router.
admin_router = APIRouter(tags=["bids-admin"])


@admin_router.get("/api/v1/admin/bids")
async def admin_list_bids_route(
    status: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    docs = await service.list_all_for_admin(status=status)
    return {"success": True, "bids": docs}


@router.post("", response_model=BidResponse)
async def place_bid_route(
    body: BidPlaceRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RECYCLER")),
):
    result = await service.place_bid(
        current_user=current_user,
        lot_id=body.lot_id,
        amount_str=body.amount,
        idempotency_key=idempotency_key,
    )
    return BidResponse(**result)


@router.get("/mine")
async def list_my_bids_route(current_user: dict = Depends(require_role("RECYCLER"))):
    docs = await service.list_my_bids(current_user)
    return {"success": True, "bids": docs}


@router.post("/{bid_id}/cancel", response_model=BidResponse)
async def cancel_bid_route(
    bid_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RECYCLER")),
):
    result = await service.cancel_bid(current_user=current_user, bid_id=bid_id, idempotency_key=idempotency_key)
    return BidResponse(**result)


@router.post("/{bid_id}/accept", response_model=BidResponse)
async def accept_bid_route(
    bid_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RRR_CENTER", "COLLECTOR")),
):
    result = await service.accept_bid(current_user=current_user, bid_id=bid_id, idempotency_key=idempotency_key)
    return BidResponse(**result)


@router.post("/{bid_id}/cancel-acceptance", response_model=BidResponse)
async def cancel_acceptance_route(
    bid_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RRR_CENTER", "COLLECTOR")),
):
    result = await service.cancel_acceptance(
        current_user=current_user, bid_id=bid_id, idempotency_key=idempotency_key
    )
    return BidResponse(**result)

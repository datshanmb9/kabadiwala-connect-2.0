from fastapi import APIRouter, Depends, Header, Query

from app.core.rbac import require_role
from app.modules.bids import service as bids_service
from app.modules.lots import service
from app.modules.lots.schemas import LotCreateRequest, LotResponse

router = APIRouter(prefix="/api/v1/lots", tags=["lots"])

# Unprefixed sibling router (Phase 7), same reason as ewaste/router.py's
# admin_router: the /api/v1/lots prefix above would otherwise double up
# with the /api/v1/admin/... convention.
admin_router = APIRouter(tags=["lots-admin"])


@admin_router.get("/api/v1/admin/lots")
async def admin_list_lots_route(
    status: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    docs = await service.list_all_for_admin(status=status)
    return {"success": True, "lots": docs}


@admin_router.post("/api/v1/admin/lots/{lot_id}/complete", response_model=LotResponse)
async def admin_complete_lot_route(
    lot_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    """Phase 10: the final SOLD -> COMPLETED step, admin/system-controlled
    only — no other role has this permission anywhere."""
    result = await service.complete_lot(actor=current_user, lot_id=lot_id, idempotency_key=idempotency_key)
    return LotResponse(**result)


@router.post("", response_model=LotResponse)
async def create_lot_route(
    body: LotCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RRR_CENTER")),
):
    result = await service.create_lot(
        current_user=current_user,
        category=body.category,
        submission_ids=body.submission_ids,
        idempotency_key=idempotency_key,
    )
    return LotResponse(**result)


@router.get("")
async def list_lots_route(current_user: dict = Depends(require_role("RRR_CENTER"))):
    docs = await service.list_my_lots(current_user)
    return {"success": True, "lots": docs}


@router.get("/listed")
async def list_listed_for_bidding_route(current_user: dict = Depends(require_role("RECYCLER"))):
    """Registered before /lots/{lot_id} deliberately — FastAPI matches
    routes in registration order, and this static path must win over the
    path-parameter route, same reason as every other static-before-dynamic
    route in this codebase (e.g. /submissions/pending)."""
    docs = await service.list_listed_for_bidding(current_user)
    return {"success": True, "lots": docs}


@router.get("/{lot_id}/bids")
async def list_bids_for_lot_route(
    lot_id: str,
    current_user: dict = Depends(require_role("RRR_CENTER", "COLLECTOR")),
):
    docs = await bids_service.list_bids_for_lot(current_user=current_user, lot_id=lot_id)
    return {"success": True, "bids": docs}


@router.get("/{lot_id}", response_model=LotResponse)
async def get_lot_route(
    lot_id: str,
    current_user: dict = Depends(require_role("RRR_CENTER", "GOVERNMENT_ADMIN", "RECYCLER", "COLLECTOR")),
):
    doc = await service.get_lot(lot_id, current_user)
    return LotResponse(
        lot_id=doc["lot_id"],
        rrr_id=doc.get("rrr_id"),
        owner_collector_id=doc.get("owner_collector_id"),
        ward_id=doc["ward_id"],
        category=doc["category"],
        item_ids=doc["item_ids"],
        status=doc["status"],
        bid_deadline=doc.get("bid_deadline"),
        total_weight_kg=doc.get("total_weight_kg"),
        item_details=doc.get("item_details", []),
        price_estimate=doc.get("price_estimate"),
    )


@router.post("/{lot_id}/publish", response_model=LotResponse)
async def publish_lot_route(
    lot_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RRR_CENTER")),
):
    result = await service.publish_lot(
        current_user=current_user,
        lot_id=lot_id,
        idempotency_key=idempotency_key,
    )
    return LotResponse(**result)

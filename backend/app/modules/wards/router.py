from fastapi import APIRouter, Depends

from app.core.rbac import require_role
from app.modules.wards import service
from app.modules.wards.schemas import WardCreateRequest, WardResponse

router = APIRouter(prefix="/api/v1/wards", tags=["wards"])


@router.post("", response_model=WardResponse)
async def create_ward_route(
    body: WardCreateRequest,
    current_user: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    doc = await service.create_ward(ward_id=body.ward_id, name=body.name, actor=current_user)
    return WardResponse(ward_id=doc["ward_id"], name=doc["name"])


@router.get("")
async def list_wards_route():
    """Deliberately public (Phase 3 addition): ward_id/name are non-sensitive
    reference data, and the Home User registration screen needs to offer a
    ward picker before the user has an account — there is no token to send
    at that point. Only this read is public; creation stays admin-only,
    unchanged above."""
    wards = await service.list_wards()
    return {"success": True, "wards": wards}

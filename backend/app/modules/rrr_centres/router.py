from fastapi import APIRouter, Depends, Query

from app.core.errors import not_found
from app.core.rbac import require_role
from app.db.repositories import users_repo
from app.modules.rrr_centres import service
from app.modules.rrr_centres.schemas import RrrCentreProfileResponse, RrrCentreRegisterRequest

router = APIRouter(tags=["rrr-centres"])


def _to_response(profile: dict, username: str) -> RrrCentreProfileResponse:
    return RrrCentreProfileResponse(
        user_id=profile["user_id"],
        username=username,
        rrr_id=profile["rrr_id"],
        tender_id=profile["tender_id"],
        ward_id=profile["ward_id"],
        licence_doc_ref=profile.get("licence_doc_ref"),
        status=profile["status"],
    )


@router.post("/api/v1/rrr-centres/register", response_model=RrrCentreProfileResponse)
async def register_route(body: RrrCentreRegisterRequest):
    result = await service.register(
        username=body.username,
        password=body.password,
        rrr_id=body.rrr_id,
        tender_id=body.tender_id,
        ward_id=body.ward_id,
        licence_doc_ref=body.licence_doc_ref,
    )
    return _to_response(result["profile"], result["user"]["username"])


@router.get("/api/v1/rrr-centres/me", response_model=RrrCentreProfileResponse)
async def me_route(current_user: dict = Depends(require_role("RRR_CENTER"))):
    profile = await service.get_profile(current_user["user_id"])
    if profile is None:
        raise not_found("RRR_CENTRE_PROFILE_NOT_FOUND", "No RRR centre profile found for this account.")
    return _to_response(profile, current_user["username"])


@router.get("/api/v1/admin/rrr-centres")
async def list_rrr_centres_route(
    status: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    profiles = await service.list_all_for_admin(status=status)
    return {"success": True, "rrr_centres": profiles}


@router.post("/api/v1/admin/rrr-centres/{user_id}/approve", response_model=RrrCentreProfileResponse)
async def approve_route(user_id: str, current_user: dict = Depends(require_role("GOVERNMENT_ADMIN"))):
    profile = await service.approve(user_id=user_id, actor=current_user)
    user = await users_repo.find_by_id(user_id)
    return _to_response(profile, user["username"] if user else "")


@router.post("/api/v1/admin/rrr-centres/{user_id}/reject", response_model=RrrCentreProfileResponse)
async def reject_route(user_id: str, current_user: dict = Depends(require_role("GOVERNMENT_ADMIN"))):
    profile = await service.reject(user_id=user_id, actor=current_user)
    user = await users_repo.find_by_id(user_id)
    return _to_response(profile, user["username"] if user else "")

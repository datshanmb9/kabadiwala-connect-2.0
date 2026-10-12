from fastapi import APIRouter, Depends, Query

from app.core.errors import not_found
from app.core.rbac import require_role
from app.db.repositories import users_repo
from app.modules.recyclers import service
from app.modules.recyclers.schemas import RecyclerProfileResponse, RecyclerRegisterRequest

router = APIRouter(tags=["recyclers"])


def _to_response(profile: dict, username: str) -> RecyclerProfileResponse:
    return RecyclerProfileResponse(
        user_id=profile["user_id"],
        username=username,
        license_id=profile["license_id"],
        company_name=profile["company_name"],
        status=profile["status"],
    )


@router.post("/api/v1/recyclers/register", response_model=RecyclerProfileResponse)
async def register_route(body: RecyclerRegisterRequest):
    result = await service.register(username=body.username, password=body.password, company_name=body.company_name)
    return _to_response(result["profile"], result["user"]["username"])


@router.get("/api/v1/recyclers/me", response_model=RecyclerProfileResponse)
async def me_route(current_user: dict = Depends(require_role("RECYCLER"))):
    profile = await service.get_profile(current_user["user_id"])
    if profile is None:
        raise not_found("RECYCLER_PROFILE_NOT_FOUND", "No recycler profile found for this account.")
    return _to_response(profile, current_user["username"])


@router.get("/api/v1/admin/recyclers")
async def list_recyclers_route(
    status: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    profiles = await service.list_all_for_admin(status=status)
    return {"success": True, "recyclers": profiles}


@router.post("/api/v1/admin/recyclers/{user_id}/approve", response_model=RecyclerProfileResponse)
async def approve_route(user_id: str, current_user: dict = Depends(require_role("GOVERNMENT_ADMIN"))):
    profile = await service.approve(user_id=user_id, actor=current_user)
    user = await users_repo.find_by_id(user_id)
    return _to_response(profile, user["username"] if user else "")


@router.post("/api/v1/admin/recyclers/{user_id}/reject", response_model=RecyclerProfileResponse)
async def reject_route(user_id: str, current_user: dict = Depends(require_role("GOVERNMENT_ADMIN"))):
    profile = await service.reject(user_id=user_id, actor=current_user)
    user = await users_repo.find_by_id(user_id)
    return _to_response(profile, user["username"] if user else "")

from fastapi import APIRouter, Depends

from app.core.errors import not_found
from app.core.rbac import require_role
from app.modules.home_users import service
from app.modules.home_users.schemas import (
    HomeUserPreferencesRequest,
    HomeUserProfileResponse,
    HomeUserProfileUpdateRequest,
    HomeUserRegisterRequest,
)

router = APIRouter(prefix="/api/v1/home-users", tags=["home-users"])


@router.post("/register", response_model=HomeUserProfileResponse)
async def register_route(body: HomeUserRegisterRequest):
    result = await service.register(
        username=body.username,
        password=body.password,
        full_name=body.full_name,
        address=body.address,
        ward_id=body.ward_id,
        household_lat=body.household_lat,
        household_lng=body.household_lng,
        upi_id=body.upi_id,
    )
    user, profile = result["user"], result["profile"]
    return HomeUserProfileResponse(
        user_id=user["user_id"],
        username=user["username"],
        full_name=profile["full_name"],
        address=profile["address"],
        ward_id=profile["ward_id"],
        household_lat=profile["household_lat"],
        household_lng=profile["household_lng"],
        upi_id=profile["upi_id"],
    )


@router.get("/me", response_model=HomeUserProfileResponse)
async def me_route(current_user: dict = Depends(require_role("HOME_USER"))):
    profile = await service.get_profile(current_user["user_id"])
    if profile is None:
        raise not_found("HOME_USER_PROFILE_NOT_FOUND", "No home-user profile found for this account.")
    return HomeUserProfileResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        full_name=profile["full_name"],
        address=profile["address"],
        ward_id=profile["ward_id"],
        household_lat=profile["household_lat"],
        household_lng=profile["household_lng"],
        upi_id=profile["upi_id"],
        account_status=current_user["status"],
        created_at=profile.get("created_at"),
        preferences=profile.get("preferences", {}),
    )


@router.patch("/me", response_model=HomeUserProfileResponse)
async def update_me_route(
    body: HomeUserProfileUpdateRequest,
    current_user: dict = Depends(require_role("HOME_USER")),
):
    profile = await service.update_profile(
        user_id=current_user["user_id"],
        full_name=body.full_name,
        address=body.address,
    )
    return HomeUserProfileResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        full_name=profile["full_name"],
        address=profile["address"],
        ward_id=profile["ward_id"],
        household_lat=profile["household_lat"],
        household_lng=profile["household_lng"],
        upi_id=profile.get("upi_id"),
        account_status=current_user["status"],
        created_at=profile.get("created_at"),
        preferences=profile.get("preferences", {}),
    )


@router.patch("/me/preferences", response_model=HomeUserProfileResponse)
async def update_preferences_route(
    body: HomeUserPreferencesRequest,
    current_user: dict = Depends(require_role("HOME_USER")),
):
    profile = await service.update_preferences(
        user_id=current_user["user_id"],
        language=body.language,
        collection_updates=body.collection_updates,
        status_updates=body.status_updates,
        account_updates=body.account_updates,
    )
    return HomeUserProfileResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        full_name=profile["full_name"],
        address=profile["address"],
        ward_id=profile["ward_id"],
        household_lat=profile["household_lat"],
        household_lng=profile["household_lng"],
        upi_id=profile.get("upi_id"),
        account_status=current_user["status"],
        created_at=profile.get("created_at"),
        preferences=profile.get("preferences", {}),
    )


@router.post("/me/deactivate")
async def deactivate_me_route(current_user: dict = Depends(require_role("HOME_USER"))):
    await service.deactivate_account(current_user)
    return {"success": True}

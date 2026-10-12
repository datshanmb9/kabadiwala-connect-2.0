from fastapi import APIRouter, Depends

from app.core.rbac import get_current_user
from app.modules.auth import service
from app.modules.auth.schemas import (
    AccessTokenResponse,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login_route(body: LoginRequest):
    result = await service.login(body.username, body.password)
    return TokenResponse(**result)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_route(body: RefreshRequest):
    result = await service.refresh(body.refresh_token)
    return AccessTokenResponse(**result)


@router.post("/logout")
async def logout_route(current_user: dict = Depends(get_current_user)):
    await service.logout(current_user)
    return {"success": True}


@router.get("/me", response_model=MeResponse)
async def me_route(current_user: dict = Depends(get_current_user)):
    return MeResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        role=current_user["role"],
    )

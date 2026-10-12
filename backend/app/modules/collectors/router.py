from fastapi import APIRouter, Depends

from app.core.errors import not_found
from app.core.rbac import require_role
from app.modules.collectors import service
from app.modules.collectors.schemas import (
    CollectorAssignmentUpdateRequest,
    CollectorCreateRequest,
    CollectorProfileResponse,
    CollectorStatusUpdateRequest,
)

router = APIRouter(tags=["collectors"])


@router.post("/api/v1/admin/collectors", response_model=CollectorProfileResponse)
async def create_collector_route(
    body: CollectorCreateRequest,
    current_user: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    result = await service.create_collector(
        employee_id=body.employee_id,
        password=body.password,
        ward_id=body.ward_id,
        rrr_id=body.rrr_id,
        assigned_area_radius_m=body.assigned_area_radius_m,
        actor=current_user,
    )
    profile = result["profile"]
    return CollectorProfileResponse(
        user_id=profile["user_id"],
        employee_id=profile["employee_id"],
        ward_id=profile["ward_id"],
        rrr_id=profile["rrr_id"],
        assigned_area_radius_m=profile["assigned_area_radius_m"],
    )


@router.get("/api/v1/collectors/me", response_model=CollectorProfileResponse)
async def me_route(current_user: dict = Depends(require_role("COLLECTOR"))):
    """Read-only, by construction: this router defines no PATCH/PUT route
    for a collector's own profile. Only the admin-only create route above
    (and a future admin-only PATCH, when Phase 2+ needs one) can write to
    this collection."""
    profile = await service.get_profile(current_user["user_id"])
    if profile is None:
        raise not_found("COLLECTOR_PROFILE_NOT_FOUND", "No collector profile found for this account.")
    return CollectorProfileResponse(
        user_id=profile["user_id"],
        employee_id=profile["employee_id"],
        ward_id=profile["ward_id"],
        rrr_id=profile["rrr_id"],
        assigned_area_radius_m=profile["assigned_area_radius_m"],
    )


@router.get("/api/v1/admin/collectors")
async def list_collectors_route(current_user: dict = Depends(require_role("GOVERNMENT_ADMIN"))):
    profiles = await service.list_all_for_admin()
    return {"success": True, "collectors": profiles}


@router.patch("/api/v1/admin/collectors/{user_id}")
async def update_collector_assignment_route(
    user_id: str,
    body: CollectorAssignmentUpdateRequest,
    current_user: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    profile = await service.update_assignment(
        user_id=user_id,
        ward_id=body.ward_id,
        rrr_id=body.rrr_id,
        assigned_area_radius_m=body.assigned_area_radius_m,
        actor=current_user,
    )
    return {"success": True, "collector": profile}


@router.post("/api/v1/admin/collectors/{user_id}/status")
async def update_collector_status_route(
    user_id: str,
    body: CollectorStatusUpdateRequest,
    current_user: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    profile = await service.set_status(user_id=user_id, new_status=body.status, actor=current_user)
    return {"success": True, "collector": profile}

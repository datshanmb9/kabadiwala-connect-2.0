from fastapi import APIRouter, Depends

from app.core.rbac import require_role
from app.modules.admin import service

router = APIRouter(tags=["admin"])


@router.get("/api/v1/admin/dashboard/summary")
async def dashboard_summary_route(_admin: dict = Depends(require_role("GOVERNMENT_ADMIN"))):
    summary = await service.get_dashboard_summary()
    return {"success": True, "summary": summary}

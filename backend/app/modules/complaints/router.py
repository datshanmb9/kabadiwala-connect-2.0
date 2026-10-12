from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_role
from app.modules.complaints import service
from app.modules.complaints.schemas import ComplaintCreateRequest, ComplaintResponse, ComplaintReviewRequest

router = APIRouter(tags=["complaints"])


@router.post("/api/v1/complaints", response_model=ComplaintResponse)
async def file_complaint_route(
    body: ComplaintCreateRequest,
    current_user: dict = Depends(require_role()),
):
    """Any authenticated role may file a complaint (architecture Section 7:
    HOME_USER/COLLECTOR/RRR_CENTER/RECYCLER all have "File complaint" ✅).
    reporter_id/reporter_role always come from the verified token, never
    the request body."""
    result = await service.file_complaint(
        current_user=current_user,
        target_type=body.target_type,
        target_id=body.target_id,
        category=body.category,
        description=body.description,
    )
    return ComplaintResponse(**result)


@router.get("/api/v1/complaints/mine")
async def list_my_complaints_route(current_user: dict = Depends(require_role())):
    docs = await service.list_my_complaints(current_user)
    return {"success": True, "complaints": docs}


@router.get("/api/v1/admin/complaints")
async def list_complaints_route(
    status: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    docs = await service.list_all_for_admin(status=status)
    return {"success": True, "complaints": docs}


@router.post("/api/v1/admin/complaints/{complaint_id}/review", response_model=ComplaintResponse)
async def review_complaint_route(
    complaint_id: str,
    body: ComplaintReviewRequest,
    current_user: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    result = await service.review_complaint(
        complaint_id=complaint_id,
        new_status=body.new_status,
        resolution_notes=body.resolution_notes,
        actor=current_user,
    )
    return ComplaintResponse(**result)

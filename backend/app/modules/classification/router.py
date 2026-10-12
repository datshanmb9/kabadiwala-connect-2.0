from fastapi import APIRouter, Depends, Header

from app.core.rbac import require_role
from app.modules.classification import service
from app.modules.classification.schemas import (
    AiClassifyResponse,
    AiPhotoClassifyRequest,
    AiPhotoClassifyResponse,
)

router = APIRouter(tags=["classification"])


@router.post("/api/v1/ai/classify-photo", response_model=AiPhotoClassifyResponse)
async def ai_classify_photo_route(
    body: AiPhotoClassifyRequest,
    _current_user: dict = Depends(require_role("HOME_USER", "COLLECTOR")),
):
    if not body.photo_file_id:
        from app.core.errors import bad_request

        raise bad_request("INVALID_PHOTO_REFERENCE", "A photo_file_id is required.")
    result = await service.classify_photo(body.photo_file_id)
    return AiPhotoClassifyResponse(**result)


@router.post("/api/v1/ai/classify/{submission_id}", response_model=AiClassifyResponse)
async def ai_classify_route(
    submission_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RRR_CENTER")),
):
    """RRR-only, own ward only (checked in the service layer — role alone
    is never sufficient). GOVERNMENT_ADMIN gets read-only oversight via
    the existing Phase 7 GET /api/v1/admin/submissions, which already
    surfaces every status including NEEDS_REVIEW — no separate admin
    route needed here."""
    result = await service.classify_with_ai(
        current_user=current_user, submission_id=submission_id, idempotency_key=idempotency_key
    )
    return AiClassifyResponse(**result)

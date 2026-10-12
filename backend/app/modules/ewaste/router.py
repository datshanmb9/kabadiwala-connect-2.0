from fastapi import APIRouter, Depends, File, Header, Query, UploadFile

from app.core.rbac import require_role
from app.modules.ewaste import service
from app.modules.ewaste.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    CollectorActionResponse,
    HandoverRequest,
    HandoverResponse,
    PhotoUploadResponse,
    ReceiveResponse,
    SubmissionCreateRequest,
    SubmissionDetailResponse,
    SubmissionResponse,
)
from app.core.media_storage import store_image

router = APIRouter(prefix="/api/v1/ewaste", tags=["ewaste"])

# Separate, unprefixed router (Phase 7): admin oversight routes live at
# /api/v1/admin/... — same path convention rrr_centres/recyclers/collectors
# already use for their own admin sub-routes — but this module's main
# `router` above carries a hardcoded "/api/v1/ewaste" prefix, so these
# can't be added to it directly without becoming
# /api/v1/ewaste/api/v1/admin/... A second router instance with no prefix
# is the clean fix; both are registered in main.py.
admin_router = APIRouter(tags=["ewaste-admin"])


@router.post("/photos", response_model=PhotoUploadResponse)
async def upload_photo_route(
    file: UploadFile = File(...),
    _current_user: dict = Depends(require_role("HOME_USER", "COLLECTOR")),
):
    try:
        photo_file_id = await store_image(file)
    except ValueError as exc:
        from app.core.errors import bad_request

        raise bad_request("INVALID_PHOTO", str(exc)) from exc
    return PhotoUploadResponse(photo_file_id=photo_file_id)


@admin_router.get("/api/v1/admin/submissions")
async def admin_list_submissions_route(
    status: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    """Read-only, system-wide (not ward-scoped) — the oversight view the
    architecture's admin permission line implies. No new state-transition
    endpoint is added here; this only reads."""
    docs = await service.list_all_submissions_for_admin(status=status)
    return {"success": True, "submissions": docs}


@admin_router.get("/api/v1/admin/handovers")
async def admin_list_handovers_route(
    verification_result: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    """Geo-verification detail (distance_m, verification_result) that
    never gets copied onto the submission document — this is the only
    admin read path that reaches it."""
    docs = await service.list_all_handovers_for_admin(verification_result=verification_result)
    return {"success": True, "handovers": docs}


@router.post("/submissions", response_model=SubmissionResponse)
async def create_submission_route(
    body: SubmissionCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("HOME_USER")),
):
    result = await service.create_submission(
        current_user=current_user,
        ward_id=body.ward_id,
        photo_file_id=body.photo_file_id,
        category=body.category,
        condition=body.condition,
        approximate_weight_kg=body.approximate_weight_kg,
        price_estimate=body.price_estimate.model_dump() if body.price_estimate else None,
        home_lat=body.home_lat,
        home_lng=body.home_lng,
        home_ts=body.home_ts,
        idempotency_key=idempotency_key,
    )
    return SubmissionResponse(**result)


@router.get("/submissions")
async def list_submissions_route(current_user: dict = Depends(require_role("HOME_USER"))):
    docs = await service.list_my_submissions(current_user["user_id"])
    return {"success": True, "submissions": docs}


@router.get("/submissions/pending")
async def list_pending_submissions_route(current_user: dict = Depends(require_role("COLLECTOR"))):
    """Registered before /submissions/{submission_id} deliberately — FastAPI
    matches routes in registration order, and this static path must win
    over the path-parameter route, or a request here would be misrouted
    as a lookup for a submission literally named 'pending'."""
    docs = await service.list_pending_for_collector(current_user)
    return {"success": True, "submissions": docs}


@router.get("/submissions/assigned")
async def list_assigned_submissions_route(current_user: dict = Depends(require_role("COLLECTOR"))):
    docs = await service.list_assigned_for_collector(current_user)
    return {"success": True, "submissions": docs}


@router.get("/submissions/handed-over")
async def list_handed_over_submissions_route(current_user: dict = Depends(require_role("COLLECTOR"))):
    """"Accepted Collections": submissions this collector has already
    handed over (status COLLECTED or later) — registered before
    /submissions/{submission_id}, same static-before-dynamic reason as
    /submissions/pending above."""
    docs = await service.list_handed_over_for_collector(current_user)
    return {"success": True, "submissions": docs}


@router.get("/submissions/awaiting-receipt")
async def list_awaiting_receipt_route(current_user: dict = Depends(require_role("RRR_CENTER"))):
    """Registered before /submissions/{submission_id}, same reason as
    /submissions/pending above."""
    docs = await service.list_awaiting_receipt_for_rrr(current_user)
    return {"success": True, "submissions": docs}


@router.get("/submissions/awaiting-classification")
async def list_awaiting_classification_route(current_user: dict = Depends(require_role("RRR_CENTER"))):
    docs = await service.list_awaiting_classification_for_rrr(current_user)
    return {"success": True, "submissions": docs}


@router.get("/submissions/classified")
async def list_classified_route(current_user: dict = Depends(require_role("RRR_CENTER"))):
    docs = await service.list_classified_for_rrr(current_user)
    return {"success": True, "submissions": docs}


@router.get("/submissions/{submission_id}", response_model=SubmissionDetailResponse)
async def get_submission_route(
    submission_id: str,
    current_user: dict = Depends(require_role("HOME_USER", "COLLECTOR", "GOVERNMENT_ADMIN")),
):
    doc = await service.get_submission(submission_id, current_user)
    return SubmissionDetailResponse(**doc)


@router.post("/submissions/{submission_id}/accept", response_model=CollectorActionResponse)
async def accept_submission_route(
    submission_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("COLLECTOR")),
):
    result = await service.accept_submission(
        current_user=current_user, submission_id=submission_id, idempotency_key=idempotency_key
    )
    return CollectorActionResponse(**result)


@router.post("/submissions/{submission_id}/handover", response_model=HandoverResponse)
async def handover_route(
    submission_id: str,
    body: HandoverRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("COLLECTOR")),
):
    result = await service.handover(
        current_user=current_user,
        submission_id=submission_id,
        photo_file_id=body.photo_file_id,
        collector_lat=body.collector_lat,
        collector_lng=body.collector_lng,
        collector_ts=body.collector_ts,
        actual_weight_kg=body.actual_weight_kg,
        idempotency_key=idempotency_key,
    )
    # A verified handover immediately continues on to a published, biddable
    # lot — see auto_progress_to_listed_lot's docstring. A FLAGGED handover
    # (result["status"] != "COLLECTED") returns lot_id/lot_status as None.
    lot_info = await service.auto_progress_to_listed_lot(submission_id, current_user)
    return HandoverResponse(**result, **lot_info)


@router.post("/submissions/{submission_id}/receive", response_model=ReceiveResponse)
async def receive_route(
    submission_id: str,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RRR_CENTER")),
):
    result = await service.receive(
        current_user=current_user,
        submission_id=submission_id,
        idempotency_key=idempotency_key,
    )
    return ReceiveResponse(**result)


@router.post("/submissions/{submission_id}/classify", response_model=ClassifyResponse)
async def classify_route(
    submission_id: str,
    body: ClassifyRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_role("RRR_CENTER")),
):
    result = await service.classify(
        current_user=current_user,
        submission_id=submission_id,
        category=body.category,
        idempotency_key=idempotency_key,
    )
    return ClassifyResponse(**result)

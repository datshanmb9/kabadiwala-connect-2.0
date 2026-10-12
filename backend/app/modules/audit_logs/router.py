from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_role
from app.db.repositories import audit_repo

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("")
async def list_audit_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    actor_role: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    _admin: dict = Depends(require_role("GOVERNMENT_ADMIN")),
):
    """Read-only. There is no POST/PATCH/DELETE route anywhere for this
    collection, for any role including admin — audit_logs is append-only
    at the API surface, not just by convention. Phase 7 adds optional
    actor_role/entity_type filters (additive — omitting both reproduces
    the exact original unfiltered behavior); actor_role=GOVERNMENT_ADMIN
    doubles as the "Government Actions" admin-web view."""
    logs = await audit_repo.list_logs(skip=skip, limit=limit, actor_role=actor_role, entity_type=entity_type)
    for log in logs:
        log.pop("_id", None)
    return {"success": True, "logs": logs}

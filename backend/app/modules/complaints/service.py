"""
Complaint filing (any authenticated actor, self-only reporter) + admin
review (architecture Section 13). No idempotency key on file/review —
matching the established precedent that admin-facing state-changing
endpoints in this codebase (ward create, collector create, RRR/recycler
approve/reject) don't use one either; only the financial/marketplace
endpoints (submissions, handovers, lots, bids) do.
"""
from datetime import datetime, timezone
from uuid import uuid4

from app.core import audit
from app.core.errors import bad_request, not_found
from app.db.repositories import complaints_repo
from app.state_machines import complaint_states


def _strip(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def file_complaint(
    *, current_user: dict, target_type: str, target_id: str, category: str, description: str
) -> dict:
    complaint_id = str(uuid4())
    doc = {
        "complaint_id": complaint_id,
        "reporter_id": current_user["user_id"],
        "reporter_role": current_user["role"],
        "target_type": target_type,
        "target_id": target_id,
        "category": category,
        "description": description,
        "status": "OPEN",
        "resolution_notes": None,
        "created_at": datetime.now(timezone.utc),
    }
    await complaints_repo.insert_complaint(doc)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="COMPLAINT_FILED",
        entity_type="complaint",
        entity_id=complaint_id,
        details={"target_type": target_type, "target_id": target_id, "category": category},
    )

    return _strip(doc)


async def list_my_complaints(current_user: dict) -> list[dict]:
    docs = await complaints_repo.list_by_reporter(current_user["user_id"])
    return [_strip(d) for d in docs]


async def list_all_for_admin(status: str | None = None) -> list[dict]:
    docs = await complaints_repo.list_all(status=status)
    return [_strip(d) for d in docs]


async def review_complaint(*, complaint_id: str, new_status: str, resolution_notes: str | None, actor: dict) -> dict:
    complaint = await complaints_repo.find_by_complaint_id(complaint_id)
    if complaint is None:
        raise not_found("COMPLAINT_NOT_FOUND", "No complaint exists with this complaint_id.")

    try:
        resolved_status = complaint_states.transition(complaint["status"], new_status)
    except complaint_states.InvalidComplaintStateTransitionError as exc:
        raise bad_request(
            "INVALID_COMPLAINT_TRANSITION",
            f"Cannot move a complaint from {exc.from_state} to {exc.to_state}.",
        ) from exc

    await complaints_repo.update_status(complaint_id, resolved_status, resolution_notes=resolution_notes)

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="COMPLAINT_REVIEWED",
        entity_type="complaint",
        entity_id=complaint_id,
        details={"from_status": complaint["status"], "to_status": resolved_status},
    )

    complaint["status"] = resolved_status
    complaint["resolution_notes"] = resolution_notes
    return _strip(complaint)

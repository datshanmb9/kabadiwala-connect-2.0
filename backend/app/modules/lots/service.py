"""
Lot creation + publish — the RRR's last two Phase 5 actions, taking
CLASSIFIED items through to LISTED_FOR_BIDDING. Drives TWO state
machines in parallel per document written: the lot's own status
(app/state_machines/lot_states.py) and each contained item's status
(app/state_machines/ewaste_states.py, unchanged since Phase 2) — this
mirrors the architecture's explicit separation of the lot lifecycle
(Section 6.3) from the item lifecycle (Section 6.1). Actual bidding
(anything past LISTED_FOR_BIDDING) is Phase 6 scope; this module only
gets a lot to the point recyclers could see it.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core import audit, idempotency
from app.core.config import settings
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.db.repositories import lots_repo, submissions_repo
from app.modules.pricing import service as pricing_service
from app.modules.recyclers import service as recyclers_service
from app.modules.rrr_centres import service as rrr_centres_service
from app.state_machines import lot_states
from app.state_machines.ewaste_states import transition

LOT_CREATE_IDEMPOTENCY_SCOPE = "lot_create"
LOT_PUBLISH_IDEMPOTENCY_SCOPE = "lot_publish"
LOT_COMPLETE_IDEMPOTENCY_SCOPE = "lot_complete"


async def create_lot(
    *, current_user: dict, category: str, submission_ids: list[str], idempotency_key: str
) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, LOT_CREATE_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    if not submission_ids:
        raise bad_request("LOT_REQUIRES_AT_LEAST_ONE_ITEM", "A lot must contain at least one item.")

    rrr_profile = await rrr_centres_service.require_approved_rrr(current_user)

    submissions = []
    for submission_id in submission_ids:
        submission = await submissions_repo.find_by_submission_id(submission_id)
        if submission is None:
            raise not_found("SUBMISSION_NOT_FOUND", f"No submission exists with id {submission_id}.")
        if submission["ward_id"] != rrr_profile["ward_id"]:
            raise forbidden("RRR_OUTSIDE_ASSIGNED_WARD", f"Submission {submission_id} is outside your assigned ward.")
        if submission["status"] != "CLASSIFIED":
            raise bad_request(
                "SUBMISSION_NOT_CLASSIFIED",
                f"Submission {submission_id} is in status {submission['status']}, not eligible for a lot.",
            )
        if submission.get("category") != category:
            raise bad_request(
                "SUBMISSION_CATEGORY_MISMATCH",
                f"Submission {submission_id} has category {submission.get('category')!r}, not {category!r}.",
            )
        submissions.append(submission)

    now = datetime.now(timezone.utc)
    lot_id = str(uuid4())
    item_details = [
        {
            "submission_id": submission["submission_id"],
            "home_user_id": submission["home_user_id"],
            "actual_weight_kg": submission.get("actual_weight_kg"),
            "collection_photo_file_id": submission.get("collection_photo_file_id"),
            "collector_id": submission.get("assigned_collector_id"),
            "collector_lat": submission.get("collector_lat"),
            "collector_lng": submission.get("collector_lng"),
            "collection_ts": submission.get("collection_ts"),
        }
        for submission in submissions
    ]
    measured_weights = [item["actual_weight_kg"] for item in item_details if item["actual_weight_kg"] is not None]
    lot_doc = {
        "lot_id": lot_id,
        "rrr_id": rrr_profile["rrr_id"],
        "ward_id": rrr_profile["ward_id"],
        "category": category,
        "item_ids": submission_ids,
        "status": "DRAFT",  # entry state — no transition() call, same as an item's implicit "CREATED" start
        "bid_deadline": None,
        "total_weight_kg": sum(measured_weights) if measured_weights else None,
        "item_details": item_details,
        "created_at": now,
        "updated_at": now,
    }
    await lots_repo.insert_lot(lot_doc)

    new_item_status = transition("CLASSIFIED", "LOT_CREATED")
    for submission_id in submission_ids:
        await submissions_repo.update_status(submission_id, new_item_status)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="LOT_CREATED",
        entity_type="lot",
        entity_id=lot_id,
        details={"category": category, "item_ids": submission_ids, "item_count": len(submission_ids)},
    )

    response = {
        "lot_id": lot_id,
        "rrr_id": lot_doc["rrr_id"],
        "ward_id": lot_doc["ward_id"],
        "category": category,
        "item_ids": submission_ids,
        "status": "DRAFT",
        "bid_deadline": None,
        "total_weight_kg": lot_doc["total_weight_kg"],
        "item_details": item_details,
    }
    await idempotency.store_response(current_user["user_id"], idempotency_key, LOT_CREATE_IDEMPOTENCY_SCOPE, response)
    return response


async def publish_lot(*, current_user: dict, lot_id: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, LOT_PUBLISH_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    rrr_profile = await rrr_centres_service.require_approved_rrr(current_user)

    lot = await lots_repo.find_by_lot_id(lot_id)
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists with this lot_id.")
    if lot["rrr_id"] != rrr_profile["rrr_id"]:
        raise forbidden("NOT_LOT_OWNER", "You do not have access to this lot.")
    if lot["status"] != "DRAFT":
        raise bad_request("LOT_NOT_DRAFT", f"Lot is in status {lot['status']}, not eligible for publishing.")

    new_lot_status = lot_states.transition("DRAFT", "LISTED_FOR_BIDDING")
    bid_deadline = datetime.now(timezone.utc) + timedelta(days=settings.lot_bid_window_days)
    await lots_repo.update_status_and_deadline(lot_id, new_lot_status, bid_deadline)

    new_item_status = transition("LOT_CREATED", "LISTED_FOR_BIDDING")
    for submission_id in lot["item_ids"]:
        await submissions_repo.update_status(submission_id, new_item_status)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="LOT_PUBLISHED",
        entity_type="lot",
        entity_id=lot_id,
        details={"status": new_lot_status, "bid_deadline": bid_deadline.isoformat()},
    )

    response = {
        "lot_id": lot_id,
        "rrr_id": lot["rrr_id"],
        "ward_id": lot["ward_id"],
        "category": lot["category"],
        "item_ids": lot["item_ids"],
        "status": new_lot_status,
        "bid_deadline": bid_deadline,
        "total_weight_kg": lot.get("total_weight_kg"),
        "item_details": lot.get("item_details", []),
    }
    await idempotency.store_response(current_user["user_id"], idempotency_key, LOT_PUBLISH_IDEMPOTENCY_SCOPE, response)
    return response


async def list_my_lots(current_user: dict) -> list[dict]:
    rrr_profile = await rrr_centres_service.require_approved_rrr(current_user)
    docs = await lots_repo.list_by_rrr(rrr_profile["rrr_id"])
    for d in docs:
        d.pop("_id", None)
    return docs


# Recyclers bid on what a lot contains, not on who handed it over or where.
# item_details also carries the home user's ID and the handover GPS point,
# time and photo (taken within MAX_HANDOVER_DISTANCE_METERS of the
# household), which only the lot owner and the Government Admin may see
# (architecture Section 17). An allow-list keeps any field added to
# item_details later from reaching recyclers by default.
_RECYCLER_ITEM_FIELDS = ("submission_id", "actual_weight_kg")


def _recycler_view(lot: dict) -> dict:
    view = dict(lot)
    view["item_details"] = [
        {field: item.get(field) for field in _RECYCLER_ITEM_FIELDS}
        for item in lot.get("item_details", [])
    ]
    return view


async def list_listed_for_bidding(current_user: dict) -> list[dict]:
    """Marketplace-wide, not ward-scoped — every APPROVED recycler can see
    every lot currently open for bidding, regardless of which RRR/ward
    published it. Gated only by approval status, same require_approved_*
    pattern as every other privileged action in this codebase."""
    await recyclers_service.require_approved_recycler(current_user)
    docs = await lots_repo.list_listed_for_bidding()
    for d in docs:
        d.pop("_id", None)
    return [_recycler_view(d) for d in docs]


async def get_lot(lot_id: str, current_user: dict) -> dict:
    lot = await lots_repo.find_by_lot_id(lot_id)
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists with this lot_id.")

    is_admin = current_user["role"] == "GOVERNMENT_ADMIN"
    is_owner = False
    if current_user["role"] == "RRR_CENTER":
        rrr_profile = await rrr_centres_service.require_approved_rrr(current_user)
        is_owner = lot.get("rrr_id") == rrr_profile["rrr_id"]
    # Collector-owned lot (auto-created from their own confirmed handover,
    # no RRR centre involved) — same ownership-scoped access pattern as
    # the RRR branch above, keyed on owner_collector_id instead of rrr_id.
    if current_user["role"] == "COLLECTOR":
        is_owner = lot.get("owner_collector_id") == current_user["user_id"]

    # Phase 6: any APPROVED recycler may view any lot's detail, read-only
    # and regardless of status — this is inherently public marketplace
    # information once a lot exists, unlike an RRR's or item's owner-only
    # data. Additive widening; RRR-own/admin-any behavior above unchanged.
    is_recycler_viewer = False
    if current_user["role"] == "RECYCLER":
        await recyclers_service.require_approved_recycler(current_user)
        is_recycler_viewer = True

    if not (is_owner or is_admin or is_recycler_viewer):
        raise forbidden("NOT_LOT_OWNER", "You do not have access to this lot.")

    lot.pop("_id", None)
    lot["price_estimate"] = await _lot_price_estimate(lot)
    if is_recycler_viewer:
        return _recycler_view(lot)
    return lot


async def _lot_price_estimate(lot: dict) -> dict | None:
    """Reuses the ML estimate already stored on each item's submission
    (never re-runs the model), with totals based on each item's actual
    collected weight."""
    weights = {d.get("submission_id"): d.get("actual_weight_kg") for d in lot.get("item_details", [])}
    items = []
    for item_id in lot.get("item_ids", []):
        submission = await submissions_repo.find_by_submission_id(item_id)
        if submission is None:
            return None
        weight = weights.get(item_id)
        if weight is None:
            weight = submission.get("actual_weight_kg")
        items.append((submission.get("price_estimate"), weight))
    return pricing_service.lot_price_estimate(items)


async def complete_lot(*, actor: dict, lot_id: str, idempotency_key: str) -> dict:
    """Phase 10: the final, controlled `SOLD -> COMPLETED` step the
    architecture's own state machines have defined since Phase 5/2 but
    that nothing ever drove — a genuine integration gap found during
    Phase 10's audit, not a redesign of Phase 9's payment flow. Payment
    semantics (READY_FOR_COLLECTION -> PAYMENT_PENDING -> SOLD/PAID) are
    completely untouched; this only adds the one step after a payment
    has already succeeded. Admin/system-controlled by design — no other
    role appears anywhere in the permission matrix for finalizing a sale,
    and a recycler/RRR marking their own sale "complete" would be an
    unchecked self-attestation with no independent verification."""
    cached = await idempotency.get_cached_response(actor["user_id"], idempotency_key, LOT_COMPLETE_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    lot = await lots_repo.find_by_lot_id(lot_id)
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists with this lot_id.")

    if lot["status"] == "COMPLETED":
        # A repeated completion attempt (a NEW idempotency key, not a
        # replay of the same one) on an already-completed lot is
        # rejected, not silently re-accepted — same "prevent
        # backwards/duplicate transitions with a clear conflict" pattern
        # already established by payments' LOT_ALREADY_PAID.
        raise conflict("LOT_ALREADY_COMPLETED", "This lot has already been marked COMPLETED.")
    if lot["status"] != "SOLD":
        raise bad_request(
            "LOT_NOT_SOLD", f"Lot is in status {lot['status']}, not eligible for completion."
        )

    new_lot_status = lot_states.transition("SOLD", "COMPLETED")
    await lots_repo.update_status(lot_id, new_lot_status)

    new_item_status = transition("PAID", "COMPLETED")
    for item_id in lot["item_ids"]:
        await submissions_repo.update_status(item_id, new_item_status)

    await audit.record(
        actor_id=actor["user_id"],
        actor_role=actor["role"],
        action="LOT_COMPLETED",
        entity_type="lot",
        entity_id=lot_id,
        details={"item_ids": lot["item_ids"]},
    )

    response = {
        "lot_id": lot_id,
        "rrr_id": lot["rrr_id"],
        "ward_id": lot["ward_id"],
        "category": lot["category"],
        "item_ids": lot["item_ids"],
        "status": new_lot_status,
        "bid_deadline": lot.get("bid_deadline"),
        "total_weight_kg": lot.get("total_weight_kg"),
        "item_details": lot.get("item_details", []),
    }
    await idempotency.store_response(actor["user_id"], idempotency_key, LOT_COMPLETE_IDEMPOTENCY_SCOPE, response)
    return response


async def list_all_for_admin(status: str | None = None) -> list[dict]:
    """Admin oversight (Phase 7): every lot, every RRR, not ward-scoped."""
    docs = await lots_repo.list_all(status=status)
    for d in docs:
        d.pop("_id", None)
    return docs

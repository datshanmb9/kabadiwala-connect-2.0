"""
Pure data access for the `e_waste_submissions` collection. No business rules
here — that lives in app/modules/ewaste/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_submission(submission_doc: dict[str, Any]) -> None:
    await get_db().e_waste_submissions.insert_one(submission_doc)


async def find_by_submission_id(submission_id: str) -> dict[str, Any] | None:
    return await get_db().e_waste_submissions.find_one({"submission_id": submission_id})


async def list_by_home_user(home_user_id: str) -> list[dict[str, Any]]:
    cursor = get_db().e_waste_submissions.find({"home_user_id": home_user_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def list_by_ward_and_status(ward_id: str, status: str) -> list[dict[str, Any]]:
    """General ward-scoped queue query, backing every "items waiting for
    my action" screen (collector pending-collection, RRR awaiting-receipt/
    awaiting-classification/classified-for-lot). Callers always pass their
    OWN ward_id (looked up server-side from their profile), never a
    client-supplied one — this can't be used to browse another ward's
    queue. Uses the (ward_id, status) index added in Phase 4."""
    cursor = get_db().e_waste_submissions.find(
        {"ward_id": ward_id, "status": status}
    ).sort("created_at", -1)
    return [doc async for doc in cursor]


async def list_pending_by_ward(ward_id: str) -> list[dict[str, Any]]:
    """Submissions awaiting collection in a given ward — the collector's
    pending queue. Thin, named wrapper kept for readability at call
    sites; identical query to list_by_ward_and_status(ward_id,
    "WAITING_FOR_COLLECTION")."""
    return await list_by_ward_and_status(ward_id, "WAITING_FOR_COLLECTION")


async def list_assigned_to_collector(collector_id: str) -> list[dict[str, Any]]:
    cursor = get_db().e_waste_submissions.find(
        {"assigned_collector_id": collector_id, "status": {"$in": ["COLLECTOR_ACCEPTED", "COLLECTING"]}}
    ).sort("created_at", -1)
    return [doc async for doc in cursor]


# Every status an item can be in from the moment its handover is verified
# (COLLECTED) onward — the "Accepted Collections" list (post-handover),
# distinct from list_assigned_to_collector above (pre-handover, still
# awaiting physical pickup). Uses the same (assigned_collector_id, status)
# index already created for list_assigned_to_collector's query shape.
HANDED_OVER_STATUSES = [
    "COLLECTED",
    "AT_RRR",
    "CLASSIFIED",
    "NEEDS_REVIEW",
    "LOT_CREATED",
    "LISTED_FOR_BIDDING",
    "BID_SELECTED",
    "LOGISTICS_BOOKED",
    "READY_FOR_COLLECTION",
    "PAYMENT_PENDING",
    "PAID",
    "COMPLETED",
]


async def list_handed_over_to_collector(collector_id: str) -> list[dict[str, Any]]:
    cursor = get_db().e_waste_submissions.find(
        {"assigned_collector_id": collector_id, "status": {"$in": HANDED_OVER_STATUSES}}
    ).sort("updated_at", -1)
    return [doc async for doc in cursor]


async def set_lot_id(submission_id: str, lot_id: str) -> None:
    await get_db().e_waste_submissions.update_one(
        {"submission_id": submission_id}, {"$set": {"lot_id": lot_id}}
    )


async def assign_collector_if_waiting(
    submission_id: str, collector_id: str, new_status: str, now
) -> dict[str, Any] | None:
    result = await get_db().e_waste_submissions.find_one_and_update(
        {"submission_id": submission_id, "status": "WAITING_FOR_COLLECTION"},
        {
            "$set": {
                "status": new_status,
                "assigned_collector_id": collector_id,
                "updated_at": now,
            }
        },
        return_document=True,
    )
    return result


async def update_collection_data(
    submission_id: str,
    *,
    new_status: str,
    actual_weight_kg: float | None,
    collector_lat: float | None,
    collector_lng: float | None,
    collection_ts,
    collection_photo_file_id: str,
    collector_id: str,
) -> None:
    from datetime import datetime, timezone

    update: dict[str, Any] = {
        "status": new_status,
        "collector_lat": collector_lat,
        "collector_lng": collector_lng,
        "collection_ts": collection_ts,
        "collection_photo_file_id": collection_photo_file_id,
        "assigned_collector_id": collector_id,
        "updated_at": datetime.now(timezone.utc),
    }
    if actual_weight_kg is not None:
        update["actual_weight_kg"] = actual_weight_kg
    await get_db().e_waste_submissions.update_one(
        {"submission_id": submission_id}, {"$set": update}
    )


async def list_all(status: str | None = None) -> list[dict[str, Any]]:
    """Admin oversight (Phase 7): every submission across every ward/home
    user, optionally filtered by status (e.g. FLAGGED_FOR_REVIEW). Unlike
    every other query in this file, this one is deliberately NOT scoped
    to a caller's own ward/ownership — GOVERNMENT_ADMIN is the one role
    the architecture's permission matrix grants system-wide visibility."""
    query: dict[str, Any] = {"status": status} if status else {}
    cursor = get_db().e_waste_submissions.find(query).sort("created_at", -1)
    return [doc async for doc in cursor]


async def update_status(submission_id: str, new_status: str) -> None:
    from datetime import datetime, timezone

    await get_db().e_waste_submissions.update_one(
        {"submission_id": submission_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
    )


async def update_status_and_category(submission_id: str, new_status: str, category: str) -> None:
    from datetime import datetime, timezone

    await get_db().e_waste_submissions.update_one(
        {"submission_id": submission_id},
        {"$set": {"status": new_status, "category": category, "updated_at": datetime.now(timezone.utc)}},
    )


async def set_reward_eligible_at_if_unset(submission_id: str, ts) -> None:
    """Phase 9: the authoritative, immutable reward-eligibility event
    (architecture Section 6.1/12) — written exactly once, at the moment
    an item first reaches COLLECTED, and never touched again by any
    later transition (CLASSIFIED, LOT_CREATED, SOLD, COMPLETED, ...).
    The {"reward_eligible_at": {"$exists": False}} precondition is what
    makes this genuinely set-once at the database level, not just by
    convention — same pattern as wards.rrr_centre_id's one-time
    assignment (Phase 5)."""
    await get_db().e_waste_submissions.update_one(
        {"submission_id": submission_id, "reward_eligible_at": {"$exists": False}},
        {"$set": {"reward_eligible_at": ts}},
    )


async def list_reward_eligible_in_period(start, end) -> list[dict[str, Any]]:
    """Every submission whose reward_eligible_at falls within [start, end)
    — the authoritative query for the monthly reward batch. Deliberately
    NOT a query on current `status` — an item's eligibility can never be
    silently lost or delayed by unrelated downstream lot/bid/payment
    activity (an unsold lot, a cancelled bid, a slow sale)."""
    cursor = get_db().e_waste_submissions.find(
        {"reward_eligible_at": {"$gte": start, "$lt": end}}
    )
    return [doc async for doc in cursor]

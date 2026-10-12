"""
Pure data access for the `lots` collection. No business rules here —
that lives in app/modules/lots/service.py.
"""
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_db


async def insert_lot(lot_doc: dict[str, Any]) -> None:
    await get_db().lots.insert_one(lot_doc)


async def find_by_lot_id(lot_id: str) -> dict[str, Any] | None:
    return await get_db().lots.find_one({"lot_id": lot_id})


async def list_by_rrr(rrr_id: str) -> list[dict[str, Any]]:
    cursor = get_db().lots.find({"rrr_id": rrr_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def list_listed_for_bidding() -> list[dict[str, Any]]:
    """Marketplace-wide (Phase 6): every lot currently open for bidding,
    across all RRRs/wards — recyclers are not ward-scoped anywhere in the
    architecture, unlike RRR/Collector queries which always filter to the
    caller's own ward."""
    cursor = get_db().lots.find({"status": "LISTED_FOR_BIDDING"}).sort("bid_deadline", 1)
    return [doc async for doc in cursor]


async def list_all(status: str | None = None) -> list[dict[str, Any]]:
    """Admin oversight (Phase 7): every lot across every RRR, optionally
    filtered by status — unlike list_by_rrr/list_listed_for_bidding above,
    deliberately not scoped to any owner."""
    query: dict[str, Any] = {"status": status} if status else {}
    cursor = get_db().lots.find(query).sort("created_at", -1)
    return [doc async for doc in cursor]


async def update_status_and_deadline(lot_id: str, new_status: str, bid_deadline: datetime) -> None:
    await get_db().lots.update_one(
        {"lot_id": lot_id},
        {"$set": {"status": new_status, "bid_deadline": bid_deadline, "updated_at": datetime.now(timezone.utc)}},
    )


async def update_status(lot_id: str, new_status: str) -> None:
    await get_db().lots.update_one(
        {"lot_id": lot_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
    )


async def transition_status_if_current(lot_id: str, from_status: str, to_status: str) -> bool:
    """Conditional, race-safe transition (Phase 9): succeeds only if the
    lot is still in from_status at the moment of the write; returns False
    (not an exception) otherwise — same conditional-update pattern as
    wards_repo.assign_rrr_centre. This is the actual concurrency guard
    for payment initiation: of two requests racing to move the same lot
    from READY_FOR_COLLECTION into PAYMENT_PENDING, only one can ever
    have its update match, so only one ever proceeds to call the (mock)
    gateway for that lot."""
    result = await get_db().lots.update_one(
        {"lot_id": lot_id, "status": from_status},
        {"$set": {"status": to_status, "updated_at": datetime.now(timezone.utc)}},
    )
    return result.matched_count == 1


async def list_by_lot_ids(lot_ids: list[str]) -> list[dict[str, Any]]:
    """Category/ward/weight of the given lots (pricing trend lookup)."""
    if not lot_ids:
        return []
    cursor = get_db().lots.find(
        {"lot_id": {"$in": lot_ids}},
        {"_id": 0, "lot_id": 1, "category": 1, "ward_id": 1, "total_weight_kg": 1},
    )
    return [doc async for doc in cursor]

"""
Pure data access for the `bids` collection. No business rules here —
that lives in app/modules/bids/service.py. In particular, this file does
not catch the duplicate-key error from the partial unique index on
(lot_id, status=ACCEPTED) — the service layer does, turning it into the
structured LOT_ALREADY_ACCEPTED response, same pattern as every other
DB-level race guard in this codebase.
"""
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_db


async def insert_bid(bid_doc: dict[str, Any]) -> None:
    await get_db().bids.insert_one(bid_doc)


async def find_by_bid_id(bid_id: str) -> dict[str, Any] | None:
    return await get_db().bids.find_one({"bid_id": bid_id})


async def list_by_recycler(recycler_id: str) -> list[dict[str, Any]]:
    cursor = get_db().bids.find({"recycler_id": recycler_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def list_by_lot(lot_id: str) -> list[dict[str, Any]]:
    cursor = get_db().bids.find({"lot_id": lot_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def list_all(status: str | None = None) -> list[dict[str, Any]]:
    """Admin oversight (Phase 7): every bid across every recycler/lot,
    optionally filtered by status (e.g. ACCEPTED) — deliberately not
    scoped to any owner, unlike list_by_recycler/list_by_lot above."""
    query: dict[str, Any] = {"status": status} if status else {}
    cursor = get_db().bids.find(query).sort("created_at", -1)
    return [doc async for doc in cursor]


async def find_accepted_bid_for_lot(lot_id: str) -> dict[str, Any] | None:
    """Phase 9: the one bid a lot's logistics/payment flow acts on. Relies
    on the same invariant the partial unique index enforces — at most one
    ACCEPTED bid can ever exist per lot — so this is a safe, unambiguous
    lookup, not an arbitrary "first match"."""
    return await get_db().bids.find_one({"lot_id": lot_id, "status": "ACCEPTED"})


async def update_status(bid_id: str, new_status: str, *, accepted_at: datetime | None = None) -> None:
    update: dict[str, Any] = {"status": new_status, "updated_at": datetime.now(timezone.utc)}
    if accepted_at is not None:
        update["accepted_at"] = accepted_at
    await get_db().bids.update_one({"bid_id": bid_id}, {"$set": update})


async def list_accepted_since(since: datetime) -> list[dict[str, Any]]:
    """ACCEPTED bids (agreed sale prices) accepted at or after `since` —
    the real market price records behind the pricing trend. A bid whose
    acceptance was later cancelled is CANCELLED, so it is not included."""
    cursor = get_db().bids.find(
        {"status": "ACCEPTED", "accepted_at": {"$gte": since}},
        {"_id": 0, "lot_id": 1, "amount": 1, "accepted_at": 1},
    )
    return [doc async for doc in cursor]

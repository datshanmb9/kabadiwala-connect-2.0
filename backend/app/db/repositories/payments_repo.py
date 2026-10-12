"""
Pure data access for the `payments` collection. No business rules here —
that lives in app/modules/payments/service.py. This file deliberately
does not catch the duplicate-key error from the partial unique index on
(lot_id, status=SUCCEEDED) — the service layer does, turning it into the
structured LOT_ALREADY_PAID response, same pattern as bids_repo.py's
accept-bid race guard.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_payment(payment_doc: dict[str, Any]) -> None:
    await get_db().payments.insert_one(payment_doc)


async def find_by_payment_id(payment_id: str) -> dict[str, Any] | None:
    return await get_db().payments.find_one({"payment_id": payment_id})


async def list_by_lot(lot_id: str) -> list[dict[str, Any]]:
    """Append-only history: every attempt (FAILED or SUCCEEDED) for a
    given lot, never overwritten."""
    cursor = get_db().payments.find({"lot_id": lot_id}).sort("created_at", 1)
    return [doc async for doc in cursor]


async def find_succeeded_for_lot(lot_id: str) -> dict[str, Any] | None:
    return await get_db().payments.find_one({"lot_id": lot_id, "status": "SUCCEEDED"})


async def list_all(status: str | None = None) -> list[dict[str, Any]]:
    """Admin oversight, same pattern as every other admin list (Phase 7)."""
    query: dict[str, Any] = {"status": status} if status else {}
    cursor = get_db().payments.find(query).sort("created_at", -1)
    return [doc async for doc in cursor]

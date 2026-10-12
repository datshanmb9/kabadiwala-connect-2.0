"""
Pure data access for the `wards` reference-data collection. No business
rules here — that lives in app/modules/wards/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_ward(ward_doc: dict[str, Any]) -> None:
    await get_db().wards.insert_one(ward_doc)


async def find_by_ward_id(ward_id: str) -> dict[str, Any] | None:
    return await get_db().wards.find_one({"ward_id": ward_id})


async def list_wards() -> list[dict[str, Any]]:
    cursor = get_db().wards.find().sort("ward_id", 1)
    return [doc async for doc in cursor]


async def assign_rrr_centre(ward_id: str, rrr_id: str) -> bool:
    """Links a ward to an approved RRR centre — only if the ward exists
    and doesn't already have one assigned. Returns False (not an
    exception) when that precondition fails, so the caller can turn it
    into a clear, specific error rather than a generic write failure. The
    partial unique index on wards.rrr_centre_id (see app/db/mongo.py) is
    the actual race-safe guarantee; this check just gives a clean error on
    the common sequential path, same pattern as the duplicate-handover
    pre-check in ewaste/service.py."""
    result = await get_db().wards.update_one(
        {"ward_id": ward_id, "rrr_centre_id": {"$exists": False}},
        {"$set": {"rrr_centre_id": rrr_id}},
    )
    return result.matched_count == 1

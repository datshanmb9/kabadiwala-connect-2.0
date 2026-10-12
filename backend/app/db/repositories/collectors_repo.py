"""
Pure data access for the `collectors` profile collection. No business rules
here — that lives in app/modules/collectors/service.py. In particular this
file exposes no update-by-collector path; only admin-facing service code
(Phase 2 scope: creation only) writes to this collection.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_profile(profile_doc: dict[str, Any]) -> None:
    await get_db().collectors.insert_one(profile_doc)


async def find_by_user_id(user_id: str) -> dict[str, Any] | None:
    return await get_db().collectors.find_one({"user_id": user_id})


async def find_by_employee_id(employee_id: str) -> dict[str, Any] | None:
    return await get_db().collectors.find_one({"employee_id": employee_id})


async def list_all() -> list[dict[str, Any]]:
    """Admin oversight (Phase 7). Collectors have no PENDING/APPROVED
    workflow (unlike RRR/recycler), so this takes no status filter —
    every collector document is admin-visible."""
    cursor = get_db().collectors.find().sort("created_at", 1)
    return [doc async for doc in cursor]


async def update_assignment(
    user_id: str, *, ward_id: str | None = None, rrr_id: str | None = None, assigned_area_radius_m: float | None = None
) -> bool:
    """Admin-only (Phase 7): the write path PROJECT_STATUS.md flagged as
    missing since Phase 2. Only fields explicitly passed are updated —
    None here means "not supplied," not "clear the field" (an update
    that wants to actually clear rrr_id passes an empty string, not
    None, so a partial PATCH body never accidentally wipes an
    unmentioned field)."""
    update: dict[str, Any] = {}
    if ward_id is not None:
        update["ward_id"] = ward_id
    if rrr_id is not None:
        update["rrr_id"] = rrr_id
    if assigned_area_radius_m is not None:
        update["assigned_area_radius_m"] = assigned_area_radius_m
    if not update:
        return True
    result = await get_db().collectors.update_one({"user_id": user_id}, {"$set": update})
    return result.matched_count == 1

"""
Pure data access for the `complaints` collection (new in Phase 7). No
business rules here — that lives in app/modules/complaints/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_complaint(complaint_doc: dict[str, Any]) -> None:
    await get_db().complaints.insert_one(complaint_doc)


async def find_by_complaint_id(complaint_id: str) -> dict[str, Any] | None:
    return await get_db().complaints.find_one({"complaint_id": complaint_id})


async def list_by_reporter(reporter_id: str) -> list[dict[str, Any]]:
    cursor = get_db().complaints.find({"reporter_id": reporter_id}).sort("created_at", -1)
    return [doc async for doc in cursor]


async def list_all(status: str | None = None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"status": status} if status else {}
    cursor = get_db().complaints.find(query).sort("created_at", -1)
    return [doc async for doc in cursor]


async def update_status(complaint_id: str, new_status: str, *, resolution_notes: str | None = None) -> None:
    from datetime import datetime, timezone

    update: dict[str, Any] = {"status": new_status, "updated_at": datetime.now(timezone.utc)}
    if resolution_notes is not None:
        update["resolution_notes"] = resolution_notes
    await get_db().complaints.update_one({"complaint_id": complaint_id}, {"$set": update})

"""
Pure data access for the `rrr_centres` collection. No business rules
here — that lives in app/modules/rrr_centres/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_profile(profile_doc: dict[str, Any]) -> None:
    await get_db().rrr_centres.insert_one(profile_doc)


async def find_by_user_id(user_id: str) -> dict[str, Any] | None:
    return await get_db().rrr_centres.find_one({"user_id": user_id})


async def list_all(status: str | None = None) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"status": status} if status else {}
    cursor = get_db().rrr_centres.find(query).sort("created_at", 1)
    return [doc async for doc in cursor]


async def update_status(user_id: str, new_status: str) -> None:
    await get_db().rrr_centres.update_one({"user_id": user_id}, {"$set": {"status": new_status}})

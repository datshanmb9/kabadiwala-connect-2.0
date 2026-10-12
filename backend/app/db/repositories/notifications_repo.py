"""Persistence for user-owned notifications."""
from typing import Any

from app.db.mongo import get_db


async def insert_notification(notification: dict[str, Any]) -> bool:
    from pymongo.errors import DuplicateKeyError

    try:
        await get_db().notifications.insert_one(notification)
    except DuplicateKeyError:
        return False
    return True


async def list_for_user(user_id: str, *, limit: int, offset: int) -> list[dict[str, Any]]:
    cursor = (
        get_db()
        .notifications.find({"user_id": user_id})
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )
    return [doc async for doc in cursor]


async def count_unread(user_id: str) -> int:
    return await get_db().notifications.count_documents({"user_id": user_id, "read": False})


async def mark_read(user_id: str, notification_id: str, read_at) -> dict[str, Any] | None:
    return await get_db().notifications.find_one_and_update(
        {"user_id": user_id, "notification_id": notification_id},
        {"$set": {"read": True, "read_at": read_at}},
        return_document=True,
    )


async def mark_all_read(user_id: str, read_at) -> int:
    result = await get_db().notifications.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True, "read_at": read_at}},
    )
    return result.modified_count

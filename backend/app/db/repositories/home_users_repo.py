"""
Pure data access for the `home_users` profile collection. No business rules
here — that lives in app/modules/home_users/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_profile(profile_doc: dict[str, Any]) -> None:
    await get_db().home_users.insert_one(profile_doc)


async def find_by_user_id(user_id: str) -> dict[str, Any] | None:
    return await get_db().home_users.find_one({"user_id": user_id})


async def update_profile(user_id: str, values: dict[str, Any]) -> None:
    await get_db().home_users.update_one({"user_id": user_id}, {"$set": values})


async def update_preferences(user_id: str, preferences: dict[str, Any]) -> None:
    await get_db().home_users.update_one(
        {"user_id": user_id},
        {"$set": {f"preferences.{key}": value for key, value in preferences.items()}},
    )

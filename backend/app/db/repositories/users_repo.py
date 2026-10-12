"""
Pure data access for the `users` collection. No business rules here —
that lives in app/modules/auth/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def find_by_username(username: str) -> dict[str, Any] | None:
    return await get_db().users.find_one({"username": username})


async def find_by_id(user_id: str) -> dict[str, Any] | None:
    return await get_db().users.find_one({"user_id": user_id})


async def insert_user(user_doc: dict[str, Any]) -> None:
    await get_db().users.insert_one(user_doc)


async def delete_user(user_id: str) -> None:
    await get_db().users.delete_one({"user_id": user_id})


async def set_refresh_token_hash(user_id: str, refresh_token_hash: str | None) -> None:
    await get_db().users.update_one(
        {"user_id": user_id},
        {"$set": {"refresh_token_hash": refresh_token_hash}},
    )


async def update_status(user_id: str, new_status: str) -> None:
    """Admin-only write path (Phase 7): toggling a collector (or any
    account) between ACTIVE/DISABLED. Enforcement is not cosmetic — every
    request re-fetches this same document via get_current_user() and
    rejects non-ACTIVE accounts with ACCOUNT_DISABLED, so a disabled
    account is locked out immediately, not just hidden from a list."""
    await get_db().users.update_one({"user_id": user_id}, {"$set": {"status": new_status}})


async def deactivate(user_id: str) -> None:
    await get_db().users.update_one(
        {"user_id": user_id},
        {"$set": {"status": "DISABLED", "refresh_token_hash": None}},
    )


async def count_by_role(role: str) -> int:
    return await get_db().users.count_documents({"role": role})

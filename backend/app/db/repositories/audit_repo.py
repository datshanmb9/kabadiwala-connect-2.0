"""
Append-only access to `audit_logs`. Deliberately exposes only `insert` and
`find` — there is no update/delete function anywhere in this file, and
nothing elsewhere in the app should reach into this collection directly.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_log(log_doc: dict[str, Any]) -> None:
    await get_db().audit_logs.insert_one(log_doc)


async def list_logs(
    *,
    skip: int = 0,
    limit: int = 50,
    actor_role: str | None = None,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Phase 7 adds optional actor_role/entity_type filters, additive to
    the existing skip/limit pagination — every existing caller that
    passes neither still gets the original unfiltered behavior. Used both
    for the general Audit Logs page and, with actor_role="GOVERNMENT_ADMIN",
    as the "Government Actions" view — reusing this one append-only
    collection rather than standing up the architecture's separate
    government_actions collection early (its real payload, eligibility
    invalidations, doesn't exist until Phase 9)."""
    query: dict[str, Any] = {}
    if actor_role:
        query["actor_role"] = actor_role
    if entity_type:
        query["entity_type"] = entity_type
    cursor = get_db().audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    return [doc async for doc in cursor]

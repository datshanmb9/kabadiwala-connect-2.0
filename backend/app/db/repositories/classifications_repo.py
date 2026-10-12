"""
Pure data access for the `ai_classifications` collection. Append-only by
convention (like audit_logs) — every classification attempt (AI or
manual) is kept, never overwritten, so predicted vs. confirmed category
stay both visible. No business rules here — that lives in
app/modules/classification/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_classification(doc: dict[str, Any]) -> None:
    await get_db().ai_classifications.insert_one(doc)


async def find_by_item_id(item_id: str) -> dict[str, Any] | None:
    """Most recent classification attempt for an item, if any."""
    return await get_db().ai_classifications.find_one({"item_id": item_id}, sort=[("created_at", -1)])

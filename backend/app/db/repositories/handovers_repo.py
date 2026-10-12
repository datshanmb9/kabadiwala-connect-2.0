"""
Pure data access for the `collection_handovers` collection. No business
rules here — that lives in app/modules/ewaste/service.py. The unique index
on `submission_id` (see app/db/mongo.py) is what actually enforces "one
handover per submission" at the database level; this file does not catch
that duplicate-key error itself so the service layer can turn it into the
structured DUPLICATE_HANDOVER response.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_handover(handover_doc: dict[str, Any]) -> None:
    await get_db().collection_handovers.insert_one(handover_doc)


async def find_by_submission_id(submission_id: str) -> dict[str, Any] | None:
    return await get_db().collection_handovers.find_one({"submission_id": submission_id})


async def list_all(verification_result: str | None = None) -> list[dict[str, Any]]:
    """Admin oversight (Phase 7): geo-verification detail (distance_m,
    verification_result) that never gets copied onto the submission
    document — this is the only read path that reaches it, optionally
    filtered to just the FLAGGED ones for a "geo-verification failures"
    view."""
    query: dict[str, Any] = {"verification_result": verification_result} if verification_result else {}
    cursor = get_db().collection_handovers.find(query).sort("collector_ts", -1)
    return [doc async for doc in cursor]

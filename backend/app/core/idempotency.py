"""
Generic idempotency-key helper for state-changing/financial endpoints
(bids, payments, rewards, submissions, handovers — Phase 2 onward).

Not wired into any Phase 1 endpoint: login/refresh/logout are not on the
idempotency-required list in the architecture doc (Section 30), so Phase 1
intentionally does not create the `idempotency_keys` collection or its
index yet — the module owning the first idempotent endpoint (Phase 2's
e-waste submission) is responsible for adding that index alongside its own
collections, per the "index ownership lives next to the code that uses it"
convention in app/db/mongo.py.

This file only defines the reusable mechanism so every later module uses
the same pattern instead of inventing its own.

Phase 11 security fix: the cache is scoped per calling user
(user_id, idempotency_key, scope), not just (idempotency_key, scope).
Before this fix, if an idempotency-key value was ever known or reused
across two different accounts for the same scope, the second caller
received the FIRST caller's cached response — bypassing whatever
ownership/approval check ran on the original request, since a cache hit
short-circuits before any such check runs again. Real-world
exploitability was low (every client generates a cryptographically
random UUID), but this closes the structural gap regardless of key
randomness. See PROJECT_STATUS.md Phase 11 for the full writeup.
"""
from typing import Any

from app.db.mongo import get_db
from app.core.errors import AppError


async def get_cached_response(user_id: str, idempotency_key: str, scope: str) -> dict[str, Any] | None:
    doc = await get_db().idempotency_keys.find_one(
        {"user_id": user_id, "idempotency_key": idempotency_key, "scope": scope}
    )
    return doc["response"] if doc else None


async def store_response(user_id: str, idempotency_key: str, scope: str, response: dict[str, Any]) -> None:
    try:
        await get_db().idempotency_keys.insert_one(
            {"user_id": user_id, "idempotency_key": idempotency_key, "scope": scope, "response": response}
        )
    except Exception as exc:  # duplicate key = a concurrent request already stored it
        raise AppError(
            status_code=409,
            error_code="DUPLICATE_REQUEST",
            message="This request is already being processed.",
        ) from exc

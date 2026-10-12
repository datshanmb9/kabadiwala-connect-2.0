"""
Pure data access for the `rewards` and `reward_transactions` collections.
No business rules here — that lives in app/modules/rewards/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_reward(reward_doc: dict[str, Any]) -> None:
    await get_db().rewards.insert_one(reward_doc)


async def find_by_home_user_and_period(home_user_id: str, period: str) -> dict[str, Any] | None:
    return await get_db().rewards.find_one({"home_user_id": home_user_id, "period": period})


async def find_by_reward_id(reward_id: str) -> dict[str, Any] | None:
    return await get_db().rewards.find_one({"reward_id": reward_id})


async def list_by_home_user(home_user_id: str) -> list[dict[str, Any]]:
    cursor = get_db().rewards.find({"home_user_id": home_user_id}).sort("period", -1)
    return [doc async for doc in cursor]


async def list_by_period(period: str) -> list[dict[str, Any]]:
    cursor = get_db().rewards.find({"period": period})
    return [doc async for doc in cursor]


async def list_all() -> list[dict[str, Any]]:
    cursor = get_db().rewards.find().sort("period", -1)
    return [doc async for doc in cursor]


async def update_status(reward_id: str, new_status: str) -> None:
    await get_db().rewards.update_one({"reward_id": reward_id}, {"$set": {"status": new_status}})


async def transition_status_if_current(reward_id: str, from_status: str, to_status: str) -> bool:
    """Phase 11 security fix: the real concurrency guard against duplicate
    redemption — a single conditional write that only one of two racing
    requests can ever have matched, returning False (not an exception)
    for the loser. Same pattern as lots_repo.transition_status_if_current
    (Phase 9's payment-race guard) and wards_repo.assign_rrr_centre
    (Phase 5); previously redeem_reward() only did a plain read-then-check
    with no atomic guard at all, allowing two concurrent redemption
    requests for the same reward to both pass the status check and both
    succeed against the mock payout."""
    result = await get_db().rewards.update_one(
        {"reward_id": reward_id, "status": from_status}, {"$set": {"status": to_status}}
    )
    return result.matched_count == 1


# --- reward_transactions (append-only ledger) -------------------------


async def insert_transaction(txn_doc: dict[str, Any]) -> None:
    await get_db().reward_transactions.insert_one(txn_doc)


async def list_transactions_by_home_user(
    home_user_id: str, *, limit: int | None = None, offset: int = 0
) -> list[dict[str, Any]]:
    cursor = get_db().reward_transactions.find({"home_user_id": home_user_id}).sort("created_at", -1).skip(offset)
    if limit is not None:
        cursor = cursor.limit(limit)
    return [doc async for doc in cursor]


async def list_transactions_by_reward(reward_id: str) -> list[dict[str, Any]]:
    cursor = get_db().reward_transactions.find({"reward_id": reward_id}).sort("created_at", 1)
    return [doc async for doc in cursor]

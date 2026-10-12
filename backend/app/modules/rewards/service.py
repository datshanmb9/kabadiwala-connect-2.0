"""
Reward computation + mock UPI redemption (architecture Section 12).

Eligibility is keyed ENTIRELY on `e_waste_submissions.reward_eligible_at`
(set exactly once, at COLLECTED, by ewaste/service.py's handover()) —
never on an item's current/later status. An item whose lot is never
sold, whose bid gets cancelled, or that is still sitting in
NEEDS_REVIEW months later still earns its reward the moment it was
collected; none of that downstream activity is queried here at all.

No automatic clawback exists anywhere in this module — there is no
function that decrements a reward or reward_transactions balance. The
"never claw back" guarantee holds structurally (nothing to call), the
same proof-by-absence method used for AI-credential-optionality in
Phase 8.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from bson.decimal128 import Decimal128

from app.core import audit, idempotency
from app.core.config import settings
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.db.repositories import home_users_repo, rewards_repo, submissions_repo
from app.modules.rewards.payout import payout
from app.modules.notifications import service as notifications_service

REDEEM_IDEMPOTENCY_SCOPE = "reward_redeem"


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    """'YYYY-MM' -> [start, end) as naive UTC datetimes, the same
    convention every stored timestamp in this codebase uses (real
    MongoDB always hands back naive-but-UTC datetimes)."""
    try:
        year, month = (int(p) for p in period.split("-", 1))
        if not (1 <= month <= 12):
            raise ValueError
    except ValueError as exc:
        raise bad_request("INVALID_PERIOD", "period must be in YYYY-MM format.") from exc

    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def _amount_to_str(stored: Decimal128 | Decimal | str) -> str:
    if isinstance(stored, Decimal128):
        return str(stored.to_decimal())
    return str(stored)


def _reward_to_response(doc: dict) -> dict:
    return {
        "reward_id": doc["reward_id"],
        "home_user_id": doc["home_user_id"],
        "period": doc["period"],
        "points": doc["points"],
        "amount": _amount_to_str(doc["amount"]),
        "status": doc["status"],
        "created_at": doc["created_at"],
    }


def _txn_to_response(doc: dict) -> dict:
    return {
        "txn_id": doc["txn_id"],
        "home_user_id": doc["home_user_id"],
        "reward_id": doc["reward_id"],
        "type": doc["type"],
        "amount": _amount_to_str(doc["amount"]),
        "status": doc["status"],
        "created_at": doc["created_at"],
    }


async def compute_rewards_for_period(*, period: str, actor: dict) -> list[dict]:
    """Admin-triggered batch (no scheduler infrastructure exists — this
    is the deliberate, disclosed equivalent of the architecture's
    month-end batch job). Idempotent by construction: a home user
    already credited for this exact period is skipped, never
    re-credited or double-counted — the unique(home_user_id, period)
    index is the structural backstop, this pre-check is just a clean
    no-op on the common re-run path."""
    start, end = _period_bounds(period)

    eligible_docs = await submissions_repo.list_reward_eligible_in_period(start, end)

    by_home_user: dict[str, int] = {}
    for doc in eligible_docs:
        by_home_user[doc["home_user_id"]] = by_home_user.get(doc["home_user_id"], 0) + 1

    created: list[dict] = []
    now = _naive_utc(datetime.now(timezone.utc))
    point_value = Decimal(settings.reward_value_per_point_inr)

    for home_user_id, item_count in by_home_user.items():
        existing = await rewards_repo.find_by_home_user_and_period(home_user_id, period)
        if existing is not None:
            continue  # already computed for this period — never re-credited

        points = item_count * settings.reward_points_per_item
        amount = Decimal(points) * point_value

        reward_id = str(uuid4())
        reward_doc = {
            "reward_id": reward_id,
            "home_user_id": home_user_id,
            "period": period,
            "points": points,
            "amount": Decimal128(amount),
            "status": "CREDITED",
            "item_count": item_count,
            "created_at": now,
        }
        await rewards_repo.insert_reward(reward_doc)

        txn_doc = {
            "txn_id": str(uuid4()),
            "home_user_id": home_user_id,
            "reward_id": reward_id,
            "type": "CREDIT",
            "amount": Decimal128(amount),
            "status": "SUCCEEDED",
            "idempotency_key": f"{home_user_id}:{period}:credit",
            "created_at": now,
        }
        await rewards_repo.insert_transaction(txn_doc)

        await notifications_service.create_notification(
            user_id=home_user_id,
            event_key=f"reward:{reward_id}:credited",
            notification_type="REWARD_CREDITED",
            title_key="Reward credit available",
            message_key="A reward credit has been added to your account.",
            related_entity_type="reward",
            related_entity_id=reward_id,
            metadata={"amount": str(amount), "period": period},
        )

        await audit.record(
            actor_id=actor["user_id"],
            actor_role=actor["role"],
            action="REWARD_COMPUTED",
            entity_type="reward",
            entity_id=reward_id,
            details={"home_user_id": home_user_id, "period": period, "points": points, "amount": str(amount)},
        )

        created.append(_reward_to_response(reward_doc))

    return created


async def list_my_rewards(current_user: dict) -> list[dict]:
    docs = await rewards_repo.list_by_home_user(current_user["user_id"])
    return [_reward_to_response(d) for d in docs]


async def list_all_for_admin(period: str | None = None) -> list[dict]:
    docs = await rewards_repo.list_by_period(period) if period else await rewards_repo.list_all()
    return [_reward_to_response(d) for d in docs]


async def redeem_reward(*, current_user: dict, reward_id: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, REDEEM_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    reward = await rewards_repo.find_by_reward_id(reward_id)
    if reward is None:
        raise not_found("REWARD_NOT_FOUND", "No reward exists with this reward_id.")
    if reward["home_user_id"] != current_user["user_id"]:
        raise forbidden("NOT_REWARD_OWNER", "You do not have access to this reward.")
    if reward["status"] != "CREDITED":
        raise bad_request(
            "REWARD_NOT_REDEEMABLE", f"Reward is in status {reward['status']}, not eligible for redemption."
        )

    home_profile = await home_users_repo.find_by_user_id(current_user["user_id"])
    upi_id = home_profile.get("upi_id") if home_profile else None
    if not upi_id:
        # Never asks for or accepts a PIN/password — only confirms an
        # account identifier is on file, exactly like every other
        # ownership check in this codebase.
        raise bad_request("NO_UPI_ID_ON_FILE", "Add a UPI ID to your profile before requesting redemption.")

    # Phase 11 security fix — the real concurrency guard: only one of two
    # racing redemption requests for the same reward can ever win this
    # conditional write (mirrors lots_repo.transition_status_if_current,
    # Phase 9's payment-race guard). The loser is rejected here, before
    # ever calling the mock payout or inserting a transaction — no
    # possibility of two SUCCEEDED redemption records for one reward.
    claimed = await rewards_repo.transition_status_if_current(reward_id, "CREDITED", "REDEEMING")
    if not claimed:
        raise conflict(
            "REWARD_REDEMPTION_ALREADY_IN_PROGRESS",
            "A redemption attempt for this reward is already in progress or has already completed.",
        )

    amount_str = _amount_to_str(reward["amount"])
    result = payout(reward_id, amount_str)
    now = _naive_utc(datetime.now(timezone.utc))

    txn_doc = {
        "txn_id": str(uuid4()),
        "home_user_id": current_user["user_id"],
        "reward_id": reward_id,
        "type": "REDEMPTION",
        "amount": reward["amount"],
        "status": "SUCCEEDED" if result.succeeded else "FAILED",
        "gateway": "MOCK_UPI_PAYOUT",
        "gateway_reference": result.reference,
        "idempotency_key": f"{reward_id}:redemption:{idempotency_key}",
        "created_at": now,
    }
    await rewards_repo.insert_transaction(txn_doc)

    if result.succeeded:
        await rewards_repo.update_status(reward_id, "REDEEMED")
        reward["status"] = "REDEEMED"
    else:
        # Revert the transient claim so the home user can retry — same
        # "failure reopens for retry" shape as payments' PAYMENT_PENDING
        # -> READY_FOR_COLLECTION revert.
        await rewards_repo.update_status(reward_id, "CREDITED")
        reward["status"] = "CREDITED"

    await notifications_service.create_notification(
        user_id=current_user["user_id"],
        event_key=f"reward:{reward_id}:redemption:{txn_doc['status']}:{idempotency_key}",
        notification_type=(
            "REWARD_REDEMPTION_SUCCEEDED" if result.succeeded else "REWARD_REDEMPTION_FAILED"
        ),
        title_key=(
            "Reward redemption completed" if result.succeeded else "Reward redemption failed"
        ),
        message_key=(
            "Your reward redemption was completed."
            if result.succeeded
            else "Your reward redemption could not be completed. You may retry."
        ),
        related_entity_type="reward",
        related_entity_id=reward_id,
        metadata={"amount": amount_str, "status": txn_doc["status"]},
    )

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="REWARD_REDEMPTION_ATTEMPTED",
        entity_type="reward",
        entity_id=reward_id,
        details={"succeeded": result.succeeded, "amount": amount_str, "gateway_reference": result.reference},
    )

    response = _txn_to_response(txn_doc)
    await idempotency.store_response(current_user["user_id"], idempotency_key, REDEEM_IDEMPOTENCY_SCOPE, response)
    return response


async def list_my_transactions(current_user: dict, *, limit: int = 20, offset: int = 0) -> dict:
    docs = await rewards_repo.list_transactions_by_home_user(
        current_user["user_id"], limit=limit, offset=offset
    )
    return {
        "transactions": [_txn_to_response(d) for d in docs],
        "has_more": len(docs) == limit,
    }


async def summarize_my_transactions(current_user: dict) -> dict:
    docs = await rewards_repo.list_transactions_by_home_user(current_user["user_id"])
    completed_credits = Decimal("0")
    completed_redemptions = Decimal("0")
    failed_count = 0
    for document in docs:
        amount = document["amount"].to_decimal() if isinstance(document["amount"], Decimal128) else Decimal(str(document["amount"]))
        if document["status"] != "SUCCEEDED":
            failed_count += 1
            continue
        if document["type"] == "CREDIT":
            completed_credits += amount
        elif document["type"] == "REDEMPTION":
            completed_redemptions += amount
    return {
        "completed_credits": str(completed_credits),
        "completed_redemptions": str(completed_redemptions),
        "failed_count": failed_count,
        "pending_amount": "0",
    }

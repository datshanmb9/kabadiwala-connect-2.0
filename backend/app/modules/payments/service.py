"""
Mock payment processing (architecture Section 11) — the last step in the
LOT -> BID -> LOGISTICS -> PAYMENT -> SOLD/COMPLETED flow. Drives TWO
state machines in parallel per write (the lot's own status and each
contained item's status), same pattern established since Phase 5/6/9's
logistics module — no endpoint writes a status field directly.

Money: the amount is read from the accepted bid's own Decimal128 field
and carried through unchanged — this module never re-parses a
client-supplied amount at payment time. The price was already fixed and
validated when the bid was placed (Phase 6); removing any "amount" input
from this endpoint removes an entire class of "client changes the price
at payment time" bug by construction, not by validation.

Concurrency: the actual guard against two racing payment attempts for
the same lot is lots_repo.transition_status_if_current() — a
conditional database write that only one of two concurrent requests can
ever win. The partial unique index on payments.lot_id (status=SUCCEEDED
only) is the second, independent layer of defense at the database level
for the SUCCEEDED-insert itself.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from bson.decimal128 import Decimal128
from pymongo.errors import DuplicateKeyError

from app.core import audit, idempotency
from app.core.config import settings
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.db.repositories import bids_repo, lots_repo, payments_repo, submissions_repo
from app.modules.payments.gateway import charge
from app.modules.recyclers import service as recyclers_service
from app.state_machines import lot_states
from app.state_machines.ewaste_states import transition as item_transition

PAYMENT_IDEMPOTENCY_SCOPE = "payment_initiate"


def _naive_utc(dt: datetime) -> datetime:
    """Same normalization used throughout this codebase since Phase 2:
    real MongoDB always returns naive-but-UTC datetimes; mongomock can
    hand back a tz-aware object as-is, so every timestamp is normalized
    before storing or comparing to behave identically against both."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _amount_to_str(stored: Decimal128 | Decimal | str) -> str:
    if isinstance(stored, Decimal128):
        return str(stored.to_decimal())
    return str(stored)


def _to_response(doc: dict) -> dict:
    return {
        "payment_id": doc["payment_id"],
        "lot_id": doc["lot_id"],
        "recycler_id": doc["recycler_id"],
        "amount": _amount_to_str(doc["amount"]),
        "status": doc["status"],
        "gateway": doc["gateway"],
        "gateway_reference": doc.get("gateway_reference"),
        "created_at": doc["created_at"],
    }


async def initiate_payment(*, current_user: dict, lot_id: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, PAYMENT_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    recycler_profile = await recyclers_service.require_approved_recycler(current_user)

    lot = await lots_repo.find_by_lot_id(lot_id)
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists with this lot_id.")

    accepted_bid = await bids_repo.find_accepted_bid_for_lot(lot_id)
    if accepted_bid is None or accepted_bid["recycler_id"] != recycler_profile["license_id"]:
        raise forbidden("NOT_ACCEPTED_BID_OWNER", "You do not have an accepted bid on this lot.")
    if accepted_bid["status"] != "ACCEPTED":
        # Guards against a cancelled/invalid bid ever reaching payment —
        # in normal operation the lot's own status check below already
        # rules this out (a cancelled acceptance reopens the lot), but
        # this is the direct, explicit check on the bid itself.
        raise bad_request("BID_NOT_ACCEPTED", "The accepted bid for this lot is no longer active.")

    already_succeeded = await payments_repo.find_succeeded_for_lot(lot_id)
    if already_succeeded is not None:
        raise conflict("LOT_ALREADY_PAID", "This lot has already been paid for.")

    if lot["status"] != "READY_FOR_COLLECTION":
        raise bad_request(
            "LOT_NOT_READY_FOR_COLLECTION",
            f"Lot is in status {lot['status']}, not eligible for payment.",
        )

    # The actual concurrency guard: only one of two racing requests can
    # ever win this conditional write for the same lot. The loser gets a
    # clean rejection here, before ever calling the (mock) gateway or
    # touching any item — no transient/stuck intermediate state possible.
    entered_pending = await lots_repo.transition_status_if_current(lot_id, "READY_FOR_COLLECTION", "PAYMENT_PENDING")
    if not entered_pending:
        raise conflict(
            "PAYMENT_ALREADY_IN_PROGRESS",
            "A payment attempt for this lot is already in progress or has already completed.",
        )
    pending_item_status = item_transition("READY_FOR_COLLECTION", "PAYMENT_PENDING")
    for item_id in lot["item_ids"]:
        await submissions_repo.update_status(item_id, pending_item_status)

    payment_id = str(uuid4())
    now = _naive_utc(datetime.now(timezone.utc))
    amount = accepted_bid["amount"]  # already Decimal128 — never re-parsed from client input
    amount_str = _amount_to_str(amount)

    gateway_result = charge(amount_str)

    if gateway_result.succeeded:
        payment_status = "SUCCEEDED"
        new_lot_status = lot_states.transition("PAYMENT_PENDING", "SOLD")
        new_item_status = item_transition("PAYMENT_PENDING", "PAID")
    else:
        payment_status = "FAILED"
        new_lot_status = lot_states.transition("PAYMENT_PENDING", "READY_FOR_COLLECTION")
        new_item_status = item_transition("PAYMENT_PENDING", "READY_FOR_COLLECTION")

    payment_doc = {
        "payment_id": payment_id,
        "lot_id": lot_id,
        "recycler_id": recycler_profile["license_id"],
        "amount": amount,
        "status": payment_status,
        "gateway": settings.payment_mode,
        "gateway_reference": gateway_result.reference,
        "idempotency_key": idempotency_key,
        "created_at": now,
    }
    try:
        await payments_repo.insert_payment(payment_doc)
    except DuplicateKeyError as exc:
        # Backstop only — the conditional lot transition above already
        # prevents two requests from both reaching this point for the
        # same lot, but the partial unique index on
        # payments.lot_id(status=SUCCEEDED) is kept as a second,
        # independent database-level guarantee, same defense-in-depth
        # pattern as every other DB-level race guard in this codebase.
        raise conflict("LOT_ALREADY_PAID", "This lot has already been paid for.") from exc

    await lots_repo.update_status(lot_id, new_lot_status)
    for item_id in lot["item_ids"]:
        await submissions_repo.update_status(item_id, new_item_status)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="PAYMENT_ATTEMPTED",
        entity_type="lot",
        entity_id=lot_id,
        details={
            "payment_id": payment_id,
            "status": payment_status,
            "amount": amount_str,
            "gateway_reference": gateway_result.reference,
        },
    )

    response = _to_response(payment_doc)
    await idempotency.store_response(current_user["user_id"], idempotency_key, PAYMENT_IDEMPOTENCY_SCOPE, response)
    return response


async def list_payments_for_lot(*, current_user: dict, lot_id: str) -> list[dict]:
    """Recycler-own or admin — append-only history of every attempt."""
    lot = await lots_repo.find_by_lot_id(lot_id)
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists with this lot_id.")

    if current_user["role"] != "GOVERNMENT_ADMIN":
        recycler_profile = await recyclers_service.require_approved_recycler(current_user)
        accepted_bid = await bids_repo.find_accepted_bid_for_lot(lot_id)
        if accepted_bid is None or accepted_bid["recycler_id"] != recycler_profile["license_id"]:
            raise forbidden("NOT_ACCEPTED_BID_OWNER", "You do not have an accepted bid on this lot.")

    docs = await payments_repo.list_by_lot(lot_id)
    return [_to_response(d) for d in docs]


async def list_all_for_admin(status: str | None = None) -> list[dict]:
    docs = await payments_repo.list_all(status=status)
    return [_to_response(d) for d in docs]

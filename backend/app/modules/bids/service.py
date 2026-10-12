"""
Bid placement, cancellation, acceptance, and acceptance-cancellation
(architecture Section 6.2/10). Drives THREE state machines in parallel
per accept/cancel-acceptance call: the bid's own status
(state_machines/bid_states.py), the lot's status
(state_machines/lot_states.py, unchanged since Phase 5), and each
contained item's status (state_machines/ewaste_states.py, unchanged
since Phase 2 except the one Phase 6 addition of
BID_SELECTED->LISTED_FOR_BIDDING). No endpoint writes a `status` field
directly on any of the three — every change goes through that
collection's own transition() function.

Money: amounts are accepted/returned as decimal strings only, parsed to
Decimal, stored as bson.Decimal128 — never a Python float, anywhere in
this file, per the architecture's explicit money rule.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from bson.decimal128 import Decimal128
from pymongo.errors import DuplicateKeyError

from app.core import audit, idempotency
from app.core.config import settings
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.db.repositories import bids_repo, lots_repo, submissions_repo, users_repo
from app.modules.rrr_centres import service as rrr_centres_service
from app.modules.recyclers import service as recyclers_service
from app.modules.notifications import service as notifications_service
from app.state_machines import bid_states, lot_states
from app.state_machines.ewaste_states import transition as item_transition

PLACE_BID_IDEMPOTENCY_SCOPE = "bid_place"
CANCEL_BID_IDEMPOTENCY_SCOPE = "bid_cancel"
ACCEPT_BID_IDEMPOTENCY_SCOPE = "bid_accept"
CANCEL_ACCEPTANCE_IDEMPOTENCY_SCOPE = "bid_cancel_acceptance"


def _naive_utc(dt: datetime) -> datetime:
    """Same normalization as ewaste/service.py — real MongoDB always
    returns naive-but-UTC datetimes; mongomock can hand back a tz-aware
    object as-is, so every timestamp is normalized before storing or
    comparing to behave identically against both."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_amount(raw: str) -> Decimal:
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise bad_request("INVALID_BID_AMOUNT", "Bid amount must be a valid decimal number.") from exc
    if not amount.is_finite() or amount <= 0:
        raise bad_request("INVALID_BID_AMOUNT", "Bid amount must be a positive, finite number.")
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise bad_request("INVALID_BID_AMOUNT", "Bid amount may have at most 2 decimal places.")
    return amount


def _amount_to_str(stored: Decimal128 | Decimal | str) -> str:
    if isinstance(stored, Decimal128):
        return str(stored.to_decimal())
    return str(stored)


async def _require_lot_owner(current_user: dict, lot: dict) -> None:
    """Whoever is allowed to choose the winning bid for this lot: the RRR
    centre that built it, or — for a lot auto-created from a collector's
    own confirmed handover (see ewaste/service.py's
    auto_progress_to_listed_lot) — that collector. Exactly one of
    lot["rrr_id"]/lot["owner_collector_id"] is set on any given lot."""
    role = current_user["role"]
    if role == "RRR_CENTER":
        rrr_profile = await rrr_centres_service.require_approved_rrr(current_user)
        if lot.get("rrr_id") == rrr_profile["rrr_id"]:
            return
    elif role == "COLLECTOR":
        if lot.get("owner_collector_id") == current_user["user_id"]:
            return
    raise forbidden("NOT_LOT_OWNER", "You do not have access to this lot.")


def _to_bid_response(doc: dict) -> dict:
    return {
        "bid_id": doc["bid_id"],
        "lot_id": doc["lot_id"],
        "recycler_id": doc["recycler_id"],
        "amount": _amount_to_str(doc["amount"]),
        "status": doc["status"],
        "placed_at": doc["placed_at"],
        "accepted_at": doc.get("accepted_at"),
    }


async def place_bid(*, current_user: dict, lot_id: str, amount_str: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, PLACE_BID_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    recycler_profile = await recyclers_service.require_approved_recycler(current_user)
    amount = _parse_amount(amount_str)

    lot = await lots_repo.find_by_lot_id(lot_id)
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists with this lot_id.")
    if lot["status"] != "LISTED_FOR_BIDDING":
        raise bad_request(
            "LOT_NOT_LISTED_FOR_BIDDING", f"Lot is in status {lot['status']}, not currently open for bidding."
        )

    now = datetime.now(timezone.utc)
    bid_deadline = lot.get("bid_deadline")
    if bid_deadline is not None and _naive_utc(now) > _naive_utc(bid_deadline):
        raise bad_request("BID_DEADLINE_PASSED", "The bidding deadline for this lot has passed.")

    bid_id = str(uuid4())
    bid_doc = {
        "bid_id": bid_id,
        "lot_id": lot_id,
        "recycler_id": recycler_profile["license_id"],
        "amount": Decimal128(amount),
        "status": "PLACED",
        "placed_at": _naive_utc(now),
        "accepted_at": None,
        "created_at": _naive_utc(now),
        "updated_at": _naive_utc(now),
    }
    await bids_repo.insert_bid(bid_doc)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="BID_PLACED",
        entity_type="bid",
        entity_id=bid_id,
        details={"lot_id": lot_id, "amount": str(amount)},
    )

    response = _to_bid_response(bid_doc)
    await idempotency.store_response(current_user["user_id"], idempotency_key, PLACE_BID_IDEMPOTENCY_SCOPE, response)
    return response


async def cancel_bid(*, current_user: dict, bid_id: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, CANCEL_BID_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    recycler_profile = await recyclers_service.require_approved_recycler(current_user)

    bid = await bids_repo.find_by_bid_id(bid_id)
    if bid is None:
        raise not_found("BID_NOT_FOUND", "No bid exists with this bid_id.")
    if bid["recycler_id"] != recycler_profile["license_id"]:
        raise forbidden("NOT_BID_OWNER", "You do not have access to this bid.")
    if bid["status"] != "PLACED":
        raise bad_request(
            "BID_NOT_CANCELLABLE", f"Bid is in status {bid['status']}, not eligible for cancellation."
        )

    new_status = bid_states.transition("PLACED", "CANCELLED")
    await bids_repo.update_status(bid_id, new_status)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="BID_CANCELLED",
        entity_type="bid",
        entity_id=bid_id,
        details={"lot_id": bid["lot_id"]},
    )

    response = _to_bid_response({**bid, "status": new_status})
    await idempotency.store_response(current_user["user_id"], idempotency_key, CANCEL_BID_IDEMPOTENCY_SCOPE, response)
    return response


async def list_my_bids(current_user: dict) -> list[dict]:
    recycler_profile = await recyclers_service.require_approved_recycler(current_user)
    docs = await bids_repo.list_by_recycler(recycler_profile["license_id"])
    return [_to_bid_response(d) for d in docs]


async def list_bids_for_lot(*, current_user: dict, lot_id: str) -> list[dict]:
    """Lot-owner-only — the RRR centre that built the lot, or the
    collector it was auto-created for — needed to actually choose which
    bid to accept."""
    lot = await lots_repo.find_by_lot_id(lot_id)
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists with this lot_id.")
    await _require_lot_owner(current_user, lot)
    docs = await bids_repo.list_by_lot(lot_id)
    return [_to_bid_response(d) for d in docs]


async def accept_bid(*, current_user: dict, bid_id: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, ACCEPT_BID_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    bid = await bids_repo.find_by_bid_id(bid_id)
    if bid is None:
        raise not_found("BID_NOT_FOUND", "No bid exists with this bid_id.")

    lot = await lots_repo.find_by_lot_id(bid["lot_id"])
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists for this bid.")
    await _require_lot_owner(current_user, lot)
    if bid["status"] != "PLACED":
        raise bad_request("BID_NOT_ACCEPTABLE", f"Bid is in status {bid['status']}, not eligible for acceptance.")
    if lot["status"] != "LISTED_FOR_BIDDING":
        raise bad_request(
            "LOT_NOT_LISTED_FOR_BIDDING", f"Lot is in status {lot['status']}, not eligible for bid acceptance."
        )

    new_bid_status = bid_states.transition("PLACED", "ACCEPTED")
    now = _naive_utc(datetime.now(timezone.utc))

    # This update_one is the actual race guarantee: the partial unique
    # index on bids.lot_id (status=ACCEPTED only — see app/db/mongo.py)
    # rejects a second concurrent acceptance for the same lot at the
    # database level, regardless of which recycler's bid or which
    # request reaches Mongo first. The pre-checks above are just a
    # cleaner error on the common sequential path, same pattern as every
    # other DB-level race guard in this codebase (duplicate handover,
    # ward-already-has-RRR, etc.).
    try:
        await bids_repo.update_status(bid_id, new_bid_status, accepted_at=now)
    except DuplicateKeyError as exc:
        raise conflict(
            "LOT_ALREADY_ACCEPTED", "Another bid has already been accepted for this lot."
        ) from exc

    new_lot_status = lot_states.transition("LISTED_FOR_BIDDING", "BID_SELECTED")
    await lots_repo.update_status(lot["lot_id"], new_lot_status)

    new_item_status = item_transition("LISTED_FOR_BIDDING", "BID_SELECTED")
    for item_id in lot["item_ids"]:
        await submissions_repo.update_status(item_id, new_item_status)

    # Sibling rejection (architecture: "PLACED -> REJECTED, implicit, when
    # a sibling bid is ACCEPTED"). Never touches CANCELLED bids.
    siblings = await bids_repo.list_by_lot(lot["lot_id"])
    for sibling in siblings:
        if sibling["bid_id"] == bid_id or sibling["status"] != "PLACED":
            continue
        sibling_new_status = bid_states.transition("PLACED", "REJECTED")
        await bids_repo.update_status(sibling["bid_id"], sibling_new_status)
        await audit.record(
            actor_id=current_user["user_id"],
            actor_role=current_user["role"],
            action="BID_SIBLING_REJECTED",
            entity_type="bid",
            entity_id=sibling["bid_id"],
            details={"lot_id": lot["lot_id"], "accepted_bid_id": bid_id},
        )
        # recycler_id on a bid is the recycler's license_id, which is also
        # their login username by construction (see recyclers/service.py's
        # register()) — this resolves it to the user_id create_notification
        # needs, with no new lookup field required anywhere.
        sibling_user = await users_repo.find_by_username(sibling["recycler_id"])
        if sibling_user is not None:
            await notifications_service.create_notification(
                user_id=sibling_user["user_id"],
                event_key=f"bid:{sibling['bid_id']}:rejected",
                notification_type=notifications_service.BID_REJECTED,
                title_key="Bid not approved",
                message_key="Your bid was not approved for this lot.",
                related_entity_type="bid",
                related_entity_id=sibling["bid_id"],
                metadata={"lot_id": lot["lot_id"]},
            )

    winner_user = await users_repo.find_by_username(bid["recycler_id"])
    if winner_user is not None:
        await notifications_service.create_notification(
            user_id=winner_user["user_id"],
            event_key=f"bid:{bid_id}:accepted",
            notification_type=notifications_service.BID_ACCEPTED,
            title_key="Bid approved",
            message_key="Your bid was approved. You have been selected for this lot.",
            related_entity_type="bid",
            related_entity_id=bid_id,
            metadata={"lot_id": lot["lot_id"]},
        )

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="BID_ACCEPTED",
        entity_type="bid",
        entity_id=bid_id,
        details={"lot_id": lot["lot_id"], "amount": _amount_to_str(bid["amount"])},
    )

    response = _to_bid_response({**bid, "status": new_bid_status, "accepted_at": now})
    await idempotency.store_response(current_user["user_id"], idempotency_key, ACCEPT_BID_IDEMPOTENCY_SCOPE, response)
    return response


async def cancel_acceptance(*, current_user: dict, bid_id: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, CANCEL_ACCEPTANCE_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    bid = await bids_repo.find_by_bid_id(bid_id)
    if bid is None:
        raise not_found("BID_NOT_FOUND", "No bid exists with this bid_id.")

    lot = await lots_repo.find_by_lot_id(bid["lot_id"])
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists for this bid.")
    await _require_lot_owner(current_user, lot)
    if bid["status"] != "ACCEPTED":
        raise bad_request(
            "BID_NOT_CANCELLABLE", f"Bid is in status {bid['status']}, not an active acceptance to cancel."
        )

    accepted_at = bid.get("accepted_at")
    if accepted_at is not None:
        elapsed = _naive_utc(datetime.now(timezone.utc)) - _naive_utc(accepted_at)
        if elapsed > timedelta(hours=settings.bid_acceptance_cancel_window_hours):
            raise bad_request(
                "ACCEPTANCE_CANCEL_WINDOW_EXPIRED",
                f"This bid acceptance can no longer be cancelled "
                f"(past the {settings.bid_acceptance_cancel_window_hours}h window).",
            )
    # "...and before payment" (architecture Section 6.2), now enforced for
    # real (Phase 9): the lot's OWN current status is checked, not assumed.
    # A bid stays ACCEPTED throughout logistics booking/collection/payment
    # (bid_states.py has no transition off ACCEPTED except to CANCELLED) —
    # only the lot/item statuses advance — so once logistics has been
    # booked (lot no longer BID_SELECTED), cancellation is no longer
    # possible; this also structurally covers "before payment", since
    # payment can only happen after logistics. Found and fixed as a real
    # bug during Phase 9: the code previously hardcoded the lot's "from"
    # state as BID_SELECTED unconditionally, which was harmless while
    # nothing could move a lot past BID_SELECTED (Phase 6) but would have
    # silently reverted an already-LOGISTICS_BOOKED/SOLD lot back to
    # LISTED_FOR_BIDDING once Phase 9 added further lot progression.
    if lot["status"] != "BID_SELECTED":
        raise bad_request(
            "LOT_NOT_BID_SELECTED",
            f"Lot is in status {lot['status']}; acceptance can no longer be cancelled once logistics has begun.",
        )

    new_bid_status = bid_states.transition("ACCEPTED", "CANCELLED")
    await bids_repo.update_status(bid_id, new_bid_status)

    new_lot_status = lot_states.transition(lot["status"], "LISTED_FOR_BIDDING")
    await lots_repo.update_status(lot["lot_id"], new_lot_status)

    new_item_status = item_transition("BID_SELECTED", "LISTED_FOR_BIDDING")
    for item_id in lot["item_ids"]:
        await submissions_repo.update_status(item_id, new_item_status)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="BID_ACCEPTANCE_CANCELLED",
        entity_type="bid",
        entity_id=bid_id,
        details={"lot_id": lot["lot_id"]},
    )

    response = _to_bid_response({**bid, "status": new_bid_status})
    await idempotency.store_response(current_user["user_id"], idempotency_key, CANCEL_ACCEPTANCE_IDEMPOTENCY_SCOPE, response)
    return response


async def list_all_for_admin(status: str | None = None) -> list[dict]:
    """Admin oversight (Phase 7): every bid, every recycler/lot."""
    docs = await bids_repo.list_all(status=status)
    return [_to_bid_response(d) for d in docs]

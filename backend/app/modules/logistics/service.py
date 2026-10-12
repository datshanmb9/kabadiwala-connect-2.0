"""
Logistics booking — the Recycler's two-step progression from an accepted
bid to a collection-ready lot (architecture Section 10/11): book a
pickup slot (BID_SELECTED -> LOGISTICS_BOOKED), then confirm the
recycler has reached the collection stage (LOGISTICS_BOOKED ->
READY_FOR_COLLECTION). Both steps are the Recycler's own action — the
permission matrix has no other role for logistics. Drives TWO state
machines in parallel per write, same pattern as lots/service.py and
bids/service.py: the lot's own status and each contained item's status.
"""
from datetime import datetime, timezone
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from app.core import audit, idempotency
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.db.repositories import bids_repo, logistics_repo, lots_repo, submissions_repo
from app.modules.recyclers import service as recyclers_service
from app.state_machines import lot_states
from app.state_machines.ewaste_states import transition as item_transition

BOOK_IDEMPOTENCY_SCOPE = "logistics_book"
CONFIRM_IDEMPOTENCY_SCOPE = "logistics_confirm"


def _naive_utc(dt: datetime) -> datetime:
    """Same normalization used throughout this codebase since Phase 2."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _to_response(doc: dict) -> dict:
    return {
        "booking_id": doc["booking_id"],
        "lot_id": doc["lot_id"],
        "recycler_id": doc["recycler_id"],
        "slot_time": doc["slot_time"],
        "status": doc["status"],
    }


async def _require_own_accepted_bid(recycler_profile: dict, lot_id: str) -> dict:
    accepted_bid = await bids_repo.find_accepted_bid_for_lot(lot_id)
    if accepted_bid is None or accepted_bid["recycler_id"] != recycler_profile["license_id"]:
        raise forbidden("NOT_ACCEPTED_BID_OWNER", "You do not have an accepted bid on this lot.")
    return accepted_bid


async def book_logistics(*, current_user: dict, lot_id: str, slot_time: datetime, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, BOOK_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    recycler_profile = await recyclers_service.require_approved_recycler(current_user)

    lot = await lots_repo.find_by_lot_id(lot_id)
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists with this lot_id.")

    await _require_own_accepted_bid(recycler_profile, lot_id)

    if lot["status"] != "BID_SELECTED":
        raise bad_request(
            "LOT_NOT_BID_SELECTED", f"Lot is in status {lot['status']}, not eligible for booking logistics."
        )

    new_lot_status = lot_states.transition("BID_SELECTED", "LOGISTICS_BOOKED")
    new_item_status = item_transition("BID_SELECTED", "LOGISTICS_BOOKED")

    booking_id = str(uuid4())
    now = _naive_utc(datetime.now(timezone.utc))
    booking_doc = {
        "booking_id": booking_id,
        "lot_id": lot_id,
        "recycler_id": recycler_profile["license_id"],
        "slot_time": _naive_utc(slot_time),
        "status": "BOOKED",
        "created_at": now,
        "updated_at": now,
    }
    try:
        await logistics_repo.insert_booking(booking_doc)
    except DuplicateKeyError as exc:
        raise conflict("LOT_ALREADY_HAS_BOOKING", "A logistics booking already exists for this lot.") from exc

    await lots_repo.update_status(lot_id, new_lot_status)
    for item_id in lot["item_ids"]:
        await submissions_repo.update_status(item_id, new_item_status)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="LOGISTICS_BOOKED",
        entity_type="lot",
        entity_id=lot_id,
        details={"booking_id": booking_id, "slot_time": slot_time.isoformat()},
    )

    response = _to_response(booking_doc)
    await idempotency.store_response(current_user["user_id"], idempotency_key, BOOK_IDEMPOTENCY_SCOPE, response)
    return response


async def get_booking_for_lot(*, current_user: dict, lot_id: str) -> dict | None:
    """Recycler-own lookup — lets the UI find an already-booked lot's
    booking_id without needing to remember it across page loads/sessions."""
    recycler_profile = await recyclers_service.require_approved_recycler(current_user)
    await _require_own_accepted_bid(recycler_profile, lot_id)
    booking = await logistics_repo.find_by_lot_id(lot_id)
    return _to_response(booking) if booking else None


async def confirm_collection(*, current_user: dict, booking_id: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, CONFIRM_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    recycler_profile = await recyclers_service.require_approved_recycler(current_user)

    booking = await logistics_repo.find_by_booking_id(booking_id)
    if booking is None:
        raise not_found("BOOKING_NOT_FOUND", "No logistics booking exists with this booking_id.")
    if booking["recycler_id"] != recycler_profile["license_id"]:
        raise forbidden("NOT_BOOKING_OWNER", "You do not have access to this booking.")

    lot = await lots_repo.find_by_lot_id(booking["lot_id"])
    if lot is None:
        raise not_found("LOT_NOT_FOUND", "No lot exists for this booking.")
    if lot["status"] != "LOGISTICS_BOOKED":
        raise bad_request(
            "LOT_NOT_LOGISTICS_BOOKED",
            f"Lot is in status {lot['status']}, not eligible for collection confirmation.",
        )

    new_lot_status = lot_states.transition("LOGISTICS_BOOKED", "READY_FOR_COLLECTION")
    new_item_status = item_transition("LOGISTICS_BOOKED", "READY_FOR_COLLECTION")
    new_booking_status = "COLLECTED"

    await logistics_repo.update_status(booking_id, new_booking_status)
    await lots_repo.update_status(lot["lot_id"], new_lot_status)
    for item_id in lot["item_ids"]:
        await submissions_repo.update_status(item_id, new_item_status)

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="LOGISTICS_COLLECTION_CONFIRMED",
        entity_type="lot",
        entity_id=lot["lot_id"],
        details={"booking_id": booking_id},
    )

    response = {
        "booking_id": booking_id,
        "lot_id": lot["lot_id"],
        "recycler_id": booking["recycler_id"],
        "slot_time": booking["slot_time"],
        "status": new_booking_status,
    }
    await idempotency.store_response(current_user["user_id"], idempotency_key, CONFIRM_IDEMPOTENCY_SCOPE, response)
    return response

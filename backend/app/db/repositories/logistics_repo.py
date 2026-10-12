"""
Pure data access for the `logistics_bookings` collection. No business
rules here — that lives in app/modules/logistics/service.py.
"""
from typing import Any

from app.db.mongo import get_db


async def insert_booking(booking_doc: dict[str, Any]) -> None:
    await get_db().logistics_bookings.insert_one(booking_doc)


async def find_by_lot_id(lot_id: str) -> dict[str, Any] | None:
    return await get_db().logistics_bookings.find_one({"lot_id": lot_id})


async def find_by_booking_id(booking_id: str) -> dict[str, Any] | None:
    return await get_db().logistics_bookings.find_one({"booking_id": booking_id})


async def update_status(booking_id: str, new_status: str) -> None:
    from datetime import datetime, timezone

    await get_db().logistics_bookings.update_one(
        {"booking_id": booking_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
    )

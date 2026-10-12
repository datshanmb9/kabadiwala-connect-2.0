from datetime import datetime

from pydantic import BaseModel


class LogisticsBookRequest(BaseModel):
    slot_time: datetime


class LogisticsBookingResponse(BaseModel):
    booking_id: str
    lot_id: str
    recycler_id: str
    slot_time: datetime
    status: str

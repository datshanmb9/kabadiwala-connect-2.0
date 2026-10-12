from datetime import datetime

from pydantic import BaseModel


class BidPlaceRequest(BaseModel):
    lot_id: str
    # A decimal string, e.g. "1250.50" — never a float over the wire, so
    # the client can't introduce binary-float rounding before the server
    # even sees it. Parsed to Decimal, stored as Decimal128, server-side.
    amount: str


class BidResponse(BaseModel):
    bid_id: str
    lot_id: str
    recycler_id: str
    amount: str
    status: str
    placed_at: datetime
    accepted_at: datetime | None = None

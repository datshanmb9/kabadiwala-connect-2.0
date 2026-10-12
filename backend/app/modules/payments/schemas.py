from datetime import datetime

from pydantic import BaseModel


class PaymentResponse(BaseModel):
    payment_id: str
    lot_id: str
    recycler_id: str
    amount: str
    status: str  # "SUCCEEDED" or "FAILED"
    gateway: str
    gateway_reference: str | None = None
    created_at: datetime

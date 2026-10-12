from datetime import datetime

from pydantic import BaseModel

from app.modules.pricing.schemas import LotPriceEstimate


class LotCreateRequest(BaseModel):
    category: str
    submission_ids: list[str]


class LotResponse(BaseModel):
    lot_id: str
    # None for a lot auto-created from a collector's own handover (no RRR
    # centre involved) — see owner_collector_id below.
    rrr_id: str | None = None
    # New, additive field: set instead of rrr_id when this lot was
    # auto-created from a collector's own confirmed handover rather than
    # built by an RRR centre. Exactly one of rrr_id/owner_collector_id is
    # set on any given lot.
    owner_collector_id: str | None = None
    ward_id: str
    category: str
    item_ids: list[str]
    status: str
    bid_deadline: datetime | None = None
    total_weight_kg: float | None = None
    item_details: list[dict] = []
    # Lot-level view of the items' stored ML estimates (filled on lot
    # detail reads only; None when any item has no estimate).
    price_estimate: LotPriceEstimate | None = None

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PricePredictionRequest(BaseModel):
    product_type: str = Field(min_length=1, max_length=100)
    condition: str = Field(min_length=1, max_length=50)
    quantity: int = Field(gt=0, le=1_000_000)
    total_weight_kg: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)
    location: str = Field(min_length=1, max_length=200)


class PricePredictionResponse(BaseModel):
    predicted_price: float


class PriceEstimateRequest(BaseModel):
    product_type: str = Field(min_length=1, max_length=100)
    condition: str = Field(min_length=1, max_length=50)
    total_weight_kg: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)
    location: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, gt=0, le=1_000_000)


class PriceEstimate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    predicted_price_per_kg: float
    min_price: float
    max_price: float
    estimated_total_value: float
    # Total range = min_price/max_price x weight_kg (see
    # pricing.service.estimated_total_range). Optional so estimates stored
    # before these fields existed still validate.
    estimated_total_min: float | None = None
    estimated_total_max: float | None = None
    trend: str | None = None
    product_type: str
    condition: str
    weight_kg: float
    is_estimate: bool = True
    model_version: str | None = None
    estimated_at: datetime


class PriceEstimateResponse(PriceEstimate):
    pass


class LotPriceEstimate(BaseModel):
    """Lot-level view of the stored per-submission ML estimates, totals
    based on the lot's actual collected weight."""

    model_config = ConfigDict(protected_namespaces=())

    predicted_price_per_kg: float | None = None
    min_price: float
    max_price: float
    weight_kg: float
    estimated_total_min: float
    estimated_total_max: float
    is_estimate: bool = True
    model_version: str | None = None
    estimated_at: datetime | None = None


class PriceTrendPoint(BaseModel):
    date: date
    price_per_kg: float
    sales: int  # accepted sales averaged into this day's point


class PriceTrendResponse(BaseModel):
    """Historical INR/kg for an item from real accepted sales on the
    platform (see pricing.service.price_trend for the exact method)."""

    item: str
    ward_id: str | None = None
    scope: Literal["ward", "all_wards"]
    unit: str = "INR/kg"
    source: str = "accepted_bids"
    window_days: int
    min_points: int
    points: list[PriceTrendPoint]
    trend: Literal["increasing", "decreasing", "stable", "insufficient_data"]
    change_percent: float | None = None
    latest_price_per_kg: float | None = None
    latest_date: date | None = None

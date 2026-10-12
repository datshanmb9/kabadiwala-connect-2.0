from datetime import datetime

from pydantic import BaseModel

from app.modules.pricing.schemas import PriceEstimate


class SubmissionCreateRequest(BaseModel):
    ward_id: str
    photo_file_id: str
    category: str | None = None
    condition: str | None = None
    approximate_weight_kg: float | None = None
    price_estimate: PriceEstimate | None = None
    # No range/null constraints here on purpose: an out-of-range or missing
    # coordinate must reach the service layer's geo checks, not be rejected
    # upfront by pydantic with a generic 422 that bypasses the structured
    # {success, error_code, message} contract.
    home_lat: float | None
    home_lng: float | None
    home_ts: datetime | None = None


class SubmissionResponse(BaseModel):
    submission_id: str
    status: str
    assigned_collector_id: str | None = None


class SubmissionDetailResponse(BaseModel):
    submission_id: str
    home_user_id: str
    ward_id: str
    status: str
    home_lat: float | None
    home_lng: float | None
    home_ts: datetime
    photo_file_id: str | None = None
    category: str | None = None
    condition: str | None = None
    approximate_weight_kg: float | None = None
    actual_weight_kg: float | None = None
    assigned_collector_id: str | None = None
    collector_lat: float | None = None
    collector_lng: float | None = None
    collection_ts: datetime | None = None
    ai_classification: dict | None = None
    price_estimate: PriceEstimate | None = None
    lot_id: str | None = None


class PhotoUploadResponse(BaseModel):
    photo_file_id: str


class CollectorActionResponse(BaseModel):
    submission_id: str
    status: str
    assigned_collector_id: str | None = None


class HandoverRequest(BaseModel):
    photo_file_id: str
    collector_lat: float | None = None
    collector_lng: float | None = None
    collector_ts: datetime | None = None
    actual_weight_kg: float | None = None


class HandoverResponse(BaseModel):
    submission_id: str
    status: str
    verification_result: str
    distance_m: float | None = None
    reasons: list[str] = []
    actual_weight_kg: float | None = None
    # Set only when the handover was VERIFIED: the auto-created, published
    # lot this item now belongs to (see auto_progress_to_listed_lot).
    lot_id: str | None = None
    lot_status: str | None = None


class ReceiveResponse(BaseModel):
    submission_id: str
    status: str


class ClassifyRequest(BaseModel):
    category: str


class ClassifyResponse(BaseModel):
    submission_id: str
    status: str
    category: str

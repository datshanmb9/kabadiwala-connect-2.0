from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_role
from app.modules.pricing import service
from app.modules.pricing.schemas import (
    PriceEstimateRequest,
    PriceEstimateResponse,
    PricePredictionRequest,
    PricePredictionResponse,
    PriceTrendResponse,
)


router = APIRouter(prefix="/api/v1/pricing", tags=["pricing"])


@router.post("/predict", response_model=PricePredictionResponse)
async def predict_price_route(
    body: PricePredictionRequest,
    _current_user: dict = Depends(require_role("RRR_CENTER")),
):
    predicted_price = service.predict_price(
        product_type=body.product_type,
        condition=body.condition,
        quantity=body.quantity,
        total_weight_kg=body.total_weight_kg,
        location=body.location,
    )
    return PricePredictionResponse(predicted_price=predicted_price)


@router.post("/estimate", response_model=PriceEstimateResponse)
async def estimate_price_route(
    body: PriceEstimateRequest,
    current_user: dict = Depends(require_role("HOME_USER")),
):
    del current_user
    estimate = service.estimate_price(
        product_type=body.product_type,
        condition=body.condition,
        quantity=body.quantity,
        total_weight_kg=body.total_weight_kg,
        location=body.location,
    )
    return PriceEstimateResponse(**estimate)


@router.get("/trend", response_model=PriceTrendResponse)
async def price_trend_route(
    item: str = Query(min_length=1, max_length=100),
    ward_id: str | None = Query(default=None, max_length=50),
    _current_user: dict = Depends(require_role("HOME_USER", "COLLECTOR")),
):
    """Historical price trend from real accepted sales — shared by the Home
    User and Collector apps so both get identical results."""
    return PriceTrendResponse(**await service.price_trend(item=item, ward_id=ward_id))

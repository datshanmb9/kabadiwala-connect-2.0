
from ai.pricing.price_ml.src.predict import predict_price as _predict_price_ml


def predict_collector_price(
    product_type: str,
    condition: str,
    quantity: int,
    total_weight_kg: float,
    location: str,
) -> float:
    result = _predict_price_ml(
        material=product_type,
        condition=condition,
        quantity=quantity,
        weight_kg=total_weight_kg,
        location=location,
    )

    return round(result["predicted_price_per_kg"], 2)

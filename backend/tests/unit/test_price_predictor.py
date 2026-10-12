"""Exercises the real price_ml model artifact — no mocking of the predictor.

Guards against the class of bug that mocked service/API tests cannot catch:
a missing model file, a broken pickle/module path, or a package that isn't
actually installed in the environment (all unhandled-exception 500s in
production, surfaced to the mobile app as "An unexpected error occurred").
"""
import math

import pytest

from ai.pricing.price_predictor import predict_collector_price


@pytest.mark.parametrize(
    ("product_type", "condition", "quantity", "total_weight_kg", "location"),
    [
        ("Laptop", "Good", 1, 4.5, "Bengaluru"),
        ("Mobile Phone", "Damaged", 2, 0.4, "WARD-1"),
        ("Aluminium", "Used", 5, 22.4, "Pune"),
        # A material/location the model never saw in training — the
        # OneHotEncoder(handle_unknown="ignore") path must not raise.
        ("Unknown Gadget", "Like New", 1, 1.0, "Nowhere City"),
    ],
)
def test_predict_collector_price_returns_finite_positive_value(
    product_type, condition, quantity, total_weight_kg, location
):
    price = predict_collector_price(
        product_type=product_type,
        condition=condition,
        quantity=quantity,
        total_weight_kg=total_weight_kg,
        location=location,
    )

    assert isinstance(price, float)
    assert math.isfinite(price)
    assert price >= 0

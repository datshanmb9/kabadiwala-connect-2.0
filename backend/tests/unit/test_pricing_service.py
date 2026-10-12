import pytest

from ai.pricing import price_predictor
from app.core.errors import AppError
from app.modules.pricing import service


def test_predict_price_forwards_model_features_and_returns_prediction(monkeypatch):
    received = {}

    def fake_predict_collector_price(**features):
        received.update(features)
        return 371.72

    monkeypatch.setattr(price_predictor, "predict_collector_price", fake_predict_collector_price)

    result = service.predict_price(
        product_type=" metal-scrap ",
        condition=" good ",
        quantity=2,
        total_weight_kg=5.0,
        location=" Bengaluru ",
    )

    assert result == 371.72
    assert received == {
        "product_type": "metal-scrap",
        "condition": "good",
        "quantity": 2,
        "total_weight_kg": 5.0,
        "location": "Bengaluru",
    }


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    [
        ("product_type", " ", "PRODUCT_TYPE_REQUIRED"),
        ("condition", " ", "CONDITION_REQUIRED"),
        ("location", " ", "LOCATION_REQUIRED"),
        ("quantity", 0, "INVALID_QUANTITY"),
        ("total_weight_kg", 0, "INVALID_TOTAL_WEIGHT"),
    ],
)
def test_predict_price_rejects_invalid_values(field, value, error_code):
    features = {
        "product_type": "metal-scrap",
        "condition": "good",
        "quantity": 1,
        "total_weight_kg": 1.0,
        "location": "Bengaluru",
    }
    features[field] = value

    with pytest.raises(AppError) as error:
        service.predict_price(**features)

    assert error.value.error_code == error_code


# --- Estimated total range (regression: total must be per-kg range x weight) ---


def test_estimated_total_range_is_per_kg_range_times_weight():
    min_price, max_price, weight_kg = 98.21, 120.03, 0.40

    assert service.estimated_total_range(min_price, max_price, weight_kg) == (39.28, 48.01)


def test_estimate_price_total_range_derives_from_rounded_per_kg_range(monkeypatch):
    # 109.12 -> +/-10% band -> 98.208 / 120.032 -> rounded per-kg 98.21 / 120.03
    monkeypatch.setattr(service, "predict_price", lambda **features: 109.12)

    estimate = service.estimate_price(
        product_type="e-waste-small-appliances",
        condition="Used",
        quantity=1,
        total_weight_kg=0.40,
        location="WARD-1",
    )

    assert estimate["min_price"] == 98.21
    assert estimate["max_price"] == 120.03
    assert estimate["weight_kg"] == 0.40
    assert estimate["estimated_total_min"] == 39.28
    assert estimate["estimated_total_max"] == 48.01
    # The ML point prediction path itself is unchanged.
    assert estimate["predicted_price_per_kg"] == 109.12
    assert estimate["estimated_total_value"] == round(109.12 * 0.40, 2)


def test_with_estimated_totals_backfills_stored_estimate_and_uses_given_weight():
    stored = {"min_price": 98.21, "max_price": 120.03, "weight_kg": 0.40, "estimated_total_value": 43.65}

    assert service.with_estimated_totals(stored)["estimated_total_min"] == 39.28
    assert service.with_estimated_totals(stored)["estimated_total_max"] == 48.01

    collected = service.with_estimated_totals(stored, 0.10)
    assert collected["weight_kg"] == 0.10
    assert (collected["estimated_total_min"], collected["estimated_total_max"]) == (9.82, 12.0)
    assert "estimated_total_min" not in stored  # input not mutated
    assert service.with_estimated_totals(None) is None


def test_lot_price_estimate_single_item_keeps_per_kg_range():
    estimate = {"predicted_price_per_kg": 109.12, "min_price": 98.21, "max_price": 120.03, "weight_kg": 0.40}

    lot = service.lot_price_estimate([(estimate, 0.40)])

    assert (lot["min_price"], lot["max_price"]) == (98.21, 120.03)
    assert lot["weight_kg"] == 0.40
    assert (lot["estimated_total_min"], lot["estimated_total_max"]) == (39.28, 48.01)


def test_lot_price_estimate_sums_item_totals_and_requires_every_item_priced():
    a = {"predicted_price_per_kg": 100.0, "min_price": 90.0, "max_price": 110.0, "weight_kg": 1.0}
    b = {"predicted_price_per_kg": 200.0, "min_price": 180.0, "max_price": 220.0, "weight_kg": 1.0}

    lot = service.lot_price_estimate([(a, 1.0), (b, 3.0)])

    assert (lot["estimated_total_min"], lot["estimated_total_max"]) == (630.0, 770.0)
    assert (lot["min_price"], lot["max_price"]) == (157.5, 192.5)
    assert lot["weight_kg"] == 4.0
    assert service.lot_price_estimate([(a, 1.0), (None, 2.0)]) is None
    assert service.lot_price_estimate([]) is None

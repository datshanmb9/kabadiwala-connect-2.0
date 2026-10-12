import pytest

from app.modules.pricing import service as pricing_service


async def _login(client, username, password):
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_rrr_can_request_read_only_price_prediction(client, seeded_rrr_center, monkeypatch):
    monkeypatch.setattr(pricing_service, "predict_price", lambda **features: 371.72)
    token = await _login(client, "rrr-centre-1", "rrrpass123")

    response = await client.post(
        "/api/v1/pricing/predict",
        json={
            "product_type": "metal-scrap",
            "condition": "good",
            "quantity": 2,
            "total_weight_kg": 5.0,
            "location": "Bengaluru",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"predicted_price": 371.72}


@pytest.mark.asyncio
async def test_pricing_requires_authentication(client):
    response = await client.post(
        "/api/v1/pricing/predict",
        json={
            "product_type": "metal-scrap",
            "condition": "good",
            "quantity": 1,
            "total_weight_kg": 1.0,
            "location": "Bengaluru",
        },
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_pricing_rejects_invalid_request_values(client, seeded_rrr_center):
    token = await _login(client, "rrr-centre-1", "rrrpass123")

    response = await client.post(
        "/api/v1/pricing/predict",
        json={
            "product_type": "metal-scrap",
            "condition": "good",
            "quantity": 0,
            "total_weight_kg": 1.0,
            "location": "Bengaluru",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_home_user_can_request_price_estimate(client, seeded_home_user, monkeypatch):
    monkeypatch.setattr(pricing_service, "predict_price", lambda **features: 420.0)
    token = await _login(client, "home-user-1", "homepass123")

    response = await client.post(
        "/api/v1/pricing/estimate",
        json={
            "product_type": "Smartphone",
            "condition": "Used",
            "total_weight_kg": 2.5,
            "location": "WARD-1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["predicted_price_per_kg"] == 420.0
    assert body["min_price"] == 378.0
    assert body["max_price"] == 462.0
    assert body["estimated_total_value"] == 1050.0
    assert body["trend"] is None
    assert body["product_type"] == "Smartphone"
    assert body["condition"] == "Used"
    assert body["weight_kg"] == 2.5
    assert body["is_estimate"] is True


@pytest.mark.asyncio
async def test_home_user_price_estimate_uses_real_price_ml_model(client, seeded_home_user):
    """End-to-end through the real price_ml model — nothing mocked.

    Mobile app inputs: material/category, condition, and approximate weight,
    matching what submit_ewaste_screen.dart sends to POST /pricing/estimate.
    """
    token = await _login(client, "home-user-1", "homepass123")

    response = await client.post(
        "/api/v1/pricing/estimate",
        json={
            "product_type": "Laptop",
            "condition": "Good",
            "total_weight_kg": 4.5,
            "location": "WARD-1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["predicted_price_per_kg"], (int, float))
    assert body["predicted_price_per_kg"] > 0
    assert body["min_price"] <= body["predicted_price_per_kg"] <= body["max_price"]
    assert body["estimated_total_value"] > 0
    assert body["product_type"] == "Laptop"
    assert body["condition"] == "Good"
    assert body["weight_kg"] == 4.5
    assert body["is_estimate"] is True


@pytest.mark.asyncio
async def test_rrr_only_prediction_does_not_allow_home_user(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    response = await client.post(
        "/api/v1/pricing/predict",
        json={
            "product_type": "Smartphone",
            "condition": "Used",
            "quantity": 1,
            "total_weight_kg": 2.5,
            "location": "WARD-1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

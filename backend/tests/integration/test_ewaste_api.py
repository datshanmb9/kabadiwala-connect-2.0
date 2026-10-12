import pytest

HOME_LAT = 12.9716
HOME_LNG = 77.5946
# ~15m from HOME_LAT/LNG — within the default 150m tolerance.
NEARBY_LAT = 12.97174
NEARBY_LNG = 77.59474
# Chennai — ~290km away, well outside tolerance.
FAR_LAT = 13.0827
FAR_LNG = 80.2707


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_submission(client, home_token, idem_key="idem-key-1", **overrides):
    body = {
        "ward_id": "WARD-1",
        "photo_file_id": "photo-1",
        "home_lat": HOME_LAT,
        "home_lng": HOME_LNG,
    }
    body.update(overrides)
    return await client.post(
        "/api/v1/ewaste/submissions",
        json=body,
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": idem_key},
    )


@pytest.mark.asyncio
async def test_home_user_can_create_submission(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    resp = await _create_submission(client, token)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "WAITING_FOR_COLLECTION"
    assert "submission_id" in body


@pytest.mark.asyncio
async def test_home_user_submission_retains_category_and_approximate_weight(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    resp = await _create_submission(
        client, token, idem_key="metadata-submit", category="mobile phones", approximate_weight_kg=3.5
    )
    assert resp.status_code == 200
    detail = await client.get(
        f"/api/v1/ewaste/submissions/{resp.json()['submission_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.json()["category"] == "mobile phones"
    assert detail.json()["approximate_weight_kg"] == 3.5


@pytest.mark.asyncio
async def test_home_user_submission_retains_condition_and_price_estimate(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    price_estimate = {
        "predicted_price_per_kg": 420.0,
        "min_price": 378.0,
        "max_price": 462.0,
        "estimated_total_value": 1050.0,
        "trend": None,
        "product_type": "Smartphone",
        "condition": "Used",
        "weight_kg": 2.5,
        "is_estimate": True,
        "model_version": "collector_price_model.joblib",
        "estimated_at": "2026-09-23T00:00:00Z",
    }
    resp = await _create_submission(
        client,
        token,
        idem_key="condition-price-submit",
        category="Smartphone",
        condition="Used",
        approximate_weight_kg=2.5,
        price_estimate=price_estimate,
    )
    assert resp.status_code == 200

    detail = await client.get(
        f"/api/v1/ewaste/submissions/{resp.json()['submission_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = detail.json()
    assert body["condition"] == "Used"
    assert body["price_estimate"]["predicted_price_per_kg"] == 420.0
    assert body["price_estimate"]["estimated_total_value"] == 1050.0


@pytest.mark.asyncio
async def test_submission_rejects_non_positive_approximate_weight(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    resp = await _create_submission(client, token, idem_key="invalid-weight", approximate_weight_kg=0)
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_APPROXIMATE_WEIGHT"


@pytest.mark.asyncio
async def test_submission_requires_idempotency_key_header(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": "p", "home_lat": HOME_LAT, "home_lng": HOME_LNG},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_idempotency_replay_returns_same_submission_no_duplicate(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")

    resp1 = await _create_submission(client, token, idem_key="replay-key")
    resp2 = await _create_submission(client, token, idem_key="replay-key")

    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json()["submission_id"] == resp2.json()["submission_id"]

    list_resp = await client.get("/api/v1/ewaste/submissions", headers={"Authorization": f"Bearer {token}"})
    assert len(list_resp.json()["submissions"]) == 1


@pytest.mark.asyncio
async def test_different_idempotency_keys_create_separate_submissions(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")

    resp1 = await _create_submission(client, token, idem_key="key-a")
    resp2 = await _create_submission(client, token, idem_key="key-b")

    assert resp1.json()["submission_id"] != resp2.json()["submission_id"]


@pytest.mark.asyncio
async def test_non_home_user_cannot_create_submission(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await _create_submission(client, token)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_submission_rejects_unknown_ward(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    resp = await _create_submission(client, token, ward_id="NOPE")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "WARD_NOT_FOUND"


# --- Handover ---------------------------------------------------------


async def _submit_and_login_collector(client, seeded_home_user, seeded_collector, idem_key="submit-1"):
    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(client, home_token, idem_key=idem_key)
    submission_id = submission_resp.json()["submission_id"]
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    return submission_id, collector_token


@pytest.mark.asyncio
async def test_valid_handover_marks_collected(client, seeded_home_user, seeded_collector):
    submission_id, collector_token = await _submit_and_login_collector(client, seeded_home_user, seeded_collector)

    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "handover-photo", "collector_lat": NEARBY_LAT, "collector_lng": NEARBY_LNG},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-key-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "COLLECTED"
    assert body["verification_result"] == "VERIFIED"
    assert body["reasons"] == []


@pytest.mark.asyncio
async def test_collector_accepts_and_completes_collection_with_weight(client, seeded_home_user, seeded_collector):
    submission_id, collector_token = await _submit_and_login_collector(
        client, seeded_home_user, seeded_collector, idem_key="submit-accept"
    )
    accept = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/accept",
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "accept-key-1"},
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "COLLECTOR_ACCEPTED"

    handover = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={
            "photo_file_id": "collection-photo-1",
            "collector_lat": NEARBY_LAT,
            "collector_lng": NEARBY_LNG,
            "actual_weight_kg": 2.75,
        },
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-accepted-1"},
    )
    assert handover.status_code == 200
    assert handover.json()["status"] == "COLLECTED"
    assert handover.json()["actual_weight_kg"] == 2.75

    from app.db.repositories import handovers_repo, submissions_repo

    submission = await submissions_repo.find_by_submission_id(submission_id)
    collection = await handovers_repo.find_by_submission_id(submission_id)
    assert submission["actual_weight_kg"] == 2.75
    assert submission["collection_photo_file_id"] == "collection-photo-1"
    assert collection["photo_file_id"] == "collection-photo-1"


@pytest.mark.asyncio
async def test_two_collectors_cannot_accept_same_submission(client, seeded_home_user, seeded_collector):
    from app.modules.collectors import service as collectors_service

    await collectors_service.create_collector(
        employee_id="EMP-SAME-WARD",
        password="collectorpass1",
        ward_id="WARD-1",
        rrr_id=None,
        assigned_area_radius_m=None,
        actor={"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"},
    )
    home_token = await _login(client, "home-user-1", "homepass123")
    submission_id = (await _create_submission(client, home_token, idem_key="submit-claim-race")).json()["submission_id"]
    first_token = await _login(client, "EMP-001", "collectorpass1")
    second_token = await _login(client, "EMP-SAME-WARD", "collectorpass1")

    first = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/accept",
        headers={"Authorization": f"Bearer {first_token}", "Idempotency-Key": "accept-first"},
    )
    second = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/accept",
        headers={"Authorization": f"Bearer {second_token}", "Idempotency-Key": "accept-second"},
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error_code"] == "SUBMISSION_ALREADY_ASSIGNED"


@pytest.mark.asyncio
async def test_handover_with_invalid_gps_flags_for_review(client, seeded_home_user, seeded_collector):
    submission_id, collector_token = await _submit_and_login_collector(
        client, seeded_home_user, seeded_collector, idem_key="submit-invalid-gps"
    )

    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "handover-photo", "collector_lat": 0.0, "collector_lng": 0.0},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-key-2"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "FLAGGED_FOR_REVIEW"
    assert body["verification_result"] == "FLAGGED"
    assert "INVALID_COLLECTOR_GPS" in body["reasons"]


@pytest.mark.asyncio
async def test_handover_with_excessive_distance_flags_for_review(client, seeded_home_user, seeded_collector):
    submission_id, collector_token = await _submit_and_login_collector(
        client, seeded_home_user, seeded_collector, idem_key="submit-far"
    )

    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "handover-photo", "collector_lat": FAR_LAT, "collector_lng": FAR_LNG},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-key-3"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "FLAGGED_FOR_REVIEW"
    assert "DISTANCE_EXCEEDED" in body["reasons"]
    assert body["distance_m"] > 150.0


@pytest.mark.asyncio
async def test_handover_with_invalid_timestamp_flags_for_review(client, seeded_home_user, seeded_collector):
    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(
        client, home_token, idem_key="submit-ts", home_ts="2026-01-10T12:00:00Z"
    )
    submission_id = submission_resp.json()["submission_id"]
    collector_token = await _login(client, "EMP-001", "collectorpass1")

    # Collector timestamp is BEFORE the home submission timestamp — impossible.
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={
            "photo_file_id": "handover-photo",
            "collector_lat": NEARBY_LAT,
            "collector_lng": NEARBY_LNG,
            "collector_ts": "2026-01-10T11:00:00Z",
        },
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-key-4"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "FLAGGED_FOR_REVIEW"
    assert "TIMESTAMP_BEFORE_SUBMISSION" in body["reasons"]


@pytest.mark.asyncio
async def test_duplicate_handover_rejected(client, seeded_home_user, seeded_collector):
    submission_id, collector_token = await _submit_and_login_collector(
        client, seeded_home_user, seeded_collector, idem_key="submit-dup"
    )
    headers1 = {"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-dup-1"}
    headers2 = {"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-dup-2"}

    resp1 = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p1", "collector_lat": NEARBY_LAT, "collector_lng": NEARBY_LNG},
        headers=headers1,
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p2", "collector_lat": NEARBY_LAT, "collector_lng": NEARBY_LNG},
        headers=headers2,
    )
    assert resp2.status_code == 409
    assert resp2.json()["error_code"] == "DUPLICATE_HANDOVER"


@pytest.mark.asyncio
async def test_handover_idempotency_replay_returns_same_result(client, seeded_home_user, seeded_collector):
    submission_id, collector_token = await _submit_and_login_collector(
        client, seeded_home_user, seeded_collector, idem_key="submit-replay"
    )
    headers = {"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-replay-key"}
    body = {"photo_file_id": "p1", "collector_lat": NEARBY_LAT, "collector_lng": NEARBY_LNG}

    resp1 = await client.post(f"/api/v1/ewaste/submissions/{submission_id}/handover", json=body, headers=headers)
    resp2 = await client.post(f"/api/v1/ewaste/submissions/{submission_id}/handover", json=body, headers=headers)

    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json() == resp2.json()


@pytest.mark.asyncio
async def test_collector_outside_assigned_ward_rejected(client, seeded_home_user, seeded_collector, other_ward):
    from app.modules.collectors import service as collectors_service

    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await collectors_service.create_collector(
        employee_id="EMP-OTHER",
        password="collectorpass1",
        ward_id="WARD-2",
        rrr_id=None,
        assigned_area_radius_m=None,
        actor=admin_actor,
    )

    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(client, home_token, idem_key="submit-other-ward")
    submission_id = submission_resp.json()["submission_id"]

    other_collector_token = await _login(client, "EMP-OTHER", "collectorpass1")
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p1", "collector_lat": NEARBY_LAT, "collector_lng": NEARBY_LNG},
        headers={"Authorization": f"Bearer {other_collector_token}", "Idempotency-Key": "handover-other-ward"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "COLLECTOR_OUTSIDE_ASSIGNED_AREA"


@pytest.mark.asyncio
async def test_non_collector_cannot_handover(client, seeded_home_user):
    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(client, home_token, idem_key="submit-self-handover")
    submission_id = submission_resp.json()["submission_id"]

    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p1", "collector_lat": NEARBY_LAT, "collector_lng": NEARBY_LNG},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "handover-self"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_handover_creates_audit_log_entry(client, seeded_admin, seeded_home_user, seeded_collector):
    submission_id, collector_token = await _submit_and_login_collector(
        client, seeded_home_user, seeded_collector, idem_key="submit-audit"
    )
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p1", "collector_lat": NEARBY_LAT, "collector_lng": NEARBY_LNG},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-audit-key"},
    )

    admin_token = await _login(client, "admin", "admin1234")
    logs_resp = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    actions = [log["action"] for log in logs_resp.json()["logs"]]
    assert "EWASTE_SUBMISSION_CREATED" in actions
    assert "EWASTE_HANDOVER_RECORDED" in actions


@pytest.mark.asyncio
async def test_home_user_cannot_view_another_home_users_submission(client, seeded_home_user, seeded_ward):
    from app.modules.home_users import service as home_users_service

    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(client, home_token, idem_key="submit-privacy")
    submission_id = submission_resp.json()["submission_id"]

    await home_users_service.register(
        username="other-home-user",
        password="otherpass123",
        full_name="Other Home User",
        address="99 Other St",
        ward_id="WARD-1",
        household_lat=HOME_LAT,
        household_lng=HOME_LNG,
        upi_id=None,
    )
    other_token = await _login(client, "other-home-user", "otherpass123")

    resp = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NOT_RESOURCE_OWNER"


@pytest.mark.asyncio
async def test_admin_can_view_any_submission(client, seeded_admin, seeded_home_user):
    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(client, home_token, idem_key="submit-admin-view")
    submission_id = submission_resp.json()["submission_id"]

    admin_token = await _login(client, "admin", "admin1234")
    resp = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["submission_id"] == submission_id


# --- Collector pending queue (Phase 4) ----------------------------------


@pytest.mark.asyncio
async def test_collector_sees_pending_submission_in_own_ward(client, seeded_home_user, seeded_collector):
    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(client, home_token, idem_key="submit-pending-1")
    submission_id = submission_resp.json()["submission_id"]

    collector_token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.get(
        "/api/v1/ewaste/submissions/pending", headers={"Authorization": f"Bearer {collector_token}"}
    )
    assert resp.status_code == 200
    submission_ids = [s["submission_id"] for s in resp.json()["submissions"]]
    assert submission_id in submission_ids


@pytest.mark.asyncio
async def test_pending_queue_is_empty_when_nothing_awaiting_collection(client, seeded_collector):
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.get(
        "/api/v1/ewaste/submissions/pending", headers={"Authorization": f"Bearer {collector_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["submissions"] == []


@pytest.mark.asyncio
async def test_collector_does_not_see_other_wards_pending_submissions(
    client, seeded_home_user, seeded_collector, other_ward
):
    from app.modules.collectors import service as collectors_service

    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await collectors_service.create_collector(
        employee_id="EMP-OTHER-WARD",
        password="collectorpass1",
        ward_id="WARD-2",
        rrr_id=None,
        assigned_area_radius_m=None,
        actor=admin_actor,
    )

    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(client, home_token, idem_key="submit-pending-other-ward")
    submission_id = submission_resp.json()["submission_id"]

    other_ward_collector_token = await _login(client, "EMP-OTHER-WARD", "collectorpass1")
    resp = await client.get(
        "/api/v1/ewaste/submissions/pending", headers={"Authorization": f"Bearer {other_ward_collector_token}"}
    )
    assert resp.status_code == 200
    submission_ids = [s["submission_id"] for s in resp.json()["submissions"]]
    assert submission_id not in submission_ids


@pytest.mark.asyncio
async def test_non_collector_cannot_view_pending_queue(client, seeded_home_user):
    home_token = await _login(client, "home-user-1", "homepass123")
    resp = await client.get(
        "/api/v1/ewaste/submissions/pending", headers={"Authorization": f"Bearer {home_token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_pending_queue_excludes_already_collected_submissions(client, seeded_home_user, seeded_collector):
    home_token = await _login(client, "home-user-1", "homepass123")
    submission_resp = await _create_submission(client, home_token, idem_key="submit-pending-collected")
    submission_id = submission_resp.json()["submission_id"]

    collector_token = await _login(client, "EMP-001", "collectorpass1")
    handover_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": "p1", "collector_lat": NEARBY_LAT, "collector_lng": NEARBY_LNG},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "handover-for-pending-test"},
    )
    assert handover_resp.status_code == 200
    assert handover_resp.json()["status"] == "COLLECTED"

    resp = await client.get(
        "/api/v1/ewaste/submissions/pending", headers={"Authorization": f"Bearer {collector_token}"}
    )
    submission_ids = [s["submission_id"] for s in resp.json()["submissions"]]
    assert submission_id not in submission_ids


# --- RRR Centre: receive + classify (Phase 5) ---------------------------


@pytest.mark.asyncio
async def test_rrr_can_receive_collected_item_in_own_ward(client, seeded_rrr_center, collected_submission):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{collected_submission}/receive",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "receive-key-1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "AT_RRR"


@pytest.mark.asyncio
async def test_pending_rrr_cannot_receive_item(client, pending_rrr_center, collected_submission):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{collected_submission}/receive",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "receive-key-pending"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "RRR_NOT_APPROVED"


@pytest.mark.asyncio
async def test_rrr_cannot_receive_item_outside_own_ward(client, seeded_admin, seeded_rrr_center, other_ward):
    from app.modules.home_users import service as home_users_service
    from app.modules.collectors import service as collectors_service
    from app.modules.ewaste import service as ewaste_service

    home_result = await home_users_service.register(
        username="other-ward-home-user", password="homepass123", full_name="Other", address="x",
        ward_id="WARD-2", household_lat=1.0, household_lng=1.0, upi_id=None,
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    collector_result = await collectors_service.create_collector(
        employee_id="EMP-WARD2", password="collectorpass1", ward_id="WARD-2",
        rrr_id=None, assigned_area_radius_m=None, actor=admin_actor,
    )
    submit_result = await ewaste_service.create_submission(
        current_user=home_result["user"], ward_id="WARD-2", photo_file_id="p",
        home_lat=1.0, home_lng=1.0, home_ts=None, idempotency_key="other-ward-submit",
    )
    await ewaste_service.handover(
        current_user=collector_result["user"], submission_id=submit_result["submission_id"],
        photo_file_id="p", collector_lat=1.0, collector_lng=1.0, collector_ts=None,
        idempotency_key="other-ward-handover",
    )

    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submit_result['submission_id']}/receive",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "receive-other-ward"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "RRR_OUTSIDE_ASSIGNED_WARD"


@pytest.mark.asyncio
async def test_awaiting_receipt_queue_shows_collected_items_in_own_ward(client, seeded_rrr_center, collected_submission):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.get(
        "/api/v1/ewaste/submissions/awaiting-receipt", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    ids = [s["submission_id"] for s in resp.json()["submissions"]]
    assert collected_submission in ids


@pytest.mark.asyncio
async def test_rrr_can_classify_a_received_item(client, seeded_rrr_center, collected_submission):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    await client.post(
        f"/api/v1/ewaste/submissions/{collected_submission}/receive",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "classify-receive-key"},
    )

    resp = await client.post(
        f"/api/v1/ewaste/submissions/{collected_submission}/classify",
        json={"category": "e-waste-small-appliances"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "classify-key-1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "CLASSIFIED"
    assert resp.json()["category"] == "e-waste-small-appliances"


@pytest.mark.asyncio
async def test_cannot_classify_an_item_still_awaiting_receipt(client, seeded_rrr_center, collected_submission):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{collected_submission}/classify",
        json={"category": "x"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "classify-too-early"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "SUBMISSION_NOT_AT_RRR"


@pytest.mark.asyncio
async def test_awaiting_classification_and_classified_queues_update_correctly(
    client, seeded_rrr_center, collected_submission
):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    await client.post(
        f"/api/v1/ewaste/submissions/{collected_submission}/receive",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "queue-receive-key"},
    )

    awaiting_resp = await client.get(
        "/api/v1/ewaste/submissions/awaiting-classification", headers={"Authorization": f"Bearer {token}"}
    )
    assert collected_submission in [s["submission_id"] for s in awaiting_resp.json()["submissions"]]

    await client.post(
        f"/api/v1/ewaste/submissions/{collected_submission}/classify",
        json={"category": "metal-scrap"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "queue-classify-key"},
    )

    classified_resp = await client.get(
        "/api/v1/ewaste/submissions/classified", headers={"Authorization": f"Bearer {token}"}
    )
    assert collected_submission in [s["submission_id"] for s in classified_resp.json()["submissions"]]

    awaiting_resp_after = await client.get(
        "/api/v1/ewaste/submissions/awaiting-classification", headers={"Authorization": f"Bearer {token}"}
    )
    assert collected_submission not in [s["submission_id"] for s in awaiting_resp_after.json()["submissions"]]


@pytest.mark.asyncio
async def test_non_rrr_role_cannot_receive_item(client, seeded_collector, collected_submission):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{collected_submission}/receive",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "non-rrr-receive"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"

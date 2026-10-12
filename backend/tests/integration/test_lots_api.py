import pytest


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _classified_submission(client, rrr_token, *, idem_prefix, category="e-waste-small-appliances"):
    """Drives a fresh submission through create->handover->receive->classify
    via the real services/API, returning its submission_id. Requires the
    seeded_collector fixture (employee_id EMP-001, WARD-1) to already
    exist in this test's db."""
    from app.db.repositories import collectors_repo
    from app.modules.home_users import service as home_users_service
    from app.modules.ewaste import service as ewaste_service

    home_result = await home_users_service.register(
        username=f"{idem_prefix}-home-user", password="homepass123", full_name="x", address="x",
        ward_id="WARD-1", household_lat=12.9716, household_lng=77.5946, upi_id=None,
    )
    collector_profile = await collectors_repo.find_by_employee_id("EMP-001")
    submit_result = await ewaste_service.create_submission(
        current_user=home_result["user"], ward_id="WARD-1", photo_file_id="p",
        home_lat=12.9716, home_lng=77.5946, home_ts=None, idempotency_key=f"{idem_prefix}-submit",
    )
    collector_user = {"user_id": collector_profile["user_id"], "role": "COLLECTOR"}
    await ewaste_service.handover(
        current_user=collector_user, submission_id=submit_result["submission_id"],
        photo_file_id="p", collector_lat=12.97165, collector_lng=77.59465, collector_ts=None,
        actual_weight_kg=2.5,
        idempotency_key=f"{idem_prefix}-handover",
    )

    submission_id = submit_result["submission_id"]
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/receive",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": f"{idem_prefix}-receive"},
    )
    await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/classify",
        json={"category": category},
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": f"{idem_prefix}-classify"},
    )
    return submission_id


@pytest.mark.asyncio
async def test_rrr_can_create_a_lot_from_classified_items(client, seeded_rrr_center, seeded_collector):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    sub_id = await _classified_submission(client, token, idem_prefix="lot-create")

    resp = await client.post(
        "/api/v1/lots",
        json={"category": "e-waste-small-appliances", "submission_ids": [sub_id]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-create-key-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "DRAFT"
    assert body["item_ids"] == [sub_id]
    assert body["rrr_id"] == "RRR-001"
    assert body["total_weight_kg"] == 2.5
    assert body["item_details"][0]["actual_weight_kg"] == 2.5


@pytest.mark.asyncio
async def test_lot_creation_rejects_an_unclassified_item(client, seeded_rrr_center, collected_submission):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        "/api/v1/lots",
        json={"category": "x", "submission_ids": [collected_submission]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-create-unclassified"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "SUBMISSION_NOT_CLASSIFIED"


@pytest.mark.asyncio
async def test_lot_creation_rejects_category_mismatch(client, seeded_rrr_center, seeded_collector):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    sub_id = await _classified_submission(client, token, idem_prefix="lot-mismatch", category="metal-scrap")

    resp = await client.post(
        "/api/v1/lots",
        json={"category": "plastics", "submission_ids": [sub_id]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-create-mismatch"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "SUBMISSION_CATEGORY_MISMATCH"


@pytest.mark.asyncio
async def test_lot_creation_requires_at_least_one_item(client, seeded_rrr_center):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    resp = await client.post(
        "/api/v1/lots",
        json={"category": "x", "submission_ids": []},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-create-empty"},
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "LOT_REQUIRES_AT_LEAST_ONE_ITEM"


@pytest.mark.asyncio
async def test_lot_create_moves_item_out_of_classified_queue(client, seeded_rrr_center, seeded_collector):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    sub_id = await _classified_submission(client, token, idem_prefix="lot-queue")

    await client.post(
        "/api/v1/lots",
        json={"category": "e-waste-small-appliances", "submission_ids": [sub_id]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-queue-create"},
    )

    classified_resp = await client.get(
        "/api/v1/ewaste/submissions/classified", headers={"Authorization": f"Bearer {token}"}
    )
    assert sub_id not in [s["submission_id"] for s in classified_resp.json()["submissions"]]


@pytest.mark.asyncio
async def test_rrr_can_publish_own_draft_lot(client, seeded_admin, seeded_rrr_center, seeded_collector):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    sub_id = await _classified_submission(client, token, idem_prefix="lot-publish")
    create_resp = await client.post(
        "/api/v1/lots",
        json={"category": "e-waste-small-appliances", "submission_ids": [sub_id]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-publish-create"},
    )
    lot_id = create_resp.json()["lot_id"]

    publish_resp = await client.post(
        f"/api/v1/lots/{lot_id}/publish",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-publish-key-1"},
    )
    assert publish_resp.status_code == 200, publish_resp.text
    body = publish_resp.json()
    assert body["status"] == "LISTED_FOR_BIDDING"
    assert body["bid_deadline"] is not None

    # get_submission's allow-list is HOME_USER(own)/GOVERNMENT_ADMIN only
    # (unchanged from Phase 2) — confirm the item's status via admin.
    admin_token = await _login(client, "admin", "admin1234")
    submission_resp = await client.get(
        f"/api/v1/ewaste/submissions/{sub_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert submission_resp.status_code == 200
    assert submission_resp.json()["status"] == "LISTED_FOR_BIDDING"


@pytest.mark.asyncio
async def test_publishing_twice_is_rejected(client, seeded_rrr_center, seeded_collector):
    token = await _login(client, "rrr-centre-1", "rrrpass123")
    sub_id = await _classified_submission(client, token, idem_prefix="lot-double-publish")
    create_resp = await client.post(
        "/api/v1/lots",
        json={"category": "e-waste-small-appliances", "submission_ids": [sub_id]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-double-publish-create"},
    )
    lot_id = create_resp.json()["lot_id"]

    headers1 = {"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-double-publish-1"}
    headers2 = {"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-double-publish-2"}
    resp1 = await client.post(f"/api/v1/lots/{lot_id}/publish", headers=headers1)
    assert resp1.status_code == 200
    resp2 = await client.post(f"/api/v1/lots/{lot_id}/publish", headers=headers2)
    assert resp2.status_code == 400
    assert resp2.json()["error_code"] == "LOT_NOT_DRAFT"


@pytest.mark.asyncio
async def test_lot_list_and_detail_are_owner_scoped(client, seeded_admin, seeded_rrr_center, seeded_collector, other_ward):
    from app.modules.rrr_centres import service as rrr_centres_service

    other_rrr_result = await rrr_centres_service.register(
        username="rrr-centre-2", password="rrrpass123", rrr_id="RRR-002",
        tender_id="TENDER-002", ward_id="WARD-2", licence_doc_ref=None,
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await rrr_centres_service.approve(user_id=other_rrr_result["user"]["user_id"], actor=admin_actor)

    token = await _login(client, "rrr-centre-1", "rrrpass123")
    sub_id = await _classified_submission(client, token, idem_prefix="lot-owner-scope")
    create_resp = await client.post(
        "/api/v1/lots",
        json={"category": "e-waste-small-appliances", "submission_ids": [sub_id]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lot-owner-scope-create"},
    )
    lot_id = create_resp.json()["lot_id"]

    other_token = await _login(client, "rrr-centre-2", "rrrpass123")
    list_resp = await client.get("/api/v1/lots", headers={"Authorization": f"Bearer {other_token}"})
    assert lot_id not in [lot["lot_id"] for lot in list_resp.json()["lots"]]

    detail_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert detail_resp.status_code == 403
    assert detail_resp.json()["error_code"] == "NOT_LOT_OWNER"

    admin_token = await _login(client, "admin", "admin1234")
    admin_detail_resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_detail_resp.status_code == 200


@pytest.mark.asyncio
async def test_non_rrr_role_cannot_create_a_lot(client, seeded_collector):
    token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.post(
        "/api/v1/lots",
        json={"category": "x", "submission_ids": ["whatever"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "non-rrr-lot-create"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


# --- Recycler marketplace visibility (Phase 6) --------------------------


@pytest.mark.asyncio
async def test_approved_recycler_sees_listed_lot_regardless_of_ward(
    client, seeded_approved_recycler, listed_lot
):
    lot_id, _submission_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.get("/api/v1/lots/listed", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert lot_id in [lot["lot_id"] for lot in resp.json()["lots"]]


@pytest.mark.asyncio
async def test_pending_recycler_cannot_browse_listed_lots(client, pending_recycler, listed_lot):
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.get("/api/v1/lots/listed", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "RECYCLER_NOT_APPROVED"


@pytest.mark.asyncio
async def test_approved_recycler_can_view_any_lot_detail(client, seeded_approved_recycler, listed_lot):
    lot_id, _submission_id = listed_lot
    token = await _login(client, "demo-recycler-1", "recyclerpass123")
    resp = await client.get(f"/api/v1/lots/{lot_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["lot_id"] == lot_id
    assert resp.json()["status"] == "LISTED_FOR_BIDDING"

"""
Integration tests for POST /api/v1/ai/classify/{submission_id}.

IMPORTANT: DeterministicMockClassifier is a pure, offline, hash-based
function — these tests validate the AI-classification INTEGRATION
(RBAC, state transitions, idempotency, audit, append-only history), not
real-world model accuracy. HIGH_CONF_PHOTO_ID/LOW_CONF_PHOTO_ID below
were derived once directly from that pure function (see the search used
during development) and are stable forever, since the function has no
external state.
"""
import asyncio

import pytest

from app.db.mongo import get_db
from app.db.repositories import audit_repo, classifications_repo
from app.modules.classification import service as classification_service
from app.modules.classification.classifier import ClassificationResult, ClassifierError, ClassifierService
from tests.support.mock_classifier import DeterministicMockClassifier

# sha256("search-0"...) -> confidence 0.7074, well above the default 0.6 threshold.
HIGH_CONF_PHOTO_ID = "search-0"
# sha256("search-2"...) -> confidence 0.239, well below the default 0.6 threshold.
LOW_CONF_PHOTO_ID = "search-2"


@pytest.fixture(autouse=True)
def use_deterministic_classifier(monkeypatch):
    monkeypatch.setattr(
        classification_service,
        "get_classifier",
        lambda: DeterministicMockClassifier(),
    )


async def _login(client, username, password):
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _submit_and_advance_to_at_rrr(client, photo_file_id, idem_prefix="clf"):
    """Drives a brand-new submission to AT_RRR through the real APIs, with
    a caller-chosen photo_file_id — used so each test controls exactly
    which deterministic confidence bucket it lands in."""
    home_token = await _login(client, "home-user-1", "homepass123")
    submit_resp = await client.post(
        "/api/v1/ewaste/submissions",
        json={"ward_id": "WARD-1", "photo_file_id": photo_file_id, "home_lat": 12.9716, "home_lng": 77.5946},
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": f"{idem_prefix}-submit"},
    )
    assert submit_resp.status_code == 200, submit_resp.text
    submission_id = submit_resp.json()["submission_id"]

    collector_token = await _login(client, "EMP-001", "collectorpass1")
    handover_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/handover",
        json={"photo_file_id": photo_file_id, "collector_lat": 12.97165, "collector_lng": 77.59465},
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": f"{idem_prefix}-handover"},
    )
    assert handover_resp.json()["status"] == "COLLECTED"

    rrr_token = await _login(client, "rrr-centre-1", "rrrpass123")
    receive_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/receive",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": f"{idem_prefix}-receive"},
    )
    assert receive_resp.json()["status"] == "AT_RRR"
    return submission_id, rrr_token


class FakeFailingClassifier(ClassifierService):
    async def classify(self, photo_file_id, category_hint=None):
        raise ClassifierError("simulated provider outage")


class FakeUnexpectedExceptionClassifier(ClassifierService):
    async def classify(self, photo_file_id, category_hint=None):
        raise ValueError("simulated unexpected bug, not a ClassifierError")


class FakeMalformedClassifier(ClassifierService):
    async def classify(self, photo_file_id, category_hint=None):
        # confidence out of [0,1] range — a malformed response.
        return ClassificationResult(success=True, predicted_category="metal-scrap", confidence=1.7, model_version="fake-v1")


# ---------------------------------------------------------------------------
# High-confidence success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_high_confidence_ai_classification_reaches_classified(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "high")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "high-ai-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "CLASSIFIED"
    assert body["needs_review"] is False
    assert body["source"] == "AI"
    assert body["category"] == body["predicted_category"]
    assert body["confidence"] >= 0.6

    # Persisted correctly — real state, not just the HTTP response.
    admin_token = await _login(client, "admin", "admin1234")
    detail = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "CLASSIFIED"


# ---------------------------------------------------------------------------
# Low-confidence -> NEEDS_REVIEW
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_confidence_ai_classification_routes_to_needs_review(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, LOW_CONF_PHOTO_ID, "low")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "low-ai-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "NEEDS_REVIEW"
    assert body["needs_review"] is True
    assert body["category"] is None  # never silently accepted
    assert body["predicted_category"] is not None  # the guess is still visible
    assert body["confidence"] < 0.6


# ---------------------------------------------------------------------------
# Classifier failure / malformed response -> NEEDS_REVIEW, never a 500
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classifier_error_routes_to_needs_review_not_a_crash(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user, monkeypatch
):
    monkeypatch.setattr(classification_service, "get_classifier", lambda: FakeFailingClassifier())
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, "irrelevant-photo", "fail")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "fail-ai-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "NEEDS_REVIEW"
    assert body["failure_reason"] == "simulated provider outage"


@pytest.mark.asyncio
async def test_unexpected_classifier_exception_never_crashes_the_request(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user, monkeypatch
):
    monkeypatch.setattr(classification_service, "get_classifier", lambda: FakeUnexpectedExceptionClassifier())
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, "irrelevant-photo-2", "unexpected")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "unexpected-ai-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "NEEDS_REVIEW"
    assert "UNEXPECTED_CLASSIFIER_EXCEPTION" in body["failure_reason"]


@pytest.mark.asyncio
async def test_malformed_classifier_response_routes_to_needs_review(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user, monkeypatch
):
    monkeypatch.setattr(classification_service, "get_classifier", lambda: FakeMalformedClassifier())
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, "irrelevant-photo-3", "malformed")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "malformed-ai-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "NEEDS_REVIEW"
    assert body["failure_reason"] == "MALFORMED_CLASSIFIER_RESPONSE"
    assert body["category"] is None


# ---------------------------------------------------------------------------
# Missing/present provider credentials — must not change behavior, must
# never leak.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classification_works_identically_with_no_provider_credentials_configured(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    from app.core.config import settings

    assert settings.ai_provider_api_key is None  # the real default
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "nocred")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "nocred-ai-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLASSIFIED"


@pytest.mark.asyncio
async def test_configuring_a_provider_key_never_leaks_into_any_response_or_db_record(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user, monkeypatch
):
    from app.core.config import settings

    fake_secret = "sk-super-secret-value-must-never-appear-anywhere"
    monkeypatch.setattr(settings, "ai_provider_api_key", fake_secret)

    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "secret")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "secret-ai-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLASSIFIED"  # behavior unchanged by the key being set
    assert fake_secret not in resp.text

    stored = await classifications_repo.find_by_item_id(submission_id)
    assert fake_secret not in str(stored)


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_home_user_cannot_call_ai_classify(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, _rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "rbac1")
    home_token = await _login(client, "home-user-1", "homepass123")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {home_token}", "Idempotency-Key": "rbac1-ai"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_collector_cannot_call_ai_classify(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, _rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "rbac2")
    collector_token = await _login(client, "EMP-001", "collectorpass1")
    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {collector_token}", "Idempotency-Key": "rbac2-ai"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_wrong_ward_rrr_cannot_classify(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user, other_ward
):
    from app.modules.rrr_centres import service as rrr_centres_service

    submission_id, _rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "rbac3")

    other_rrr = await rrr_centres_service.register(
        username="other-rrr", password="otherpass123", rrr_id="RRR-002", tender_id="TENDER-002",
        ward_id="WARD-2", licence_doc_ref=None,
    )
    admin_actor = {"user_id": "seed-admin", "role": "GOVERNMENT_ADMIN"}
    await rrr_centres_service.approve(user_id=other_rrr["user"]["user_id"], actor=admin_actor)
    other_token = await _login(client, "other-rrr", "otherpass123")

    resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "rbac3-ai"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "RRR_OUTSIDE_ASSIGNED_WARD"


@pytest.mark.asyncio
async def test_ai_classify_requires_at_rrr_status(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "notatrrr")
    first = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "notatrrr-ai-1"},
    )
    assert first.json()["status"] == "CLASSIFIED"

    second = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "notatrrr-ai-2"},
    )
    assert second.status_code == 400
    assert second.json()["error_code"] == "SUBMISSION_NOT_AT_RRR"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_classify_idempotency_replay_does_not_duplicate(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, LOW_CONF_PHOTO_ID, "idem")
    key = "idem-ai-fixed-key"
    first = await client.post(
        f"/api/v1/ai/classify/{submission_id}", headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": key}
    )
    second = await client.post(
        f"/api/v1/ai/classify/{submission_id}", headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": key}
    )
    assert first.json() == second.json()

    docs = [d async for d in get_db().ai_classifications.find({"item_id": submission_id})]
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_missing_idempotency_key_header_is_rejected(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "noidem")
    resp = await client.post(f"/api/v1/ai/classify/{submission_id}", headers={"Authorization": f"Bearer {rrr_token}"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Concurrency (documented honestly, same category of limitation as Phase 6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_ai_classify_attempts_do_not_corrupt_state(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    """Fires two AI-classify requests for the SAME submission with
    DIFFERENT idempotency keys via asyncio.gather, simulating a genuine
    double-invocation (not a retry). As documented since Phase 6,
    mongomock-motor + httpx.ASGITransport do not reliably interleave two
    'concurrent' coroutines the way two real connections against real
    MongoDB would, so this does not prove a database-level race is
    closed — the classify() status pre-check (AT_RRR-only) is the actual
    defense here, same as many other single-writer-per-document flows in
    this codebase. What this test DOES prove: no unhandled exception,
    no corrupted intermediate state, and — because the mock classifier is
    a pure function of photo_file_id — even if both requests genuinely
    raced, their computed results would be identical, never contradictory."""
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "race")

    resp1, resp2 = await asyncio.gather(
        client.post(
            f"/api/v1/ai/classify/{submission_id}",
            headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "race-key-1"},
        ),
        client.post(
            f"/api/v1/ai/classify/{submission_id}",
            headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "race-key-2"},
        ),
    )

    statuses = {resp1.status_code, resp2.status_code}
    assert statuses <= {200, 400}
    assert 200 in statuses  # at least one succeeded

    admin_token = await _login(client, "admin", "admin1234")
    final = await client.get(
        f"/api/v1/ewaste/submissions/{submission_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert final.json()["status"] == "CLASSIFIED"

    records = [d async for d in get_db().ai_classifications.find({"item_id": submission_id})]
    assert len(records) in (1, 2)
    if len(records) == 2:
        # Same deterministic input -> identical predicted output, proving
        # no corruption even if both genuinely executed.
        assert records[0]["predicted_category"] == records[1]["predicted_category"]
        assert records[0]["confidence"] == records[1]["confidence"]


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_classification_attempt_is_audited(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, HIGH_CONF_PHOTO_ID, "audit")
    await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "audit-ai-1"},
    )
    logs = await audit_repo.list_logs(entity_type="e_waste_submission")
    matching = [
        log for log in logs if log["entity_id"] == submission_id and log["action"] == "AI_CLASSIFICATION_ATTEMPTED"
    ]
    assert len(matching) == 1
    assert matching[0]["details"]["accepted"] is True
    assert matching[0]["details"]["new_status"] == "CLASSIFIED"


# ---------------------------------------------------------------------------
# Manual classification: unchanged for AT_RRR, and now also resolves
# NEEDS_REVIEW.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_classification_of_a_plain_at_rrr_item_still_works(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, "manual-only-photo", "manual1")
    resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/classify",
        json={"category": "plastics"},
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "manual1-classify"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLASSIFIED"
    assert resp.json()["category"] == "plastics"


@pytest.mark.asyncio
async def test_manual_classification_resolves_a_needs_review_item(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, LOW_CONF_PHOTO_ID, "manual2")
    ai_resp = await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "manual2-ai"},
    )
    assert ai_resp.json()["status"] == "NEEDS_REVIEW"

    manual_resp = await client.post(
        f"/api/v1/ewaste/submissions/{submission_id}/classify",
        json={"category": "batteries"},
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "manual2-classify"},
    )
    assert manual_resp.status_code == 200, manual_resp.text
    assert manual_resp.json()["status"] == "CLASSIFIED"
    assert manual_resp.json()["category"] == "batteries"

    # Append-only: both the AI attempt and the manual resolution are kept.
    docs = [
        d async for d in get_db().ai_classifications.find({"item_id": submission_id}).sort("created_at", 1)
    ]
    assert len(docs) == 2
    assert docs[0]["source"] == "AI"
    assert docs[0]["status"] == "LOW_CONFIDENCE"
    assert docs[1]["source"] == "MANUAL"
    assert docs[1]["confirmed_category"] == "batteries"


@pytest.mark.asyncio
async def test_needs_review_item_appears_in_awaiting_classification_queue(
    client, seeded_admin, seeded_rrr_center, seeded_collector, seeded_home_user
):
    submission_id, rrr_token = await _submit_and_advance_to_at_rrr(client, LOW_CONF_PHOTO_ID, "queue")
    await client.post(
        f"/api/v1/ai/classify/{submission_id}",
        headers={"Authorization": f"Bearer {rrr_token}", "Idempotency-Key": "queue-ai"},
    )
    resp = await client.get(
        "/api/v1/ewaste/submissions/awaiting-classification", headers={"Authorization": f"Bearer {rrr_token}"}
    )
    assert resp.status_code == 200
    ids_and_statuses = [(s["submission_id"], s["status"]) for s in resp.json()["submissions"]]
    assert (submission_id, "NEEDS_REVIEW") in ids_and_statuses

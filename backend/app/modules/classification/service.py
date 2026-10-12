"""
AI-driven classification (architecture Section 9), a sibling to the
existing manual classify() in app/modules/ewaste/service.py — NOT a
replacement for it. Both write to the same append-only
ai_classifications collection and drive the same
state_machines/ewaste_states.py; this module owns only the AT_RRR ->
{CLASSIFIED, NEEDS_REVIEW} decision based on the classifier's result.

Money-equivalent safety principle applied here: never silently accept an
unreliable result. success=False OR confidence below the configured
threshold OR a malformed ClassificationResult all route to NEEDS_REVIEW,
exactly like an unresolved handover routes to FLAGGED_FOR_REVIEW instead
of silently "succeeding".
"""
from datetime import datetime, timezone
from uuid import uuid4

from app.core import audit, idempotency
from app.core.config import settings
from app.core.errors import bad_request, forbidden, not_found
from app.db.repositories import classifications_repo, submissions_repo
from app.modules.classification.classifier import ClassificationResult, ClassifierError, get_classifier
from app.modules.rrr_centres import service as rrr_centres_service
from app.state_machines.ewaste_states import transition

AI_CLASSIFY_IDEMPOTENCY_SCOPE = "ai_classify"


async def classify_photo(photo_file_id: str) -> dict:
    """Classify an uploaded photo before a home-user submission exists."""
    try:
        classifier = get_classifier()
        result = await classifier.classify(photo_file_id)
    except Exception as exc:
        result = ClassificationResult(
            success=False,
            predicted_category=None,
            confidence=None,
            model_version=settings.ai_model_version,
            failure_reason=f"UNEXPECTED_CLASSIFIER_EXCEPTION: {type(exc).__name__}",
        )

    accepted = (
        result.success
        and result.confidence is not None
        and result.confidence >= settings.classification_confidence_threshold
    )
    return {
        "category": result.predicted_category if accepted else None,
        "predicted_category": result.predicted_category,
        "confidence": result.confidence,
        "model_version": result.model_version,
        "source": "AI",
        "needs_review": not accepted,
        "failure_reason": result.failure_reason,
        "detected_class": result.metadata.get("detected_label"),
        "bounding_boxes": [
            detection["bounding_box"]
            for detection in result.metadata.get("detections", [])
        ],
        "object_count": result.metadata.get("object_count", 0),
    }


def _is_well_formed(result: ClassificationResult) -> bool:
    """Defends against a malformed classifier response (e.g. a future
    real provider returning a garbage payload) — this is deliberately
    checked here, not trusted from the classifier, since the classifier
    is a swappable, potentially-untrusted-input boundary."""
    if not result.success:
        return True  # a reported failure doesn't need category/confidence to be valid
    if not isinstance(result.predicted_category, str) or not result.predicted_category.strip():
        return False
    if not isinstance(result.confidence, (int, float)):
        return False
    if isinstance(result.confidence, bool):  # bool is technically an int subclass
        return False
    if not (0.0 <= float(result.confidence) <= 1.0):
        return False
    return True


async def classify_with_ai(*, current_user: dict, submission_id: str, idempotency_key: str) -> dict:
    cached = await idempotency.get_cached_response(current_user["user_id"], idempotency_key, AI_CLASSIFY_IDEMPOTENCY_SCOPE)
    if cached is not None:
        return cached

    rrr_profile = await rrr_centres_service.require_approved_rrr(current_user)

    submission = await submissions_repo.find_by_submission_id(submission_id)
    if submission is None:
        raise not_found("SUBMISSION_NOT_FOUND", "No submission exists with this submission_id.")
    if submission["ward_id"] != rrr_profile["ward_id"]:
        raise forbidden("RRR_OUTSIDE_ASSIGNED_WARD", "This submission is outside your assigned ward.")
    if submission["status"] != "AT_RRR":
        raise bad_request(
            "SUBMISSION_NOT_AT_RRR",
            f"Submission is in status {submission['status']}, not eligible for AI classification.",
        )

    classifier = get_classifier()
    try:
        result = await classifier.classify(submission["photo_file_id"])
        if not _is_well_formed(result):
            result = ClassificationResult(
                success=False,
                predicted_category=None,
                confidence=None,
                model_version=result.model_version or settings.ai_model_version,
                failure_reason="MALFORMED_CLASSIFIER_RESPONSE",
            )
    except ClassifierError as exc:
        result = ClassificationResult(
            success=False,
            predicted_category=None,
            confidence=None,
            model_version=settings.ai_model_version,
            failure_reason=str(exc) or "CLASSIFIER_ERROR",
        )
    except Exception as exc:  # never let a classifier bug crash the RRR workflow
        result = ClassificationResult(
            success=False,
            predicted_category=None,
            confidence=None,
            model_version=settings.ai_model_version,
            failure_reason=f"UNEXPECTED_CLASSIFIER_EXCEPTION: {type(exc).__name__}",
        )

    accepted = result.success and result.confidence is not None and result.confidence >= settings.classification_confidence_threshold
    now = datetime.now(timezone.utc)

    if accepted:
        new_status = transition("AT_RRR", "CLASSIFIED")
        await submissions_repo.update_status_and_category(submission_id, new_status, result.predicted_category)
    else:
        new_status = transition("AT_RRR", "NEEDS_REVIEW")
        await submissions_repo.update_status(submission_id, new_status)

    classification_id = str(uuid4())
    await classifications_repo.insert_classification(
        {
            "classification_id": classification_id,
            "item_id": submission_id,
            "predicted_category": result.predicted_category,
            "confidence": result.confidence,
            "model_version": result.model_version,
            "confirmed_category": result.predicted_category if accepted else None,
            "confirmed_by": None,  # AI-only acceptance has no human confirmer, by design
            "source": "AI",
            "status": "ACCEPTED" if accepted else ("FAILED" if not result.success else "LOW_CONFIDENCE"),
            "failure_reason": result.failure_reason,
            "detected_class": result.metadata.get("detected_label"),
            "detections": result.metadata.get("detections", []),
            "object_count": result.metadata.get("object_count", 0),
            "created_at": now,
        }
    )

    await audit.record(
        actor_id=current_user["user_id"],
        actor_role=current_user["role"],
        action="AI_CLASSIFICATION_ATTEMPTED",
        entity_type="e_waste_submission",
        entity_id=submission_id,
        details={
            "classification_id": classification_id,
            "accepted": accepted,
            "new_status": new_status,
            "predicted_category": result.predicted_category,
            "confidence": result.confidence,
        },
    )

    response = {
        "submission_id": submission_id,
        "status": new_status,
        "category": result.predicted_category if accepted else None,
        "predicted_category": result.predicted_category,
        "confidence": result.confidence,
        "model_version": result.model_version,
        "source": "AI",
        "needs_review": not accepted,
        "failure_reason": result.failure_reason,
        "detected_class": result.metadata.get("detected_label"),
        "bounding_boxes": [detection["bounding_box"] for detection in result.metadata.get("detections", [])],
        "object_count": result.metadata.get("object_count", 0),
    }
    await idempotency.store_response(current_user["user_id"], idempotency_key, AI_CLASSIFY_IDEMPOTENCY_SCOPE, response)
    return response

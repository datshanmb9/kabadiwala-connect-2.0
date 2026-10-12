"""
Pure tests for app.modules.classification.classifier — no FastAPI/Mongo
dependency.

IMPORTANT: DeterministicMockClassifier is a hash-based, offline,
rule-based function, not a trained model. These tests validate that it
behaves consistently and deterministically (i.e. that the integration
wiring around it works), never that its category guesses are correct in
any real-world sense.
"""
import pytest

from app.modules.classification.classifier import ClassificationResult, ClassifierService
from tests.support.mock_classifier import MOCK_CATEGORIES, DeterministicMockClassifier


@pytest.mark.asyncio
async def test_same_photo_file_id_always_produces_the_same_result():
    classifier = DeterministicMockClassifier()
    result1 = await classifier.classify("photo-abc")
    result2 = await classifier.classify("photo-abc")
    assert result1 == result2


@pytest.mark.asyncio
async def test_result_is_always_well_formed():
    classifier = DeterministicMockClassifier()
    for photo_id in ("a", "b", "some-long-photo-reference-string", "", "🔋"):
        result = await classifier.classify(photo_id)
        assert result.success is True
        assert result.predicted_category in MOCK_CATEGORIES
        assert 0.0 <= result.confidence <= 1.0
        assert result.model_version
        # No chain-of-thought/free-text reasoning ever stored.
        assert set(result.metadata.keys()) <= {"heuristic"}


@pytest.mark.asyncio
async def test_different_photo_file_ids_can_produce_different_results():
    classifier = DeterministicMockClassifier()
    results = [await classifier.classify(f"photo-{i}") for i in range(20)]
    pairs = {(r.predicted_category, r.confidence) for r in results}
    # Not every one of 20 distinct inputs collides to the exact same
    # (category, confidence) pair — proves the hash is actually being
    # used, not a constant stub.
    assert len(pairs) > 1


def test_deterministic_mock_is_a_classifier_service():
    assert isinstance(DeterministicMockClassifier(), ClassifierService)


def test_classification_result_has_no_chain_of_thought_field():
    """Structural guarantee, not just a convention: the dataclass itself
    has no field named anything like 'reasoning' or 'thoughts'."""
    field_names = set(ClassificationResult.__dataclass_fields__.keys())
    assert field_names == {"success", "predicted_category", "confidence", "model_version", "failure_reason", "metadata"}

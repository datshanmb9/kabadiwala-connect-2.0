"""
The swappable AI classifier abstraction (architecture Section 9:
"a thin internal interface ClassifierService.classify(photo) ->
{category, confidence, model_version} — the concrete model implementation
is swappable behind this interface").

Phase 8 ships exactly ONE concrete implementation, DeterministicMockClassifier,
and deliberately no second "real provider" class. Why: every submission's
photo_file_id has been an opaque, caller-supplied string since Phase 3 —
never a real uploaded file — so there is nothing genuine a real vision-AI
provider could be sent. Building an HTTP-calling provider class that could
never actually be exercised with real image bytes would be exactly the
kind of half-finished/unreachable code this project avoids. The swap
point for a future real provider is get_classifier() below: add a new
ClassifierService subclass and one branch there once real image storage
exists — nothing else in the codebase needs to change, which is the
entire point of the abstraction.

IMPORTANT: DeterministicMockClassifier validates integration behavior
(does the AT_RRR -> CLASSIFIED / NEEDS_REVIEW wiring work correctly?),
never real-world classification accuracy. It is a pure hash-based
function, not a trained model, and is documented as such everywhere it
is referenced (code, tests, PROJECT_STATUS.md).
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

# Same category vocabulary the manual classification UI already suggests
# (rrr-centre-web's ClassifyItemsPage SUGGESTED_CATEGORIES) — kept in sync
# deliberately, not coincidentally.
MOCK_CATEGORIES = ("e-waste-small-appliances", "metal-scrap", "plastics", "circuit-boards", "batteries")


@dataclass(frozen=True)
class ClassificationResult:
    """What every ClassifierService implementation returns. Deliberately
    has no field for chain-of-thought/hidden reasoning — `metadata` is for
    small, safe, structured facts only (e.g. which heuristic fired), never
    free-text model reasoning."""

    success: bool
    predicted_category: str | None
    confidence: float | None
    model_version: str
    failure_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ClassifierError(Exception):
    """Raised by a ClassifierService implementation on total failure (the
    equivalent of a real provider's network/timeout/5xx error). The
    service layer catches this specifically — and any other unexpected
    exception — and converts it into a NEEDS_REVIEW outcome; it never
    propagates out of the classify-with-AI endpoint as a 500."""


class ClassifierService(ABC):
    @abstractmethod
    async def classify(self, photo_file_id: str, category_hint: str | None = None) -> ClassificationResult:
        """Must not raise for an ordinary low-confidence result — that is
        a normal, successful ClassificationResult with a low `confidence`.
        Raise ClassifierError only for a genuine attempt failure (the mock
        implementation never does; a future real provider would, e.g., on
        a network error)."""
        raise NotImplementedError


class DeterministicMockClassifier(ClassifierService):
    """Pure, offline, reproducible: the exact same photo_file_id always
    produces the exact same (category, confidence) pair, computed from a
    SHA-256 hash of the input — no network call, no external state, no
    real image bytes read. This determinism is what makes the high- and
    low-confidence paths both reliably testable and safely reproducible
    during live demo verification."""

    async def classify(self, photo_file_id: str, category_hint: str | None = None) -> ClassificationResult:
        digest = hashlib.sha256(photo_file_id.encode("utf-8")).hexdigest()
        confidence = int(digest[:8], 16) / 0xFFFFFFFF
        category = MOCK_CATEGORIES[int(digest[8:16], 16) % len(MOCK_CATEGORIES)]
        return ClassificationResult(
            success=True,
            predicted_category=category,
            confidence=round(confidence, 4),
            model_version=settings.ai_model_version,
            metadata={"heuristic": "sha256(photo_file_id)"},
        )


_classifier: ClassifierService = DeterministicMockClassifier()


def get_classifier() -> ClassifierService:
    """The one factory function a future real-provider integration would
    extend (e.g. `if settings.ai_provider_api_key: return
    RealProviderClassifier(settings.ai_provider_api_key)`). Today it
    always returns the mock, regardless of whether ai_provider_api_key is
    set — that field has no reader yet (see config.py), which is exactly
    how "the app works whether or not AI credentials are configured" is
    proven structurally rather than asserted."""
    return _classifier

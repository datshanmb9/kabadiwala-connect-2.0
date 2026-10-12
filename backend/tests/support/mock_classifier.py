from hashlib import sha256

from app.core.config import settings
from app.modules.classification.classifier import ClassificationResult, ClassifierService


MOCK_CATEGORIES = (
    "e-waste-small-appliances",
    "metal-scrap",
    "plastics",
    "circuit-boards",
    "batteries",
)


class DeterministicMockClassifier(ClassifierService):
    async def classify(
        self,
        photo_file_id: str,
        category_hint: str | None = None,
    ) -> ClassificationResult:
        digest = sha256(photo_file_id.encode("utf-8")).hexdigest()
        confidence = int(digest[:8], 16) / 0xFFFFFFFF
        category = MOCK_CATEGORIES[int(digest[8:16], 16) % len(MOCK_CATEGORIES)]

        return ClassificationResult(
            success=True,
            predicted_category=category,
            confidence=round(confidence, 4),
            model_version=settings.ai_model_version,
            metadata={"heuristic": "sha256(photo_file_id)"},
        )
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ClassificationResult:
    success: bool
    predicted_category: Optional[str] = None
    confidence: float = 0.0
    model_version: str = "unknown"
    failure_reason: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ClassifierError(Exception):
    """Raised when classification fails."""
    pass


class ClassifierService(ABC):

    @abstractmethod
    async def classify(self, photo_file_id: str) -> ClassificationResult:
        """Classify an image using the configured model."""
        raise NotImplementedError


def get_classifier() -> ClassifierService:
    """
    Return the YOLO classifier.

    The import is inside the function to prevent circular imports.
    """
    from .yolo_classifier import YOLOClassifier

    return YOLOClassifier()
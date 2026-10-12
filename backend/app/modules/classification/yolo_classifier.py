from pathlib import Path
import asyncio

from ultralytics import YOLO

from app.core.media_storage import resolve_photo_reference

from .classifier import (
    ClassifierService,
    ClassificationResult,
)


class YOLOClassifier(ClassifierService):
    def __init__(self):
        model_path = (
            Path(__file__).resolve().parents[3]
            / "ai"
            / "detection"
            / "weights"
            / "best.pt"
        )

        self.model = YOLO(str(model_path))
        self.model_version = "YOLO-best.pt"

    def map_category(self, detected_label: str) -> str:
        label = detected_label.lower()

        if "battery" in label:
            return "batteries"

        if label in ["pcb"]:
            return "circuit-boards"

        if label in [
            "computer-keyboard",
            "computer-mouse",
            "router",
            "usb-flash-drive",
            "telephone-set",
            "tv-remote-control",
        ]:
            return "e-waste-small-appliances"

        return "e-waste-small-appliances"

    async def classify(self, photo_file_id: str) -> ClassificationResult:
        try:
            image_path = resolve_photo_reference(photo_file_id)

            if not image_path.exists():
                return ClassificationResult(
                    success=False,
                    predicted_category=None,
                    confidence=0.0,
                    model_version=self.model_version,
                    failure_reason=f"Image not found: {photo_file_id}",
                    metadata={},
                )

            results = await asyncio.to_thread(
                self.model.predict,
                source=str(image_path),
                verbose=False,
            )

            result = results[0]

            if result.boxes is None or len(result.boxes) == 0:
                return ClassificationResult(
                    success=False,
                    predicted_category=None,
                    confidence=0.0,
                    model_version=self.model_version,
                    failure_reason="No object detected",
                    metadata={},
                )

            detections = []
            for index in range(len(result.boxes)):
                confidence = float(result.boxes.conf[index])
                class_id = int(result.boxes.cls[index])
                detected_label = result.names[class_id]
                detections.append(
                    {
                        "class_id": class_id,
                        "class_name": detected_label,
                        "confidence": confidence,
                        "bounding_box": [float(value) for value in result.boxes.xyxy[index].tolist()],
                    }
                )

            best_detection = max(detections, key=lambda detection: detection["confidence"])
            confidence = best_detection["confidence"]
            class_id = best_detection["class_id"]
            detected_label = best_detection["class_name"]

            category = self.map_category(detected_label)

            return ClassificationResult(
                success=True,
                predicted_category=category,
                confidence=confidence,
                model_version=self.model_version,
                failure_reason=None,
                metadata={
                    "detected_label": detected_label,
                    "class_id": class_id,
                    "object_count": len(detections),
                    "detections": detections,
                },
            )

        except Exception as error:
            return ClassificationResult(
                success=False,
                predicted_category=None,
                confidence=0.0,
                model_version=self.model_version,
                failure_reason=str(error),
                metadata={},
            )
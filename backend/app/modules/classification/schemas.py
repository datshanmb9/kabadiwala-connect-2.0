from pydantic import BaseModel, ConfigDict, Field


class AiPhotoClassifyRequest(BaseModel):
    photo_file_id: str


class AiClassifyResponse(BaseModel):
    # model_version isn't a Pydantic protected-namespace clash in intent —
    # it matches the field name already established across
    # ai_classifications/config.py/architecture docs — so the namespace
    # check is disabled here rather than renaming the field.
    model_config = ConfigDict(protected_namespaces=())

    submission_id: str
    status: str  # "CLASSIFIED" or "NEEDS_REVIEW"
    category: str | None  # the accepted category, only set when status == CLASSIFIED
    predicted_category: str | None  # whatever the classifier guessed, even if not accepted
    confidence: float | None
    model_version: str
    source: str = "AI"
    needs_review: bool
    failure_reason: str | None = None
    detected_class: str | None = None
    bounding_boxes: list[list[float]] = Field(default_factory=list)
    object_count: int = 0


class AiPhotoClassifyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    category: str | None
    predicted_category: str | None
    confidence: float | None
    model_version: str
    source: str = "AI"
    needs_review: bool
    failure_reason: str | None = None
    detected_class: str | None = None
    bounding_boxes: list[list[float]] = Field(default_factory=list)
    object_count: int = 0

from pydantic import BaseModel, Field


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    target_language: str = Field(min_length=1, max_length=32)


class TranslationResult(BaseModel):
    source_text: str
    translated_text: str


class TranslationResponse(BaseModel):
    source_language: str
    target_language: str
    source_text: str
    translated_text: str
    model: str
    is_machine_translated: bool
    cached: bool = False


class TranslationBatchRequest(BaseModel):
    target_language: str = Field(min_length=1, max_length=32)
    texts: list[str] = Field(min_length=1, max_length=64)


class TranslationBatchResponse(BaseModel):
    source_language: str
    target_language: str
    translations: list[TranslationResult]
    model: str
    is_machine_translated: bool
    cached: bool = False
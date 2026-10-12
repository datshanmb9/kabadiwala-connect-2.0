from fastapi import APIRouter, Depends

from app.core.rbac import require_role
from app.modules.translation import service
from app.modules.translation.schemas import (
    TranslationBatchRequest,
    TranslationBatchResponse,
    TranslationRequest,
    TranslationResponse,
    TranslationResult,
)

router = APIRouter(prefix="/api/v1/translation", tags=["translation"])


@router.get("/languages")
async def supported_languages_route(_current_user: dict = Depends(require_role("HOME_USER"))):
    return {
        "source_language": service.SOURCE_LANGUAGE,
        "languages": [
            {"code": code, "name": name}
            for code, name in service.SUPPORTED_LANGUAGES.items()
        ],
        "model": service.translator.model_id,
    }


@router.post("/translate", response_model=TranslationResponse)
async def translate_route(
    body: TranslationRequest,
    _current_user: dict = Depends(require_role("HOME_USER")),
):
    translated, cached = await service.translate(body.text, body.target_language)
    return TranslationResponse(
        source_language=service.SOURCE_LANGUAGE,
        target_language=body.target_language,
        source_text=body.text,
        translated_text=translated,
        model=service.translator.model_id,
        is_machine_translated=body.target_language != service.SOURCE_LANGUAGE,
        cached=cached,
    )


@router.post("/translate-batch", response_model=TranslationBatchResponse)
async def translate_batch_route(
    body: TranslationBatchRequest,
    _current_user: dict = Depends(require_role("HOME_USER")),
):
    translated, cached = await service.translate_batch(body.texts, body.target_language)
    return TranslationBatchResponse(
        source_language=service.SOURCE_LANGUAGE,
        target_language=body.target_language,
        translations=[
            TranslationResult(source_text=source, translated_text=value)
            for source, value in zip(body.texts, translated, strict=True)
        ],
        model=service.translator.model_id,
        is_machine_translated=body.target_language != service.SOURCE_LANGUAGE,
        cached=cached,
    )
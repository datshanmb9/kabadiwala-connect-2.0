import asyncio
import logging
from collections.abc import Iterable

from app.core.config import settings
from app.core.errors import bad_request, service_unavailable

logger = logging.getLogger("kabadiwala.translation")

SOURCE_LANGUAGE = "eng_Latn"

SUPPORTED_LANGUAGES: dict[str, str] = {
    "eng_Latn": "English",
    "asm_Beng": "Assamese",
    "ben_Beng": "Bengali",
    "brx_Deva": "Bodo",
    "doi_Deva": "Dogri",
    "gom_Deva": "Konkani",
    "guj_Gujr": "Gujarati",
    "hin_Deva": "Hindi",
    "kan_Knda": "Kannada",
    "kas_Arab": "Kashmiri (Arabic)",
    "kas_Deva": "Kashmiri (Devanagari)",
    "mai_Deva": "Maithili",
    "mal_Mlym": "Malayalam",
    "mar_Deva": "Marathi",
    "mni_Beng": "Manipuri (Bengali)",
    "mni_Mtei": "Manipuri (Meitei)",
    "npi_Deva": "Nepali",
    "ory_Orya": "Odia",
    "pan_Guru": "Punjabi",
    "san_Deva": "Sanskrit",
    "sat_Olck": "Santali",
    "snd_Arab": "Sindhi (Arabic)",
    "snd_Deva": "Sindhi (Devanagari)",
    "tam_Taml": "Tamil",
    "tel_Telu": "Telugu",
    "urd_Arab": "Urdu",
}


class TranslationModelError(Exception):
    pass


class IndicTrans2Translator:
    """Lazy, process-wide IndicTrans2 model holder and inference wrapper."""

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._processor = None
        self._device = None
        self._load_lock = asyncio.Lock()
        self._cache: dict[tuple[str, str, str, str], str] = {}

    @property
    def model_id(self) -> str:
        return settings.translation_model_id

    def supported_languages(self) -> dict[str, str]:
        return dict(SUPPORTED_LANGUAGES)

    def validate_target_language(self, target_language: str) -> str:
        if target_language not in SUPPORTED_LANGUAGES:
            raise bad_request(
                "UNSUPPORTED_LANGUAGE",
                "The selected language is not supported by the configured translation model.",
            )
        return target_language

    def validate_texts(self, texts: Iterable[str]) -> list[str]:
        values = list(texts)
        if not values:
            raise bad_request("INVALID_TRANSLATION_REQUEST", "At least one text is required.")
        if len(values) > settings.translation_max_batch_size:
            raise bad_request("INVALID_TRANSLATION_REQUEST", "Too many texts were supplied in one batch.")
        for text in values:
            if not isinstance(text, str) or not text.strip():
                raise bad_request("INVALID_TRANSLATION_REQUEST", "Translation text cannot be empty.")
            if len(text) > settings.translation_max_text_length:
                raise bad_request("INVALID_TRANSLATION_REQUEST", "Translation text is too long.")
        return values

    async def translate_batch(self, texts: list[str], target_language: str) -> tuple[list[str], bool]:
        target_language = self.validate_target_language(target_language)
        texts = self.validate_texts(texts)
        if target_language == SOURCE_LANGUAGE:
            return texts, True

        version = self.model_id
        translated: list[str | None] = []
        missing: list[str] = []
        for text in texts:
            key = (SOURCE_LANGUAGE, target_language, text, version)
            cached = self._cache.get(key)
            translated.append(cached)
            if cached is None and text not in missing:
                missing.append(text)

        if missing:
            await self._ensure_loaded()
            generated = await asyncio.to_thread(self._translate_sync, missing, target_language)
            for text, value in zip(missing, generated, strict=True):
                self._cache[(SOURCE_LANGUAGE, target_language, text, version)] = value
            translated = [
                self._cache[(SOURCE_LANGUAGE, target_language, text, version)]
                for text in texts
            ]

        return [value or text for value, text in zip(translated, texts, strict=True)], not missing

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._load_lock:
            if self._model is not None:
                return
            try:
                import torch
                from IndicTransToolkit.processor import IndicProcessor
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                cache_dir = settings.translation_model_cache_dir
                self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.model_id,
                    trust_remote_code=True,
                    cache_dir=cache_dir,
                )
                self._model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_id,
                    trust_remote_code=True,
                    low_cpu_mem_usage=True,
                    cache_dir=cache_dir,
                )
                self._model.to(self._device)
                self._model.eval()
                self._processor = IndicProcessor(inference=True)
                logger.info("Loaded translation model %s on %s", self.model_id, self._device)
            except Exception as exc:
                self._model = None
                logger.exception("Translation model loading failed for configured model")
                raise TranslationModelError("translation model unavailable") from exc

    def _translate_sync(self, texts: list[str], target_language: str) -> list[str]:
        try:
            import torch

            batch = self._processor.preprocess_batch(
                texts,
                src_lang=SOURCE_LANGUAGE,
                tgt_lang=target_language,
            )
            inputs = self._tokenizer(
                batch,
                truncation=True,
                padding="longest",
                return_tensors="pt",
                return_attention_mask=True,
            ).to(self._device)
            with torch.no_grad():
                generated = self._model.generate(
                    **inputs,
                    use_cache=True,
                    min_length=0,
                    max_length=settings.translation_max_new_tokens,
                    num_beams=5,
                    num_return_sequences=1,
                )
            decoded = self._tokenizer.batch_decode(
                generated,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )
            return self._processor.postprocess_batch(decoded, lang=target_language)
        except Exception as exc:
            logger.exception("Translation inference failed")
            raise TranslationModelError("translation inference failed") from exc
translator = IndicTrans2Translator()


async def translate(text: str, target_language: str) -> tuple[str, bool]:
    try:
        values, cached = await translator.translate_batch([text], target_language)
        return values[0], cached
    except TranslationModelError as exc:
        raise service_unavailable(
            "TRANSLATION_SERVICE_UNAVAILABLE",
            "The translation service is temporarily unavailable.",
        ) from exc


async def translate_batch(texts: list[str], target_language: str) -> tuple[list[str], bool]:
    try:
        return await translator.translate_batch(texts, target_language)
    except TranslationModelError as exc:
        raise service_unavailable(
            "TRANSLATION_SERVICE_UNAVAILABLE",
            "The translation service is temporarily unavailable.",
        ) from exc
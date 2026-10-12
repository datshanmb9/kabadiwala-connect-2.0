import pytest

from app.modules.translation import service as translation_service


async def _login(client, username, password):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_languages_returns_configured_model_codes(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    response = await client.get(
        "/api/v1/translation/languages",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    codes = {item["code"] for item in response.json()["languages"]}
    assert {"eng_Latn", "hin_Deva", "kan_Knda", "mar_Deva", "tam_Taml"} <= codes


@pytest.mark.asyncio
async def test_translation_validates_language_and_auth(client, seeded_home_user):
    response = await client.post(
        "/api/v1/translation/translate",
        json={"text": "Safety Measures", "target_language": "xx_Unknown"},
    )
    assert response.status_code == 401

    token = await _login(client, "home-user-1", "homepass123")
    response = await client.post(
        "/api/v1/translation/translate",
        json={"text": "Safety Measures", "target_language": "xx_Unknown"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "UNSUPPORTED_LANGUAGE"


@pytest.mark.asyncio
async def test_english_translation_is_available_without_model(client, seeded_home_user):
    token = await _login(client, "home-user-1", "homepass123")
    response = await client.post(
        "/api/v1/translation/translate",
        json={"text": "Safety Measures", "target_language": "eng_Latn"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["translated_text"] == "Safety Measures"
    assert response.json()["is_machine_translated"] is False


@pytest.mark.asyncio
async def test_batch_translation_preserves_order_and_cache(monkeypatch):
    translator = translation_service.IndicTrans2Translator()
    calls = []

    async def fake_load():
        translator._model = object()

    def fake_translate(texts, target_language):
        calls.append((texts, target_language))
        return [f"translated:{text}" for text in texts]

    monkeypatch.setattr(translator, "_ensure_loaded", fake_load)
    monkeypatch.setattr(translator, "_translate_sync", fake_translate)

    values, cached = await translator.translate_batch(
        ["Home", "Safety Measures", "Home"], "hin_Deva"
    )
    assert values == ["translated:Home", "translated:Safety Measures", "translated:Home"]
    assert cached is False
    assert calls == [(["Home", "Safety Measures"], "hin_Deva")]

    values, cached = await translator.translate_batch(["Home", "Safety Measures"], "hin_Deva")
    assert values == ["translated:Home", "translated:Safety Measures"]
    assert cached is True
    assert len(calls) == 1
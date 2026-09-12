import json


def test_calendar_translation_uses_cached_vi_and_en_labels(monkeypatch, tmp_path):
    from app.data_providers.economic_calendar_translation import translate_calendar_event_names

    cache_path = tmp_path / "event-name-translations.json"
    cache_path.write_text(json.dumps({
        "version": 1,
        "translations": {
            "美国未知指标": {"vi": "Chỉ báo chưa xác định của Hoa Kỳ", "en": "US Unknown Indicator"}
        }
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ECONOMIC_CALENDAR_TRANSLATION_CACHE_PATH", str(cache_path))

    result = translate_calendar_event_names([{"name": "美国未知指标", "name_en": "美国未知指标"}])

    assert result[0]["name_vi"] == "Chỉ báo chưa xác định của Hoa Kỳ"
    assert result[0]["name_en"] == "US Unknown Indicator"


def test_calendar_translation_uses_only_deepseek_for_uncached_chinese_labels(monkeypatch, tmp_path):
    from app.data_providers import economic_calendar_translation as translation

    class FakeLLM:
        def __init__(self, provider=None):
            assert provider == "deepseek"

        def is_configured(self, provider):
            assert provider.value == "deepseek"
            return True

        def call_llm_api(self, messages, **kwargs):
            assert kwargs["use_fallback"] is False
            assert kwargs["try_alternative_providers"] is False
            return json.dumps({"translations": [{
                "source": "美国未知指标",
                "vi": "Chỉ báo chưa xác định của Hoa Kỳ",
                "en": "US Unknown Indicator"
            }]}, ensure_ascii=False)

    monkeypatch.setattr(translation, "LLMService", FakeLLM)
    monkeypatch.setenv("ECONOMIC_CALENDAR_TRANSLATION_CACHE_PATH", str(tmp_path / "cache.json"))
    monkeypatch.setenv("ECONOMIC_CALENDAR_TRANSLATION_ENABLED", "true")

    result = translation.translate_calendar_event_names([{"name": "美国未知指标", "name_en": "美国未知指标"}])

    assert result[0]["name_vi"] == "Chỉ báo chưa xác định của Hoa Kỳ"
    assert result[0]["name_en"] == "US Unknown Indicator"


def test_calendar_translation_rejects_chinese_llm_output(monkeypatch, tmp_path):
    from app.data_providers import economic_calendar_translation as translation

    class FakeLLM:
        def __init__(self, provider=None):
            assert provider == "deepseek"

        def is_configured(self, provider):
            return True

        def call_llm_api(self, messages, **kwargs):
            return json.dumps({"translations": [{
                "source": "美国未知指标",
                "vi": "中文结果",
                "en": "中文结果"
            }]}, ensure_ascii=False)

    monkeypatch.setattr(translation, "LLMService", FakeLLM)
    monkeypatch.setenv("ECONOMIC_CALENDAR_TRANSLATION_CACHE_PATH", str(tmp_path / "cache.json"))

    result = translation.translate_calendar_event_names([{"name": "美国未知指标", "name_en": "美国未知指标"}])

    assert "name_vi" not in result[0]
    assert "name_en" not in result[0]

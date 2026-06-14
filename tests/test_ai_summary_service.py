from types import SimpleNamespace

import pytest

from wine_cellar.apps.wine.services.ai_summary import WineAISummaryService


class _FakeMessagesClient:
    def __init__(self, response, captured):
        self._response = response
        self._captured = captured

    def create(self, **kwargs):
        self._captured["kwargs"] = kwargs
        return self._response


class _FakeAnthropicClient:
    def __init__(self, response, captured):
        self.messages = _FakeMessagesClient(response, captured)


@pytest.mark.django_db
def test_refresh_summary_saves_text_and_sources(settings, monkeypatch, wine_factory):
    settings.ANTHROPIC_API_KEY = "test-key"
    settings.WINE_AI_SUMMARY_MODEL = "claude-sonnet-test"
    wine = wine_factory(
        user=None,
        household=None,
        name="Cited Wine",
        country="FR",
    )

    captured = {}
    response = SimpleNamespace(
        model="claude-sonnet-test",
        content=[
            SimpleNamespace(
                text=(
                    "A precise red from a classic appellation "
                    "with strong producer pedigree."
                ),
                citations=[
                    SimpleNamespace(
                        type="web_search_result_location",
                        title="Producer page",
                        url="https://example.com/producer",
                    ),
                    SimpleNamespace(
                        type="web_search_result_location",
                        title="Appellation guide",
                        url="https://example.com/appellation",
                    ),
                ],
            )
        ],
    )

    def fake_client(api_key):
        captured["api_key"] = api_key
        return _FakeAnthropicClient(response, captured)

    monkeypatch.setattr(
        "wine_cellar.apps.wine.services.ai_summary.anthropic.Anthropic",
        fake_client,
    )

    assert WineAISummaryService.refresh_summary(wine.pk) is True

    wine.refresh_from_db()
    assert wine.ai_summary.startswith("A precise red")
    assert wine.ai_summary_sources == [
        {"title": "Producer page", "url": "https://example.com/producer"},
        {"title": "Appellation guide", "url": "https://example.com/appellation"},
    ]
    assert wine.ai_summary_model == "claude-sonnet-test"
    assert captured["api_key"] == "test-key"
    assert captured["kwargs"]["tools"][0]["type"] == "web_search_20250305"
    assert "Cited Wine" in captured["kwargs"]["messages"][0]["content"]


@pytest.mark.django_db
def test_refresh_summary_skips_without_api_key(settings, wine_factory):
    settings.ANTHROPIC_API_KEY = ""
    wine = wine_factory(
        user=None,
        household=None,
        name="No Key Wine",
        country="FR",
    )
    wine.ai_summary = "Existing summary"
    wine.ai_summary_sources = [{"title": "Existing", "url": "https://example.com"}]
    wine.save(update_fields=["ai_summary", "ai_summary_sources"])

    assert WineAISummaryService.refresh_summary(wine.pk) is False

    wine.refresh_from_db()
    assert wine.ai_summary == "Existing summary"
    assert wine.ai_summary_sources == [
        {"title": "Existing", "url": "https://example.com"}
    ]

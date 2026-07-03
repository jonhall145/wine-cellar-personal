from types import SimpleNamespace

import pytest

from wine_cellar.apps.wine.services.ai_grapes import WineAIGrapeService


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
def test_refresh_grapes_links_existing_and_new_grapes(
    settings, monkeypatch, user, wine_factory, grape_factory
):
    settings.ANTHROPIC_API_KEY = "test-key"
    settings.WINE_AI_GRAPES_MODEL = "claude-haiku-test"
    wine = wine_factory(user=user)
    wine.grapes.clear()
    existing_grape = grape_factory(
        user=user,
        household=user.user_settings.active_household,
        name="Riesling",
    )

    captured = {}
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                text="GRAPES: riesling, cab sav\nCONFIDENCE: high",
            )
        ]
    )

    def fake_client(api_key):
        captured["api_key"] = api_key
        return _FakeAnthropicClient(response, captured)

    monkeypatch.setattr(
        "wine_cellar.apps.wine.services.ai_grapes.anthropic.Anthropic",
        fake_client,
    )

    assert WineAIGrapeService.refresh_grapes(wine.pk, include_images=False) is True

    wine.refresh_from_db()
    assert set(wine.grapes.values_list("name", flat=True)) == {
        "Riesling",
        "Cabernet Sauvignon",
    }
    assert captured["api_key"] == "test-key"
    assert captured["kwargs"]["model"] == "claude-haiku-test"
    assert "Wine Name" in captured["kwargs"]["messages"][0]["content"][0]["text"]
    assert wine.grapes.filter(pk=existing_grape.pk).exists()


@pytest.mark.django_db
def test_refresh_grapes_skips_without_api_key(
    settings, monkeypatch, user, wine_factory
):
    settings.ANTHROPIC_API_KEY = ""
    wine = wine_factory(user=user)
    wine.grapes.clear()

    monkeypatch.setattr(
        "wine_cellar.apps.wine.services.ai_grapes.anthropic.Anthropic",
        lambda api_key: (_ for _ in ()).throw(AssertionError("should not be called")),
    )

    assert WineAIGrapeService.refresh_grapes(wine.pk) is False

    wine.refresh_from_db()
    assert wine.grapes.count() == 0

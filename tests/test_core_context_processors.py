import pytest
from django.test import RequestFactory
from django.test.utils import override_settings

from wine_cellar.apps.core.context_processors import app_context


@pytest.mark.django_db
def test_app_context_defaults_to_wine():
    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["CELLAR_APP_TYPE"] == "wine"
    assert data["APP_NAME"] == "Wine Cellar"


@pytest.mark.django_db
@override_settings(CELLAR_APP_TYPE="whisky")
def test_app_context_whisky_switch_url_from_site_url(monkeypatch):
    monkeypatch.delenv("WINE_SITE_URL", raising=False)
    monkeypatch.delenv("WHISKY_SITE_URL", raising=False)
    monkeypatch.setenv("SITE_URL", "https://whisky.example.com")

    request = RequestFactory().get("/")
    data = app_context(request)

    assert data["CELLAR_APP_TYPE"] == "whisky"
    assert data["SWITCH_APP_URL"] == "https://wine.example.com"

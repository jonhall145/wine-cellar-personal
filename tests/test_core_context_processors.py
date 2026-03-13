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


@pytest.mark.django_db
def test_app_context_wine_has_all_keys():
    request = RequestFactory().get("/")
    data = app_context(request)
    expected_keys = {
        "CELLAR_APP_TYPE",
        "APP_NAME",
        "APP_ITEM_NAME",
        "APP_ITEM_NAME_PLURAL",
        "SWITCH_APP_URL",
        "SWITCH_APP_NAME",
        "SWITCH_APP_ICON",
    }
    assert set(data.keys()) == expected_keys


@pytest.mark.django_db
def test_app_context_wine_item_names():
    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["APP_ITEM_NAME"] == "wine"
    assert data["APP_ITEM_NAME_PLURAL"] == "wines"


@pytest.mark.django_db
@override_settings(CELLAR_APP_TYPE="whisky")
def test_app_context_whisky_item_names():
    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["APP_ITEM_NAME"] == "whisky"
    assert data["APP_ITEM_NAME_PLURAL"] == "whiskies"
    assert data["APP_NAME"] == "Whisky Cabinet"


@pytest.mark.django_db
@override_settings(CELLAR_APP_TYPE="whisky")
def test_app_context_whisky_switch_icon():
    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["SWITCH_APP_ICON"] == "fa-wine-bottle"
    assert data["SWITCH_APP_NAME"] == "Wine Cellar"


@pytest.mark.django_db
def test_app_context_wine_switch_icon():
    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["SWITCH_APP_ICON"] == "fa-whiskey-glass"
    assert data["SWITCH_APP_NAME"] == "Whisky Cabinet"


@pytest.mark.django_db
def test_app_context_wine_explicit_whisky_url(monkeypatch):
    monkeypatch.setenv("WHISKY_SITE_URL", "https://whisky.mycellar.com")
    monkeypatch.delenv("WINE_SITE_URL", raising=False)
    monkeypatch.delenv("SITE_URL", raising=False)

    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["SWITCH_APP_URL"] == "https://whisky.mycellar.com"


@pytest.mark.django_db
@override_settings(CELLAR_APP_TYPE="whisky")
def test_app_context_whisky_explicit_wine_url(monkeypatch):
    monkeypatch.setenv("WINE_SITE_URL", "https://wine.mycellar.com")
    monkeypatch.delenv("WHISKY_SITE_URL", raising=False)
    monkeypatch.delenv("SITE_URL", raising=False)

    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["SWITCH_APP_URL"] == "https://wine.mycellar.com"


@pytest.mark.django_db
def test_app_context_no_urls_set(monkeypatch):
    monkeypatch.delenv("WINE_SITE_URL", raising=False)
    monkeypatch.delenv("WHISKY_SITE_URL", raising=False)
    monkeypatch.delenv("SITE_URL", raising=False)

    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["SWITCH_APP_URL"] == ""


@pytest.mark.django_db
def test_app_context_wine_switch_url_from_site_url(monkeypatch):
    monkeypatch.delenv("WINE_SITE_URL", raising=False)
    monkeypatch.delenv("WHISKY_SITE_URL", raising=False)
    monkeypatch.setenv("SITE_URL", "https://wine.example.com")

    request = RequestFactory().get("/")
    data = app_context(request)
    assert data["SWITCH_APP_URL"] == "https://whisky.example.com"

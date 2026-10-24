from http import HTTPStatus

import pytest
from django.test import override_settings
from django.urls import reverse
from pytest_django.asserts import assertRedirects, assertTemplateUsed


@pytest.mark.django_db
def test_user_settings_page(client, user):
    client.force_login(user)
    r = client.get(reverse("user-settings"))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="settings.html")

    data = {
        "currency": "EUR",
        "notifications": True,
        "drink_window_notifications": "BO",
        "low_stock_notifications": "IA",
        "household_invitation_notifications": "IA",
        "price_alert_notifications": "NO",
        "reminder_enabled": True,
        "reminder_years_before": 0,
    }
    r = client.post(reverse("user-settings"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    assertRedirects(response=r, expected_url=reverse("user-settings"))
    user_settings = user.user_settings
    assert user_settings.currency == "EUR"
    assert user_settings.notifications

    data = {
        "currency": "EUR",
        "notifications": False,
        "drink_window_notifications": "EM",
        "low_stock_notifications": "NO",
        "household_invitation_notifications": "NO",
        "price_alert_notifications": "NO",
        "reminder_enabled": True,
        "reminder_years_before": 0,
    }
    r = client.post(reverse("user-settings"), data, follow=True)
    assert r.status_code == HTTPStatus.OK
    user_settings.refresh_from_db()
    assert user_settings.currency == "EUR"
    assert not user_settings.notifications
    assert user_settings.drink_window_notifications == "EM"


@pytest.mark.django_db
def test_user_signup_disabled(client, user):
    r = client.get(reverse("account_signup"))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="account/signup_closed.html")


@override_settings(ENABLE_SIGNUPS=True)
@pytest.mark.django_db
def test_user_signup_enabled(client, user):
    r = client.get(reverse("account_signup"))
    assert r.status_code == HTTPStatus.OK
    assertTemplateUsed(response=r, template_name="base.html")
    assertTemplateUsed(response=r, template_name="account/signup.html")

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from wine_cellar.apps.household.middleware import HouseholdMiddleware


def _make_middleware():
    return HouseholdMiddleware(lambda request: HttpResponse("ok"))


@pytest.mark.django_db
def test_middleware_allows_exempt_path(user):
    request = RequestFactory().get("/accounts/login/")
    request.user = user

    response = _make_middleware()(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_middleware_redirects_when_no_household(user_factory):
    user = user_factory()
    user.user_settings.active_household = None
    user.user_settings.save()
    user.household_memberships.all().delete()

    request = RequestFactory().get("/wine/")
    request.user = user

    response = _make_middleware()(request)

    assert response.status_code == 302


@pytest.mark.django_db
def test_middleware_assigns_membership_household(user_factory):
    user = user_factory()
    membership = user.household_memberships.first()
    user.user_settings.active_household = None
    user.user_settings.save()

    request = RequestFactory().get("/wine/")
    request.user = user

    response = _make_middleware()(request)

    assert response.status_code == 200
    user.user_settings.refresh_from_db()
    assert user.user_settings.active_household == membership.household

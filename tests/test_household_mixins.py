import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from wine_cellar.apps.household.mixins import (
    HouseholdContextMixin,
    RequireAdminMixin,
    RequireHouseholdMixin,
    RequireMemberMixin,
    RequireOwnerMixin,
)
from wine_cellar.apps.household.models import HouseholdRole


class BaseView(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("ok")


class DummyView(RequireHouseholdMixin, BaseView):
    pass


class DummyMemberView(RequireMemberMixin, BaseView):
    pass


class DummyAdminView(RequireAdminMixin, BaseView):
    pass


class DummyOwnerView(RequireOwnerMixin, BaseView):
    pass


def _add_messages(request):
    request.session = {}
    request._messages = FallbackStorage(request)


@pytest.mark.django_db
def test_household_context_role_helpers(user):
    mixin = HouseholdContextMixin()
    mixin.request = type("Request", (), {"user": user})()

    assert mixin.can_edit() is True
    assert mixin.can_manage_members() is True
    assert mixin.is_owner() is True
    assert mixin.has_role(HouseholdRole.MEMBER) is True
    assert mixin.has_role(HouseholdRole.ADMIN) is True


@pytest.mark.django_db
def test_require_household_redirects_without_active_household(user_factory):
    user = user_factory()
    user.user_settings.active_household = None
    user.user_settings.save()

    request = RequestFactory().get("/")
    request.user = user
    _add_messages(request)

    response = DummyView.as_view()(request)
    assert response.status_code == 302


@pytest.mark.django_db
def test_require_member_blocks_viewer(user):
    user.household_memberships.update(role=HouseholdRole.VIEWER)

    request = RequestFactory().get("/")
    request.user = user
    _add_messages(request)

    with pytest.raises(PermissionDenied):
        DummyMemberView.as_view()(request)


@pytest.mark.django_db
def test_require_admin_blocks_member(user):
    user.household_memberships.update(role=HouseholdRole.MEMBER)

    request = RequestFactory().get("/")
    request.user = user
    _add_messages(request)

    with pytest.raises(PermissionDenied):
        DummyAdminView.as_view()(request)


@pytest.mark.django_db
def test_require_owner_blocks_admin(user):
    user.household_memberships.update(role=HouseholdRole.ADMIN)

    request = RequestFactory().get("/")
    request.user = user
    _add_messages(request)

    with pytest.raises(PermissionDenied):
        DummyOwnerView.as_view()(request)

import pytest
from django.test import RequestFactory

from wine_cellar.apps.storage.filters import StorageItemFilter
from wine_cellar.apps.storage.models import StorageItem


@pytest.mark.django_db
def test_storage_item_filter_has_occasion(user, storage_item_factory):
    storage_item_factory(user=user, occasion="Birthday")
    storage_item_factory(user=user, occasion="")

    request = RequestFactory().get("/")
    request.user = user

    filt = StorageItemFilter(
        data={"has_occasion": "1"},
        queryset=StorageItem.objects.filter(user=user),
        request=request,
    )

    assert filt.qs.count() == 1
    assert filt.qs.first().occasion == "Birthday"


@pytest.mark.django_db
def test_storage_item_filter_no_occasion(user, storage_item_factory):
    storage_item_factory(user=user, occasion="Anniversary")
    storage_item_factory(user=user, occasion="")

    request = RequestFactory().get("/")
    request.user = user

    filt = StorageItemFilter(
        data={"has_occasion": "0"},
        queryset=StorageItem.objects.filter(user=user),
        request=request,
    )

    assert filt.qs.count() == 1
    assert filt.qs.first().occasion == ""


@pytest.mark.django_db
def test_storage_item_filter_sets_storage_queryset(user, storage_factory):
    storage = storage_factory(user=user)

    request = RequestFactory().get("/")
    request.user = user

    filt = StorageItemFilter(
        data={},
        queryset=StorageItem.objects.filter(user=user),
        request=request,
    )

    assert storage in filt.filters["storage"].queryset

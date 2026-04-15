import pytest
from django.urls import reverse

from wine_cellar.apps.whisky.forms import WhiskyForm, WhiskyStockAddForm


@pytest.mark.django_db
def test_whisky_form_storage_fields_use_native_select_widgets(user):
    form = WhiskyForm(user=user)

    assert form.fields["row"].widget.attrs["data-native-select"] == "true"
    assert form.fields["column"].widget.attrs["data-native-select"] == "true"


@pytest.mark.django_db
def test_whisky_edit_view_storage_fields_use_native_select_widgets(
    client, user, whisky_factory
):
    whisky = whisky_factory(user=user)
    client.force_login(user)
    response = client.get(reverse("whisky-edit", kwargs={"pk": whisky.pk}))
    form = response.context["form"]

    assert form.fields["row"].widget.attrs["data-native-select"] == "true"
    assert form.fields["column"].widget.attrs["data-native-select"] == "true"


@pytest.mark.django_db
def test_whisky_stock_add_form_storage_fields_use_native_select_widgets(user):
    form = WhiskyStockAddForm(user=user)

    assert form.fields["row"].widget.attrs["data-native-select"] == "true"
    assert form.fields["column"].widget.attrs["data-native-select"] == "true"

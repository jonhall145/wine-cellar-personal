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


@pytest.mark.django_db
def test_whisky_form_owner_choices_include_storage_item_owners(
    user, whisky_factory, whisky_storage_item_factory
):
    household = user.user_settings.active_household
    whisky_factory(user=user, household=household, owner="Walter")
    whisky_storage_item_factory(
        user=user,
        household=household,
        storage__user=user,
        storage__household=household,
        whisky__user=user,
        whisky__household=household,
        owner="Albert",
    )

    form = WhiskyForm(user=user)
    owner_choices = list(form.fields["owner"].widget.choices)

    assert ("Albert", "Albert") in owner_choices
    assert ("Walter", "Walter") in owner_choices

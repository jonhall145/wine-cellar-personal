"""Tests for wine_cellar.apps.core — shared views, forms, template tags, utils."""

import json
from datetime import date
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.urls import reverse

from wine_cellar.apps.core.forms import (
    BottleNoteForm,
    ReorderReminderForm,
    TomSelectMixin,
)
from wine_cellar.apps.core.templatetags.core_tags import _badge_impl, _rating_stars_impl
from wine_cellar.apps.core.utils import base64_to_uploaded_file
from wine_cellar.apps.wine.models import (
    BottleNote,
    DrinkRecord,
    ReorderReminder,
    Wishlist,
)

# -- TomSelectMixin tests --


class DummyForm(TomSelectMixin):
    """Minimal form-like class for testing TomSelectMixin."""

    def __init__(self):
        widget = type("A", (), {"attrs": {}})()
        self.fields = {"colour": type("W", (), {"widget": widget})()}


def test_tomselect_mixin_sets_config():
    form = DummyForm()
    form.set_tom_config("colour", create=True, max_items=5)
    config = json.loads(form.fields["colour"].widget.attrs["data-tom_config"])
    assert config["create"] is True
    assert config["maxItems"] == 5
    assert "items" not in config


def test_tomselect_mixin_items_included_when_truthy():
    form = DummyForm()
    form.set_tom_config("colour", items=["red"])
    config = json.loads(form.fields["colour"].widget.attrs["data-tom_config"])
    assert config["items"] == ["red"]


def test_tomselect_mixin_empty_list_excluded():
    """Empty list should NOT be added to config (preserves original behavior)."""
    form = DummyForm()
    form.set_tom_config("colour", items=[])
    config = json.loads(form.fields["colour"].widget.attrs["data-tom_config"])
    assert "items" not in config


def test_tomselect_mixin_none_excluded():
    form = DummyForm()
    form.set_tom_config("colour", items=None)
    config = json.loads(form.fields["colour"].widget.attrs["data-tom_config"])
    assert "items" not in config


def test_tomselect_mixin_placeholder():
    form = DummyForm()
    form.set_tom_config("colour", placeholder="Pick one")
    config = json.loads(form.fields["colour"].widget.attrs["data-tom_config"])
    assert config["placeholder"] == "Pick one"


def test_tomselect_mixin_max_options_unlimited():
    form = DummyForm()
    form.set_tom_config("colour", max_options=-1)
    config = json.loads(form.fields["colour"].widget.attrs["data-tom_config"])
    assert config["maxOptions"] is None


# -- BottleNoteForm / ReorderReminderForm tests --


def test_bottle_note_form_valid():
    form = BottleNoteForm(data={"note_date": "2025-01-15", "note": "Lovely nose."})
    assert form.is_valid()


def test_bottle_note_form_missing_note():
    form = BottleNoteForm(data={"note_date": "2025-01-15"})
    assert not form.is_valid()
    assert "note" in form.errors


def test_reorder_reminder_form_valid():
    form = ReorderReminderForm(data={"min_stock": 3})
    assert form.is_valid()


def test_reorder_reminder_form_zero_invalid():
    form = ReorderReminderForm(data={"min_stock": 0})
    assert not form.is_valid()


# -- rating_stars template tag tests --


def test_rating_stars_none():
    html = _rating_stars_impl(None)
    assert "rating-stars--empty" in html
    assert "—" in html


def test_rating_stars_zero():
    html = _rating_stars_impl(0)
    assert "star--filled" not in html
    assert html.count("fa-regular fa-star") == 3


def test_rating_stars_two():
    html = _rating_stars_impl(2)
    assert html.count("star--filled") == 2
    assert html.count("fa-regular fa-star") == 1


def test_rating_stars_max():
    html = _rating_stars_impl(3)
    assert html.count("star--filled") == 3
    assert "fa-regular fa-star" not in html


def test_rating_stars_clamped():
    html = _rating_stars_impl(99)
    assert html.count("star--filled") == 3


# -- badge helper tests --


CLASSES = {"RE": "red", "WH": "white"}
LABELS = {"RE": "Red", "WH": "White"}


def test_badge_renders_class_and_label():
    html = _badge_impl("RE", CLASSES, LABELS, "wine-type-badge")
    assert "wine-type-badge--red" in html
    assert "Red" in html


def test_badge_empty_code():
    assert _badge_impl("", CLASSES, LABELS, "wine-type-badge") == ""
    assert _badge_impl(None, CLASSES, LABELS, "wine-type-badge") == ""


def test_badge_unknown_code():
    html = _badge_impl("XX", CLASSES, LABELS, "wine-type-badge")
    assert "wine-type-badge" in html
    assert "XX" in html


# -- base64_to_uploaded_file tests --


def test_base64_to_uploaded_file():
    # 1x1 red JPEG
    import base64

    pixel = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b64 = base64.b64encode(pixel).decode()
    uploaded = base64_to_uploaded_file(b64, "test.jpg")
    assert uploaded.name == "test.jpg"
    assert uploaded.content_type == "image/jpeg"
    assert uploaded.size == len(pixel)


# -- Core view integration tests (wine mode) --


@pytest.mark.django_db
def test_wishlist_list_requires_login(client):
    r = client.get(reverse("wishlist-list"), follow=True)
    assert r.status_code == HTTPStatus.OK
    assert "login" in r.request["PATH_INFO"] or r.redirect_chain


@pytest.mark.django_db
def test_wishlist_list_view(client, user):
    client.force_login(user)
    household = user.user_settings.active_household
    Wishlist.objects.create(name="Burgundy", user=user, household=household, priority=3)
    r = client.get(reverse("wishlist-list"))
    assert r.status_code == HTTPStatus.OK
    assert len(r.context["wishlist_items"]) == 1


@pytest.mark.django_db
def test_wishlist_purchased_marks_item(client, user):
    client.force_login(user)
    household = user.user_settings.active_household
    item = Wishlist.objects.create(name="Barolo", user=user, household=household)
    r = client.post(reverse("wishlist-purchased", args=[item.pk]))
    assert r.status_code == HTTPStatus.FOUND
    item.refresh_from_db()
    assert item.purchased is True


@pytest.mark.django_db
def test_wishlist_delete_view(client, user):
    client.force_login(user)
    household = user.user_settings.active_household
    item = Wishlist.objects.create(name="Riesling", user=user, household=household)
    r = client.post(reverse("wishlist-delete", args=[item.pk]))
    assert r.status_code == HTTPStatus.FOUND
    assert not Wishlist.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_wishlist_delete_scoped_to_household(client, user_factory):
    """User cannot delete another household's wishlist item."""
    owner = user_factory()
    other = user_factory()
    household = owner.user_settings.active_household
    item = Wishlist.objects.create(name="Stolen", user=owner, household=household)
    client.force_login(other)
    r = client.post(reverse("wishlist-delete", args=[item.pk]))
    assert r.status_code == HTTPStatus.NOT_FOUND
    assert Wishlist.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_drink_history_view(client, user, wine_factory):
    client.force_login(user)
    hh = user.user_settings.active_household
    wine = wine_factory(user=user)
    DrinkRecord.objects.create(
        wine=wine,
        user=user,
        household=hh,
        date_consumed=date(2025, 1, 1),
    )
    r = client.get(reverse("drink-history"))
    assert r.status_code == HTTPStatus.OK
    assert len(r.context["drink_records"]) == 1


@pytest.mark.django_db
def test_drink_record_delete_view(client, user, wine_factory):
    client.force_login(user)
    hh = user.user_settings.active_household
    wine = wine_factory(user=user)
    record = DrinkRecord.objects.create(
        wine=wine,
        user=user,
        household=hh,
        date_consumed=date(2025, 1, 1),
    )
    r = client.post(reverse("drink-record-delete", args=[record.pk]))
    assert r.status_code == HTTPStatus.FOUND
    assert not DrinkRecord.objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_bottle_note_create_view(client, user, wine_factory, storage_item_factory):
    client.force_login(user)
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    si = storage_item_factory(wine=wine, storage=storage)
    r = client.post(
        reverse("bottle-note-add", args=[si.pk]),
        data={"note_date": "2025-06-01", "note": "Opening nicely."},
    )
    assert r.status_code == HTTPStatus.FOUND
    assert BottleNote.objects.filter(storage_item=si).exists()


@pytest.mark.django_db
def test_reorder_reminders_view(client, user, wine_factory):
    client.force_login(user)
    household = user.user_settings.active_household
    wine = wine_factory(user=user)
    ReorderReminder.objects.create(
        wine=wine, user=user, household=household, min_stock=2, is_active=True
    )
    r = client.get(reverse("reorder-reminders"))
    assert r.status_code == HTTPStatus.OK
    assert len(r.context["reminders"]) == 1


@pytest.mark.django_db
def test_reorder_reminder_create_view(client, user, wine_factory):
    client.force_login(user)
    wine = wine_factory(user=user)
    r = client.post(
        reverse("reorder-reminder-add", args=[wine.pk]),
        data={"min_stock": 3},
    )
    assert r.status_code == HTTPStatus.FOUND
    assert ReorderReminder.objects.filter(wine=wine, min_stock=3).exists()


@pytest.mark.django_db
def test_reorder_reminder_delete_view(client, user, wine_factory):
    client.force_login(user)
    household = user.user_settings.active_household
    wine = wine_factory(user=user)
    reminder = ReorderReminder.objects.create(
        wine=wine, user=user, household=household, min_stock=1, is_active=True
    )
    r = client.post(reverse("reorder-reminder-delete", args=[reminder.pk]))
    assert r.status_code == HTTPStatus.FOUND
    assert not ReorderReminder.objects.filter(pk=reminder.pk).exists()


@pytest.mark.django_db
def test_cellar_value_view(client, user, wine_factory, storage_item_factory):
    client.force_login(user)
    wine = wine_factory(user=user, country="FR")
    storage = user.storage_set.first()
    storage_item_factory(wine=wine, storage=storage, price=Decimal("25.00"))
    storage_item_factory(wine=wine, storage=storage, price=Decimal("30.00"))
    r = client.get(reverse("cellar-value"))
    assert r.status_code == HTTPStatus.OK
    assert r.context["total_bottles"] == 2
    assert r.context["total_value"] == 55


@pytest.mark.django_db
def test_cellar_value_excludes_deleted(
    client, user, wine_factory, storage_item_factory
):
    client.force_login(user)
    wine = wine_factory(user=user)
    storage = user.storage_set.first()
    si_args = dict(wine=wine, storage=storage, price=Decimal("10.00"))
    storage_item_factory(**si_args)
    storage_item_factory(**si_args, deleted=True)
    r = client.get(reverse("cellar-value"))
    assert r.status_code == HTTPStatus.OK
    assert r.context["total_bottles"] == 1
    assert r.context["total_value"] == 10

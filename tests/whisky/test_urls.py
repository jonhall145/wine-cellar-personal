import pytest
from django.urls import resolve, reverse

from wine_cellar.apps.whisky import views


@pytest.mark.parametrize(
    ("name", "args", "expected"),
    [
        ("whisky-edit", [1], "/whisky/edit/1/"),
        ("whisky-delete", [1], "/whisky/delete/1/"),
        ("whisky-scanned", ["abc123"], "/whisky/scan/abc123/"),
        ("whisky-merge-confirm", [1, 2], "/whisky/merge/1/into/2/"),
        ("stock-add", [1], "/stock/add/1/"),
        ("stock-delete", [1], "/stock/delete/1/"),
        ("stock-give", [1], "/stock/give/1/"),
        ("bottle-edit", [1], "/bottle/edit/1/"),
        ("drink-record-edit", [1], "/drink-history/edit/1/"),
        ("drink-record-delete", [1], "/drink-history/delete/1/"),
        ("wishlist-delete", [1], "/wishlist/delete/1/"),
        ("wishlist-purchased", [1], "/wishlist/purchased/1/"),
        ("reorder-reminder-add", [1], "/reorder/add/1/"),
        ("reorder-reminder-delete", [1], "/reorder/delete/1/"),
        ("bottle-note-add", [1], "/bottle/1/note/"),
        ("bottle-history", [1], "/bottle/1/history/"),
    ],
)
def test_whisky_reverse_uses_standardized_patterns(name, args, expected):
    assert reverse(name, args=args) == expected


@pytest.mark.parametrize(
    ("url", "expected_view_class"),
    [
        ("/whisky/1/edit/", views.WhiskyUpdateView),
        ("/whisky/1/delete/", views.WhiskyDeleteView),
        ("/whisky/scanned/abc123/", views.WhiskyScannedView),
        ("/whisky/1/merge/2/", views.WhiskyMergeConfirmView),
        ("/whisky/1/stock/add/", views.StorageItemAddView),
        ("/stock/1/delete/", views.StorageItemDeleteView),
        ("/stock/1/give/", views.StorageItemMarkGivenView),
        ("/stock/1/edit/", views.StorageItemUpdateView),
        ("/drink-record/1/edit/", views.DrinkRecordEditView),
        ("/drink-record/1/delete/", views.DrinkRecordDeleteView),
        ("/wishlist/1/delete/", views.WishlistDeleteView),
        ("/wishlist/1/purchased/", views.WishlistPurchasedView),
        ("/whisky/1/reorder/add/", views.ReorderReminderCreateView),
        ("/reorder/1/delete/", views.ReorderReminderDeleteView),
        ("/stock/1/note/add/", views.BottleNoteCreateView),
        ("/stock/1/history/", views.WhiskyBottleHistoryView),
    ],
)
def test_legacy_whisky_urls_still_resolve(url, expected_view_class):
    assert resolve(url).func.view_class is expected_view_class

import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from wine_cellar.apps.wine.models import Wishlist


@pytest.mark.django_db
class TestWishlistCreateView:
    def test_renders_form(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wishlist-add"))
        assert r.status_code == 200
        assertTemplateUsed(r, "core/wishlist_create.html")

    def test_create_with_extra_fields(self, client, user):
        client.force_login(user)
        data = {
            "name": "Special Reserve",
            "wine_type": "RE",
            "country": "FR",
            "subregion": "Bordeaux",
            "vintage": 2018,
            "priority": 1,
        }
        r = client.post(reverse("wishlist-add"), data=data, follow=True)
        assert r.status_code == 200
        wish = Wishlist.objects.filter(name="Special Reserve").first()
        assert wish is not None
        assert wish.wine_type == "RE"
        assert wish.country == "FR"
        assert wish.subregion == "Bordeaux"
        assert wish.vintage == 2018

    def test_create_minimal(self, client, user):
        client.force_login(user)
        data = {"name": "Simple Wish", "priority": 1}
        r = client.post(reverse("wishlist-add"), data=data, follow=True)
        assert r.status_code == 200
        wish = Wishlist.objects.filter(name="Simple Wish").first()
        assert wish is not None

    def test_create_saves_external_url(self, client, user):
        client.force_login(user)
        data = {
            "name": "Linked Wish",
            "priority": 2,
            "external_url": "https://example.com/wine",
        }
        r = client.post(reverse("wishlist-add"), data=data, follow=True)
        assert r.status_code == 200
        wish = Wishlist.objects.get(name="Linked Wish")
        assert wish.external_url == "https://example.com/wine"

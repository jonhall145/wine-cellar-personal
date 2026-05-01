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
            "external_url": "https://example.com/wines/special-reserve",
        }
        r = client.post(reverse("wishlist-add"), data=data, follow=True)
        assert r.status_code == 200
        wish = Wishlist.objects.filter(name="Special Reserve").first()
        assert wish is not None
        assert wish.wine_type == "RE"
        assert wish.country == "FR"
        assert wish.subregion == "Bordeaux"
        assert wish.vintage == 2018
        assert wish.external_url == "https://example.com/wines/special-reserve"

    def test_create_minimal(self, client, user):
        client.force_login(user)
        data = {"name": "Simple Wish", "priority": 1}
        r = client.post(reverse("wishlist-add"), data=data, follow=True)
        assert r.status_code == 200
        wish = Wishlist.objects.filter(name="Simple Wish").first()
        assert wish is not None

    def test_prefills_wine_create_from_wishlist(self, client, user):
        client.force_login(user)
        household = user.user_settings.active_household
        wish = Wishlist.objects.create(
            name="Birthday Burgundy",
            user=user,
            household=household,
            wine_type="RE",
            country="FR",
            subregion="Burgundy",
            vintage=2019,
            external_url="https://example.com/wines/birthday-burgundy",
            notes="Gift idea",
        )

        r = client.get(reverse("wine-add") + f"?wishlist_item={wish.pk}")

        assert r.status_code == 200
        form = r.context["form"]
        assert form.initial["name"] == "Birthday Burgundy"
        assert form.initial["country"] == "FR"
        assert 'name="price_url"' in r.content.decode()
        assert (
            form.initial["price_url"] == "https://example.com/wines/birthday-burgundy"
        )
        assert form.initial["comment"] == "Gift idea"

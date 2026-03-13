import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestBulkActionView:
    def test_unauthenticated_redirects(self, client):
        r = client.post(reverse("wine-bulk-action"), follow=True)
        assert r.status_code == 200
        assert "login" in r.request["PATH_INFO"]

    def test_get_not_allowed(self, client, user):
        client.force_login(user)
        r = client.get(reverse("wine-bulk-action"))
        assert r.status_code == 405

    def test_no_wines_selected(self, client, user):
        client.force_login(user)
        r = client.post(reverse("wine-bulk-action"), {"action": "delete"}, follow=True)
        assert r.status_code == 200

    def test_bulk_delete(self, client, user, wine_factory):
        wine1 = wine_factory(user=user)
        wine2 = wine_factory(user=user, name="Second Wine")
        client.force_login(user)
        r = client.post(
            reverse("wine-bulk-action"),
            {"action": "delete", "wine_ids": [wine1.pk, wine2.pk]},
            follow=True,
        )
        assert r.status_code == 200
        wine1.refresh_from_db()
        wine2.refresh_from_db()
        assert wine1.deleted is True
        assert wine2.deleted is True

    def test_bulk_update_drink_to(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(
            reverse("wine-bulk-action"),
            {
                "action": "update_drink_to",
                "wine_ids": [wine.pk],
                "drink_to_year": "2030",
            },
            follow=True,
        )
        assert r.status_code == 200
        wine.refresh_from_db()
        assert wine.drink_to == 2030

    def test_bulk_update_drink_to_invalid_year(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(
            reverse("wine-bulk-action"),
            {
                "action": "update_drink_to",
                "wine_ids": [wine.pk],
                "drink_to_year": "abc",
            },
            follow=True,
        )
        assert r.status_code == 200
        wine.refresh_from_db()
        assert wine.drink_to is None or wine.drink_to != "abc"

    def test_bulk_update_drink_to_no_year(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(
            reverse("wine-bulk-action"),
            {"action": "update_drink_to", "wine_ids": [wine.pk]},
            follow=True,
        )
        assert r.status_code == 200

    def test_unknown_action(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(
            reverse("wine-bulk-action"),
            {"action": "unknown", "wine_ids": [wine.pk]},
            follow=True,
        )
        assert r.status_code == 200

    def test_cannot_delete_other_users_wines(
        self, client, user, user_factory, wine_factory
    ):
        other = user_factory()
        wine = wine_factory(user=other)
        client.force_login(user)
        r = client.post(
            reverse("wine-bulk-action"),
            {"action": "delete", "wine_ids": [wine.pk]},
            follow=True,
        )
        assert r.status_code == 200
        wine.refresh_from_db()
        assert wine.deleted is False

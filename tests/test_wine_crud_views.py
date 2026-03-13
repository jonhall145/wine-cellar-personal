import pytest
from django.urls import reverse

from wine_cellar.apps.wine.models import Collection, Wine


@pytest.mark.django_db
class TestWineCollections:
    def test_add_to_existing_collection(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        household = wine.household
        collection = Collection.objects.create(
            name="Favorites", user=user, household=household
        )
        client.force_login(user)
        r = client.post(
            reverse("wine-collection-add", kwargs={"pk": wine.pk}),
            {"collection_id": collection.pk},
            follow=True,
        )
        assert r.status_code == 200
        assert wine in collection.wines.all()

    def test_create_new_collection(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(
            reverse("wine-collection-add", kwargs={"pk": wine.pk}),
            {"new_collection_name": "New Collection"},
            follow=True,
        )
        assert r.status_code == 200
        collection = Collection.objects.filter(name="New Collection").first()
        assert collection is not None
        assert wine in collection.wines.all()

    def test_remove_from_collection(self, client, user, wine_factory):
        wine = wine_factory(user=user)
        household = wine.household
        collection = Collection.objects.create(
            name="Remove Test", user=user, household=household
        )
        collection.wines.add(wine)
        client.force_login(user)
        r = client.post(
            reverse(
                "wine-collection-remove",
                kwargs={"pk": wine.pk, "collection_pk": collection.pk},
            ),
            follow=True,
        )
        assert r.status_code == 200
        assert wine not in collection.wines.all()

    def test_add_with_no_collection(self, client, user, wine_factory):
        """No collection_id and no new_collection_name — should still redirect."""
        wine = wine_factory(user=user)
        client.force_login(user)
        r = client.post(
            reverse("wine-collection-add", kwargs={"pk": wine.pk}),
            {},
            follow=True,
        )
        assert r.status_code == 200


@pytest.mark.django_db
class TestWineMerge:
    def test_merge_view_renders(self, client, user, wine_factory):
        wine1 = wine_factory(user=user, name="Wine A")
        wine2 = wine_factory(user=user, name="Wine B")
        client.force_login(user)
        r = client.get(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": wine2.pk, "primary_pk": wine1.pk},
            )
        )
        assert r.status_code == 200

    def test_merge_wines(self, client, user, wine_factory, storage_item_factory):
        wine1 = wine_factory(user=user, name="Keep Wine")
        wine2 = wine_factory(user=user, name="Merge Wine")
        wine2_pk = wine2.pk
        storage = user.storage_set.first()
        storage_item_factory(wine=wine2, storage=storage)
        client.force_login(user)
        r = client.post(
            reverse(
                "wine-merge-confirm",
                kwargs={"pk": wine2.pk, "primary_pk": wine1.pk},
            ),
            follow=True,
        )
        assert r.status_code == 200
        # wine2 should be soft-deleted (deleted=True)
        wine2_after = Wine.objects.filter(pk=wine2_pk).first()
        if wine2_after:
            assert wine2_after.deleted is True

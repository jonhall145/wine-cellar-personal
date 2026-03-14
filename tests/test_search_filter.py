import pytest
from django.test import RequestFactory

from wine_cellar.apps.wine.filters import WineFilter
from wine_cellar.apps.wine.models import BottleNote, DrinkRecord, Wine


@pytest.mark.django_db
class TestWineSearchFilter:
    def _filter(self, user, **params):
        request = RequestFactory().get("/")
        request.user = user
        return WineFilter(
            data=params,
            queryset=Wine.objects.filter(user=user),
            request=request,
        )

    def test_search_by_name(self, user, wine_factory):
        wine = wine_factory(user=user, name="Château Margaux")
        wine_factory(user=user, name="Riesling")

        filt = self._filter(user, search="Margaux")
        assert wine in filt.qs
        assert filt.qs.count() == 1

    def test_search_by_comment(self, user, wine_factory):
        wine = wine_factory(user=user, comment="lovely blackcurrant finish")
        wine_factory(user=user, comment="dry and mineral")

        filt = self._filter(user, search="blackcurrant")
        assert wine in filt.qs
        assert filt.qs.count() == 1

    def test_search_by_subregion(self, user, wine_factory):
        wine = wine_factory(user=user, subregion="Pauillac")
        wine_factory(user=user, subregion="Barossa Valley")

        filt = self._filter(user, search="Pauillac")
        assert wine in filt.qs
        assert filt.qs.count() == 1

    def test_search_by_tasting_notes(self, user, wine_factory):
        wine = wine_factory(user=user)
        DrinkRecord.objects.create(
            wine=wine,
            user=user,
            household=wine.household,
            date_consumed="2025-01-01",
            tasting_notes="Incredible cherry and tobacco aromas",
        )
        other = wine_factory(user=user)
        DrinkRecord.objects.create(
            wine=other,
            user=user,
            household=other.household,
            date_consumed="2025-01-01",
            tasting_notes="Light and citrusy",
        )

        filt = self._filter(user, search="tobacco")
        assert wine in filt.qs
        assert other not in filt.qs

    def test_search_by_bottle_note(self, user, wine_factory, storage_item_factory):
        wine = wine_factory(user=user)
        si = storage_item_factory(
            wine=wine,
            storage__user=user,
            storage__household=wine.household,
        )
        BottleNote.objects.create(
            storage_item=si,
            user=user,
            household=wine.household,
            note_date="2025-06-01",
            note="Opening up nicely after decanting",
        )
        other = wine_factory(user=user)

        filt = self._filter(user, search="decanting")
        assert wine in filt.qs
        assert other not in filt.qs

    def test_search_case_insensitive(self, user, wine_factory):
        wine = wine_factory(user=user, name="Barossa Shiraz")

        filt = self._filter(user, search="barossa")
        assert wine in filt.qs

    def test_search_empty_returns_all(self, user, wine_factory):
        wine_factory(user=user)
        wine_factory(user=user)

        filt = self._filter(user, search="")
        assert filt.qs.count() == 2

    def test_search_no_duplicates(self, user, wine_factory):
        """A wine matching multiple fields should appear only once."""
        wine = wine_factory(user=user, name="Cherry Wine", comment="cherry jam finish")

        filt = self._filter(user, search="cherry")
        assert list(filt.qs).count(wine) == 1

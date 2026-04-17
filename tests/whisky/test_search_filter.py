import json
import os

import pytest

if os.environ.get("CELLAR_APP_TYPE") == "whisky":
    from django.test import RequestFactory

    from wine_cellar.apps.whisky.filters import WhiskyFilter, WhiskyStorageItemFilter
    from wine_cellar.apps.whisky.models import (
        Whisky,
        WhiskyBottleNote,
        WhiskyDrinkRecord,
        WhiskyStorageItem,
    )

    @pytest.mark.django_db
    class TestWhiskySearchFilter:
        def _filter(self, user, **params):
            params.setdefault("has_stock", "0")
            params.setdefault("order", "created")
            request = RequestFactory().get("/")
            request.user = user
            return WhiskyFilter(
                data=params,
                queryset=Whisky.objects.filter(user=user),
                request=request,
            )

        def test_search_by_name(self, user, whisky_factory):
            whisky = whisky_factory(user=user, name="Lagavulin 16")
            whisky_factory(user=user, name="Glenfiddich 12")

            filt = self._filter(user, search="Lagavulin")
            assert whisky in filt.qs
            assert filt.qs.count() == 1

        def test_search_by_comment(self, user, whisky_factory):
            whisky = whisky_factory(user=user, comment="rich peat smoke and iodine")
            whisky_factory(user=user, comment="light and fruity")

            filt = self._filter(user, search="iodine")
            assert whisky in filt.qs
            assert filt.qs.count() == 1

        def test_search_by_cask_type(self, user, whisky_factory):
            whisky = whisky_factory(user=user, cask_type="Oloroso Sherry Butt")
            whisky_factory(user=user, cask_type="Bourbon Barrel")

            filt = self._filter(user, search="Oloroso")
            assert whisky in filt.qs
            assert filt.qs.count() == 1

        def test_search_by_bottler_series(self, user, whisky_factory):
            whisky = whisky_factory(user=user, bottler_series="Connoisseurs Choice")
            whisky_factory(user=user, bottler_series="")

            filt = self._filter(user, search="Connoisseurs")
            assert whisky in filt.qs
            assert filt.qs.count() == 1

        def test_search_by_tasting_notes(self, user, whisky_factory):
            whisky = whisky_factory(user=user)
            WhiskyDrinkRecord.objects.create(
                whisky=whisky,
                user=user,
                household=whisky.household,
                date_consumed="2025-01-01",
                tasting_notes="Bonfire smoke and dark chocolate",
            )
            other = whisky_factory(user=user)
            WhiskyDrinkRecord.objects.create(
                whisky=other,
                user=user,
                household=other.household,
                date_consumed="2025-01-01",
                tasting_notes="Vanilla and honeycomb",
            )

            filt = self._filter(user, search="bonfire")
            assert whisky in filt.qs
            assert other not in filt.qs

        def test_search_by_bottle_note(
            self, user, whisky_factory, whisky_storage_item_factory
        ):
            whisky = whisky_factory(user=user)
            si = whisky_storage_item_factory(
                whisky=whisky,
                storage__user=user,
                storage__household=whisky.household,
            )
            WhiskyBottleNote.objects.create(
                storage_item=si,
                user=user,
                household=whisky.household,
                note_date="2025-06-01",
                note="Opened for Burns Night supper",
            )
            other = whisky_factory(user=user)

            filt = self._filter(user, search="Burns Night")
            assert whisky in filt.qs
            assert other not in filt.qs

        def test_search_no_duplicates(self, user, whisky_factory):
            """A whisky matching multiple fields should appear only once."""
            whisky = whisky_factory(
                user=user, name="Smoky Dram", comment="very smoky finish"
            )

            filt = self._filter(user, search="smoky")
            assert list(filt.qs).count(whisky) == 1

        def test_owner_dropdown_uses_unlimited_tomselect_options(
            self, user, whisky_factory
        ):
            whisky_factory(user=user, owner="Alice")

            filt = self._filter(user)
            tom_config = json.loads(
                filt.form.fields["owner"].widget.attrs["data-tom_config"]
            )

            assert tom_config["maxOptions"] is None

        def test_rating_filter_supports_multiple_selected_ratings(
            self, user, whisky_factory
        ):
            zero_star = whisky_factory(user=user, rating=0)
            one_star = whisky_factory(user=user, rating=1)
            two_star = whisky_factory(user=user, rating=2)

            filt = self._filter(user, rating=["0", "1"], has_stock="0", order="created")

            assert list(filt.qs) == [zero_star, one_star]
            assert two_star not in filt.qs

    @pytest.mark.django_db
    class TestWhiskyStorageItemFilter:
        def _create_storage_item(self, user, whisky_storage_item_factory, **kwargs):
            household = user.user_settings.active_household
            return whisky_storage_item_factory(
                user=user,
                household=household,
                storage__user=user,
                storage__household=household,
                whisky__user=user,
                whisky__household=household,
                **kwargs,
            )

        def _filter(self, user, **params):
            request = RequestFactory().get("/")
            request.user = user
            return WhiskyStorageItemFilter(
                data=params,
                queryset=WhiskyStorageItem.objects.filter(
                    household=user.user_settings.active_household
                ),
                request=request,
            )

        def test_owner_filter(self, user, whisky_storage_item_factory):
            self._create_storage_item(user, whisky_storage_item_factory, owner="Alice")
            self._create_storage_item(user, whisky_storage_item_factory, owner="Bob")

            filt = self._filter(user, owner="Alice")
            assert filt.qs.count() == 1
            assert filt.qs.first().owner == "Alice"

        def test_owner_dropdown_uses_unlimited_tomselect_options(
            self, user, whisky_storage_item_factory
        ):
            self._create_storage_item(user, whisky_storage_item_factory, owner="Alice")

            filt = self._filter(user)
            tom_config = json.loads(
                filt.form.fields["owner"].widget.attrs["data-tom_config"]
            )

            assert tom_config["maxOptions"] is None

        def test_show_used_default_excludes_deleted(
            self, user, whisky_storage_item_factory
        ):
            self._create_storage_item(user, whisky_storage_item_factory)
            self._create_storage_item(user, whisky_storage_item_factory, deleted=True)

            filt = self._filter(user)
            assert filt.qs.count() == 1
            assert filt.qs.first().deleted is False

        def test_show_used_includes_deleted(self, user, whisky_storage_item_factory):
            self._create_storage_item(user, whisky_storage_item_factory)
            self._create_storage_item(user, whisky_storage_item_factory, deleted=True)

            filt = self._filter(user, show_used="1")
            assert filt.qs.count() == 2

from django.views.generic import TemplateView

from wine_cellar.apps.core.views import (
    BaseBottleNoteCreateView,
    BaseDrinkRecordCreateView,
    BaseDrinkRecordDeleteView,
    BaseDrinkRecordEditView,
    BaseDrinkRecordListView,
    BaseJourneyTimelineView,
)
from wine_cellar.apps.household.mixins import RequireHouseholdMixin
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.models import BottleNote, DrinkRecord, Wine


class DrinkRecordCreateView(BaseDrinkRecordCreateView):
    template_name = "core/drink_record_create.html"
    beverage_model = Wine
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import DrinkRecordForm

        return DrinkRecordForm


class DrinkRecordListView(BaseDrinkRecordListView):
    template_name = "core/drink_record_list.html"
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"
    beverage_icon = "wine-glass"


class JourneyTimelineView(BaseJourneyTimelineView):
    template_name = "core/journey_timeline.html"
    storage_item_model = StorageItem
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"
    beverage_icon = "wine-glass"


class DrinkRecordEditView(BaseDrinkRecordEditView):
    template_name = "core/drink_record_edit.html"
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import DrinkRecordForm

        return DrinkRecordForm


class DrinkRecordDeleteView(BaseDrinkRecordDeleteView):
    model = DrinkRecord
    template_name = "drink_record_confirm_delete.html"


class BottleNoteCreateView(BaseBottleNoteCreateView):
    template_name = "core/bottle_note_create.html"
    storage_item_model = StorageItem
    note_model = BottleNote
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"


class DrinkingWindowAlertsView(RequireHouseholdMixin, TemplateView):
    template_name = "drinking_window_alerts.html"

    def get_context_data(self, **kwargs):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkingWindowAlert

        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)

        alerts = DrinkingWindowAlert.objects.filter(
            household=household, is_read=False
        ).select_related("wine")

        current_year = date.today().year

        upcoming_wines = (
            Wine.objects.filter(
                household=household,
                drink_to__isnull=False,
                drink_to__gt=0,
                drink_to__gte=current_year,
                drink_to__lte=current_year + 1,
            )
            .filter(storageitem__deleted=False)
            .distinct()
        )

        overdue_wines = (
            Wine.objects.filter(
                household=household,
                drink_to__isnull=False,
                drink_to__gt=0,
                drink_to__lt=current_year,
            )
            .filter(storageitem__deleted=False)
            .distinct()
        )

        context.update(
            {
                "alerts": alerts,
                "upcoming_wines": upcoming_wines,
                "overdue_wines": overdue_wines,
            }
        )
        return context

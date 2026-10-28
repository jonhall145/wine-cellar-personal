from wine_cellar.apps.core.views import (
    BaseReorderReminderCreateView,
    BaseReorderReminderDeleteView,
    BaseReorderRemindersView,
)
from wine_cellar.apps.wine.models import ReorderReminder, Wine
from wine_cellar.apps.wine.services import WineReminderService


class ReorderRemindersView(BaseReorderRemindersView):
    template_name = "core/reorder_reminders.html"
    reminder_model = ReorderReminder
    reminder_service = WineReminderService
    beverage_fk_name = "wine"
    stock_reverse_path = "wine__storageitem"
    beverage_icon = "wine-bottle"


class ReorderReminderCreateView(BaseReorderReminderCreateView):
    template_name = "core/reorder_reminder_create.html"
    beverage_model = Wine
    reminder_model = ReorderReminder
    reminder_service = WineReminderService
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"


class ReorderReminderDeleteView(BaseReorderReminderDeleteView):
    model = ReorderReminder
    template_name = "reorder_reminder_confirm_delete.html"

from wine_cellar.apps.core.views import (
    BaseReorderReminderCreateView,
    BaseReorderReminderDeleteView,
)
from wine_cellar.apps.wine.models import ReorderReminder, Wine


class ReorderReminderCreateView(BaseReorderReminderCreateView):
    template_name = "core/reorder_reminder_create.html"
    beverage_model = Wine
    reminder_model = ReorderReminder
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"


class ReorderReminderDeleteView(BaseReorderReminderDeleteView):
    model = ReorderReminder
    template_name = "reorder_reminder_confirm_delete.html"

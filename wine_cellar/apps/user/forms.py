from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.user.models import UserSettings


class UserSettingsForm(ModelForm):

    class Meta:
        model = UserSettings
        fields = [
            "language",
            "currency",
            "notifications",
            "reminder_enabled",
            "reminder_years_before",
        ]
        help_texts = {
            "language": _("The language the site is displayed in."),
            "currency": _("The default currency used for the price of a wine."),
            "notifications": _("Receive email notifications."),
            "reminder_enabled": _(
                "Receive reminders when wines approach their drink-by date."
            ),
            "reminder_years_before": _(
                "How many years before the drink-by date to start reminding."
            ),
        }

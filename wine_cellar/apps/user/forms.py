from django.forms import ModelForm

from wine_cellar.apps.user.models import UserSettings


class UserSettingsForm(ModelForm):

    class Meta:
        model = UserSettings
        fields = [
            "currency",
            "notifications",
            "reminder_enabled",
            "reminder_years_before",
        ]
        help_texts = {
            "currency": "The default currency used for the price of a wine.",
            "notifications": "Receive email notifications.",
            "reminder_enabled": (
                "Receive reminders when wines approach their drink-by date."
            ),
            "reminder_years_before": (
                "How many years before the drink-by date to start reminding."
            ),
        }

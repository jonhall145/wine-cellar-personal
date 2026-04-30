from django.forms import ModelForm

from wine_cellar.apps.user.models import UserSettings


class UserSettingsForm(ModelForm):

    class Meta:
        model = UserSettings
        fields = [
            "currency",
            "notifications",
            "drink_window_notifications",
            "low_stock_notifications",
            "household_invitation_notifications",
            "price_alert_notifications",
            "reminder_enabled",
            "reminder_years_before",
        ]
        help_texts = {
            "currency": "The default currency used for the price of a wine.",
            "notifications": "Enable or disable notifications globally.",
            "drink_window_notifications": (
                "Pick email, in-app, both, or none for drink window reminders."
            ),
            "low_stock_notifications": (
                "Pick email, in-app, both, or none for low stock reminders."
            ),
            "household_invitation_notifications": (
                "Pick email, in-app, both, or none for household invitations."
            ),
            "price_alert_notifications": (
                "Choose how future price alerts should be delivered."
            ),
            "reminder_enabled": (
                "Receive reminders when wines approach their drink-by date."
            ),
            "reminder_years_before": (
                "How many years before the drink-by date to start reminding."
            ),
        }

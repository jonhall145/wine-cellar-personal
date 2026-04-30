from django import forms
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


class UserBackupImportForm(forms.Form):
    backup_file = forms.FileField(
        label="Backup file",
        help_text="Upload a backup JSON file exported from this app.",
    )
    confirm_replace = forms.BooleanField(
        label="Replace current cellar data",
        help_text=(
            "This will overwrite the current household's wines or whiskies,"
            " bottles, notes, and history."
        ),
    )

    def clean_backup_file(self):
        backup_file = self.cleaned_data["backup_file"]
        if not backup_file.name.lower().endswith(".json"):
            raise forms.ValidationError("Backup files must be JSON exports.")
        return backup_file

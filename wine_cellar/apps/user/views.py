from typing import TYPE_CHECKING

from django.conf import settings
from django.urls import reverse_lazy
from django.utils import translation
from django.views.generic import UpdateView

from wine_cellar.apps.user.forms import UserSettingsForm
from wine_cellar.apps.user.models import UserSettings

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class UserSettingsView(UpdateView):
    template_name = "settings.html"
    form_class = UserSettingsForm
    success_url = reverse_lazy("user-settings")

    def form_valid(self, form):
        response = super().form_valid(form)
        user_language = form.cleaned_data["language"]
        translation.activate(user_language)
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user_language)
        return response

    def get_object(self, queryset=None):
        user = self.request.user
        return get_user_settings(user)  # type: ignore[arg-type]


def get_user_settings(user: "AbstractUser") -> UserSettings:
    """Get or create user settings, ensuring persistence."""
    user_settings, _ = UserSettings.objects.get_or_create(user=user)
    return user_settings

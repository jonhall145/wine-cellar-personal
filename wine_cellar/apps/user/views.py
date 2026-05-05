from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, UpdateView, View

from wine_cellar.apps.household.mixins import RequireAdminMixin, RequireHouseholdMixin
from wine_cellar.apps.user.backup import (
    BackupImportError,
    build_backup_response,
    restore_backup_file,
)
from wine_cellar.apps.user.forms import UserBackupImportForm, UserSettingsForm
from wine_cellar.apps.user.models import InAppNotificationStatus, UserSettings
from wine_cellar.apps.user.notifications import get_notification_summary

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class UserSettingsView(LoginRequiredMixin, UpdateView):
    template_name = "settings.html"
    form_class = UserSettingsForm
    success_url = reverse_lazy("user-settings")

    def get_object(self, queryset=None):
        user = self.request.user
        return get_user_settings(user)  # type: ignore[arg-type]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["backup_import_form"] = kwargs.get(
            "backup_import_form",
            UserBackupImportForm(),
        )
        context["backup_export_url"] = reverse_lazy("user-backup-export")
        context["backup_import_url"] = reverse_lazy("user-backup-import")
        context["active_household"] = get_active_household(self.request.user)
        return context


class UserBackupExportView(LoginRequiredMixin, RequireHouseholdMixin, View):
    def get(self, request, *args, **kwargs):
        household = get_active_household(request.user)
        try:
            return build_backup_response(request.user, household)
        except BackupImportError as exc:
            messages.error(request, str(exc))
            return redirect("user-settings")


class UserBackupImportView(LoginRequiredMixin, RequireAdminMixin, View):
    def post(self, request, *args, **kwargs):
        form = UserBackupImportForm(request.POST, request.FILES)
        if not form.is_valid():
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect("user-settings")
        if not form.cleaned_data.get("confirm_replace"):
            messages.error(request, "You must confirm data replacement.")
            return redirect("user-settings")

        try:
            result = restore_backup_file(
                form.cleaned_data["backup_file"],
                user=request.user,
                household=get_active_household(request.user),
            )
        except BackupImportError as exc:
            messages.error(request, str(exc))
            return redirect("user-settings")

        beverage_label = "whiskies" if result["app_type"] == "whisky" else "wines"
        messages.success(
            request,
            "Backup restored: "
            f"{result['beverages']} {beverage_label}, "
            f"{result['bottles']} bottles, and "
            f"{result['storages']} storages.",
        )
        return redirect("user-settings")


def get_user_settings(user: "AbstractUser") -> UserSettings:
    """Get or create user settings, with per-request caching on user object."""
    if not hasattr(user, "_cached_settings"):
        user._cached_settings, _ = UserSettings.objects.get_or_create(user=user)
    return user._cached_settings


def get_active_household(user: "AbstractUser"):
    """Get the user's active household, with per-request caching."""
    if not hasattr(user, "_cached_household"):
        settings = get_user_settings(user)
        user._cached_household = settings.active_household
    return user._cached_household


class NotificationCentreView(LoginRequiredMixin, TemplateView):
    template_name = "core/notifications.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_notification_summary(self.request))
        return context


class BaseNotificationStatusUpdateView(LoginRequiredMixin, View):
    action = None
    allowed_notification_types = {
        "drink_window",
        "low_stock",
        "household_invitation",
        "price_alert",
    }

    def post(self, request, *args, **kwargs):
        notification_key = (request.POST.get("notification_key") or "").strip()
        notification_type = (request.POST.get("notification_type") or "").strip()
        redirect_to = (request.POST.get("next") or reverse("notifications")).strip()
        if (
            not notification_key
            or len(notification_key) > 120
            or notification_type not in self.allowed_notification_types
        ):
            return redirect(redirect_to or reverse("notifications"))

        status, _ = InAppNotificationStatus.objects.get_or_create(
            user=request.user,
            notification_key=notification_key,
            defaults={
                "household": get_active_household(request.user),
                "notification_type": notification_type,
            },
        )
        status.notification_type = notification_type
        status.household = status.household or get_active_household(request.user)
        status.is_read = True
        status.read_at = status.read_at or timezone.now()
        if self.action == "dismiss":
            status.dismissed_at = timezone.now()
        status.save()
        return redirect(redirect_to or reverse("notifications"))


class NotificationMarkReadView(BaseNotificationStatusUpdateView):
    action = "read"


class NotificationDismissView(BaseNotificationStatusUpdateView):
    action = "dismiss"

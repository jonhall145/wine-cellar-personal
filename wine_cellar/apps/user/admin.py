from django.contrib import admin

from wine_cellar.apps.user.models import InAppNotificationStatus, UserSettings


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "currency", "notifications", "drink_window_notifications")
    list_filter = ("currency", "notifications")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user",)


@admin.register(InAppNotificationStatus)
class InAppNotificationStatusAdmin(admin.ModelAdmin):
    list_display = ("user", "notification_type", "is_read", "dismissed_at")
    list_filter = ("notification_type", "is_read")
    search_fields = ("user__username", "notification_key")

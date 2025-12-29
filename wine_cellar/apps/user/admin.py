from django.contrib import admin

from wine_cellar.apps.user.models import UserSettings


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "language", "currency", "notifications")
    list_filter = ("language", "currency", "notifications")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user",)

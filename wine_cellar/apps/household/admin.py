from django.contrib import admin

from wine_cellar.apps.household.models import (
    Household,
    HouseholdInvitation,
    HouseholdMembership,
    HouseholdSettings,
)


class HouseholdMembershipInline(admin.TabularInline):
    model = HouseholdMembership
    extra = 0
    raw_id_fields = ["user", "invited_by"]


class HouseholdSettingsInline(admin.StackedInline):
    model = HouseholdSettings
    can_delete = False


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ["name", "get_member_count", "created", "modified"]
    search_fields = ["name"]
    inlines = [HouseholdMembershipInline, HouseholdSettingsInline]


@admin.register(HouseholdMembership)
class HouseholdMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "household", "role", "joined"]
    list_filter = ["role", "household"]
    search_fields = ["user__username", "household__name"]
    raw_id_fields = ["user", "household", "invited_by"]


@admin.register(HouseholdInvitation)
class HouseholdInvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "household", "role", "status", "expires", "created"]
    list_filter = ["status", "role", "household"]
    search_fields = ["email", "household__name"]
    raw_id_fields = ["household", "invited_by"]
    readonly_fields = ["token"]


@admin.register(HouseholdSettings)
class HouseholdSettingsAdmin(admin.ModelAdmin):
    list_display = ["household", "language", "currency", "notifications"]
    list_filter = ["language", "currency"]
    search_fields = ["household__name"]
    raw_id_fields = ["household"]

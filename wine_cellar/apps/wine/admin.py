from django.contrib import admin

from wine_cellar.apps.wine.models import (
    Attribute,
    FoodPairing,
    Grape,
    Size,
    Source,
    Vineyard,
    Wine,
)


@admin.register(Wine)
class WineAdmin(admin.ModelAdmin):
    list_display = ["name", "barcode", "user", "household"]
    list_filter = ["household", "user"]
    fields = ["name", "barcode", "user", "household"]


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "household"]
    list_filter = ["household", "user"]
    fields = ["name", "user", "household"]


@admin.register(Grape)
class GrapeAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "household"]
    list_filter = ["household", "user"]
    fields = ["name", "user", "household"]


@admin.register(Vineyard)
class VineyardAdmin(admin.ModelAdmin):
    list_display = ["name", "country", "user", "household"]
    list_filter = ["household", "user"]
    fields = ["name", "website", "country", "region", "user", "household"]


@admin.register(FoodPairing)
class FoodPairingAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "household"]
    list_filter = ["household", "user"]
    fields = ["name", "user", "household"]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "household"]
    list_filter = ["household", "user"]
    fields = ["name", "user", "household"]


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "household"]
    list_filter = ["household", "user"]
    fields = ["name", "user", "household"]

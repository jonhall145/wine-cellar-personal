from django.contrib import admin

from wine_cellar.apps.whisky.models import (
    Bottler,
    CaskHistory,
    Distillery,
    Whisky,
    WhiskyBarcode,
    WhiskyImage,
    WhiskyRegion,
    WhiskyStorageItem,
)


class CaskHistoryInline(admin.TabularInline):
    model = CaskHistory
    extra = 1


@admin.register(WhiskyRegion)
class WhiskyRegionAdmin(admin.ModelAdmin):
    list_display = ["name", "country", "order"]
    ordering = ["order"]


@admin.register(Distillery)
class DistilleryAdmin(admin.ModelAdmin):
    list_display = ["name", "region", "status", "founded_year", "owner"]
    list_filter = ["region", "status"]
    search_fields = ["name", "owner"]


@admin.register(Bottler)
class BottlerAdmin(admin.ModelAdmin):
    list_display = ["name", "short_name", "country"]
    search_fields = ["name"]


@admin.register(Whisky)
class WhiskyAdmin(admin.ModelAdmin):
    list_display = ["name", "whisky_type", "distillery", "age_statement", "abv", "user"]
    list_filter = ["whisky_type", "peated_level", "region"]
    search_fields = ["name", "distillery__name"]
    inlines = [CaskHistoryInline]


@admin.register(WhiskyImage)
class WhiskyImageAdmin(admin.ModelAdmin):
    list_display = ["whisky", "image_type", "is_primary"]


@admin.register(WhiskyBarcode)
class WhiskyBarcodeAdmin(admin.ModelAdmin):
    list_display = ["barcode", "whisky", "user"]
    search_fields = ["barcode"]


@admin.register(WhiskyStorageItem)
class WhiskyStorageItemAdmin(admin.ModelAdmin):
    list_display = ["whisky", "storage", "fill_level", "deleted", "user"]
    list_filter = ["fill_level", "deleted"]

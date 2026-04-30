import base64
import logging
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import (
    DetailView,
    ListView,
    TemplateView,
)
from django_filters.views import FilterView
from django_ratelimit.decorators import ratelimit

from wine_cellar.apps.core.views import (
    MAX_IMAGE_SIZE,
    BaseBeverageCreateView,
    BaseBeverageDeleteView,
    BaseBeverageUpdateView,
    BaseBottleNoteCreateView,
    BaseCellarValueView,
    BaseConsumptionStatsView,
    BaseDetailView,
    BaseDrinkRecordCreateView,
    BaseDrinkRecordDeleteView,
    BaseDrinkRecordEditView,
    BaseDrinkRecordListView,
    BaseHomePageView,
    BaseImagesView,
    BaseJourneyTimelineView,
    BaseLabelScanView,
    BaseListView,
    BaseMarkBottleBrokenOrLostView,
    BaseMarkBottleGivenView,
    BaseMergeConfirmView,
    BaseQRCodeView,
    BaseRandomBottleView,
    BaseReorderReminderCreateView,
    BaseReorderReminderDeleteView,
    BaseReorderRemindersView,
    BaseScanView,
    BaseStatsDashboardView,
    BaseStorageItemAddView,
    BaseStorageItemUpdateView,
    BaseWishlistCreateView,
    BaseWishlistDeleteView,
    BaseWishlistListView,
    BaseWishlistPurchasedView,
    check_beverage_duplicate_ajax,
    crop_image_ajax,
    set_primary_image_ajax,
)
from wine_cellar.apps.household.mixins import (
    RequireHouseholdMixin,
    require_member,
)
from wine_cellar.apps.storage.utils import (
    format_bottle_location,
    format_given_detail,
    format_move_detail,
    with_removal_sort_date,
)
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.whisky.filters import WhiskyFilter, WhiskyStorageItemFilter
from wine_cellar.apps.whisky.forms import (
    POST_DRINK_STATUS_CONSUMED,
    WhiskyDrinkRecordForm,
    WhiskyEditForm,
    WhiskyForm,
    WhiskyPriceHistoryForm,
    WhiskyStockAddForm,
    WhiskyWishlistForm,
)
from wine_cellar.apps.whisky.models import (
    Bottler,
    Collection,
    Distillery,
    FillLevel,
    Whisky,
    WhiskyBarcode,
    WhiskyBottleMoveHistory,
    WhiskyBottleNote,
    WhiskyDrinkingWindowAlert,
    WhiskyDrinkRecord,
    WhiskyImage,
    WhiskyPriceHistory,
    WhiskyRegion,
    WhiskyReorderReminder,
    WhiskyStorageItem,
    WhiskyVisionExtractionLog,
    WhiskyWishlist,
)

logger = logging.getLogger(__name__)


def _format_price_delta(beverage, amount):
    if amount is None:
        return None
    sign = "+" if amount > 0 else "-" if amount < 0 else ""
    formatted = beverage.format_currency(abs(amount))
    return f"{sign}{formatted}" if sign else formatted


def _normalize_scan_lookup_text(value: str) -> str:
    """Normalize scan text so distillery name checks survive punctuation and spacing."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _find_named_match(model, value: str):
    """Return an exact case-insensitive name match for a model, if one exists."""
    value = value.strip()
    if not value:
        return None
    return model.objects.filter(name__iexact=value).first()


def _store_unresolved_name(
    result_data: dict, field_name: str, preserve_unmatched_names: bool
):
    """Store a trimmed unresolved FK name when requested and non-empty."""
    unresolved_value = result_data.pop(field_name, None)
    if not preserve_unmatched_names or not isinstance(unresolved_value, str):
        return

    unresolved_value = unresolved_value.strip()
    if unresolved_value:
        result_data[f"{field_name}_name"] = unresolved_value


def _find_distillery_match(result_data: dict):
    """Resolve a distillery from extracted scan data or the whisky name itself."""
    search_values = []

    distillery_value = result_data.get("distillery")
    if isinstance(distillery_value, str) and distillery_value.strip():
        search_values.append((0, distillery_value.strip()))

    name_value = result_data.get("name")
    if isinstance(name_value, str) and name_value.strip():
        search_values.append((1, name_value.strip()))

    if not search_values:
        return None

    for _, value in search_values:
        match = _find_named_match(Distillery, value)
        if match:
            return match

    normalized_search_values = []
    for priority, value in search_values:
        normalized_value = _normalize_scan_lookup_text(value)
        if normalized_value:
            normalized_search_values.append((priority, normalized_value))

    if not normalized_search_values:
        return None

    distilleries = [
        (distillery, _normalize_scan_lookup_text(distillery.name))
        for distillery in Distillery.objects.only("pk", "name")
    ]
    substring_matches = []
    for priority, normalized_value in normalized_search_values:
        for distillery, normalized_name in distilleries:
            if normalized_name and normalized_name in normalized_value:
                substring_matches.append(
                    (priority, -len(normalized_name), distillery.name, distillery)
                )

    if substring_matches:
        substring_matches.sort()
        return substring_matches[0][3]

    return None


def _resolve_whisky_extracted_fks(
    result_data: dict, *, preserve_unmatched_names: bool = False
):
    """Resolve extracted whisky FK fields for both add-form and AJAX scan flows."""
    distillery_match = _find_distillery_match(result_data)
    if distillery_match:
        result_data["distillery"] = distillery_match.pk
    elif "distillery" in result_data and isinstance(result_data["distillery"], str):
        _store_unresolved_name(result_data, "distillery", preserve_unmatched_names)

    for field_name, model in (("region", WhiskyRegion), ("bottler", Bottler)):
        value = result_data.get(field_name)
        if not isinstance(value, str):
            continue

        match = _find_named_match(model, value)
        if match:
            result_data[field_name] = match.pk
            continue

        _store_unresolved_name(result_data, field_name, preserve_unmatched_names)


class QRCodeView(BaseQRCodeView):
    beverage_model = Whisky
    detail_url_name = "whisky-detail"


class RandomBottleView(BaseRandomBottleView):
    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    detail_url_name = "whisky-detail"


class HomePageView(BaseHomePageView):
    template_name = "core/homepage.html"
    beverage_model = Whisky
    storage_item_model = WhiskyStorageItem
    drink_record_model = WhiskyDrinkRecord
    wishlist_model = WhiskyWishlist
    reminder_model = WhiskyReorderReminder
    beverage_fk_name = "whisky"
    beverage_price_path = "whisky__price"
    stock_reverse_path = "whisky__whiskystorageitem"
    homepage_title = "My Whisky Cabinet"
    stats_template = "whisky/includes/homepage_stats.html"
    alerts_template = "whisky/includes/homepage_alerts.html"
    beverage_icon = "whiskey-glass"

    def get_app_specific_context(self, household, user):
        import datetime

        whiskies = Whisky.objects.filter(household=household, deleted=False).count()
        whisky_stats = Whisky.objects.filter(
            household=household, deleted=False
        ).aggregate(
            whiskies_in_stock=Count(
                "id", filter=Q(whiskystorageitem__deleted=False), distinct=True
            ),
            distilleries=Count("distillery", distinct=True),
            oldest_vintage=Min("vintage_year", filter=Q(vintage_year__isnull=False)),
            youngest_vintage=Max("vintage_year", filter=Q(vintage_year__isnull=False)),
        )

        open_bottles = (
            WhiskyStorageItem.objects.filter(household=household, deleted=False)
            .exclude(fill_level="UN")
            .count()
        )

        oldest_age = (
            Whisky.objects.filter(
                household=household, deleted=False, age_statement__isnull=False
            ).aggregate(Max("age_statement"))["age_statement__max"]
            or 0
        )

        dreg_cutoff_warning = datetime.date.today() - datetime.timedelta(days=335)
        dreg_cutoff_expired = datetime.date.today() - datetime.timedelta(days=365)
        dreg_expired_count = WhiskyStorageItem.objects.filter(
            household=household,
            deleted=False,
            fill_level="DR",
            dreg_date__lte=dreg_cutoff_expired,
        ).count()
        dreg_warning_count = WhiskyStorageItem.objects.filter(
            household=household,
            deleted=False,
            fill_level="DR",
            dreg_date__lte=dreg_cutoff_warning,
            dreg_date__gt=dreg_cutoff_expired,
        ).count()

        return {
            "whiskies": whiskies,
            "whiskies_in_stock": whisky_stats["whiskies_in_stock"],
            "distilleries_count": whisky_stats["distilleries"],
            "open_bottles": open_bottles,
            "oldest_age": oldest_age,
            "oldest": whisky_stats["oldest_vintage"] or "-",
            "youngest": whisky_stats["youngest_vintage"] or "-",
            "dreg_expired_count": dreg_expired_count,
            "dreg_warning_count": dreg_warning_count,
        }


@method_decorator(
    ratelimit(key="user", rate="20/m", method="POST", block=True), name="post"
)
class WhiskyCreateView(BaseBeverageCreateView):
    """View for creating new whiskies. Rate limited to 20 creations/minute per user."""

    template_name = "whisky/whisky_create.html"
    form_class = WhiskyForm
    success_url = reverse_lazy("whisky-list")
    vision_extractor_path = "wine_cellar.apps.whisky.services.WhiskyVisionExtractor"
    add_url_name = "whisky-add"
    beverage_label = "whisky"
    page_title = "Add Whisky"
    scan_url_name = "whisky-scan"
    rescan_url_name = "whisky-scan"
    duplicate_check_url_name = "whisky-check-duplicate"
    extract_vision_url_name = "whisky-extract-vision"
    quick_add_description = "Use your camera to scan the whisky label and barcode:"
    image_autofill_hint = (
        "Upload images and click 'Auto-fill from Images' to extract whisky details "
        "using AI vision."
    )
    image_extract_hint = "Extract whisky details from uploaded images"
    scanned_label_alt = "Scanned whisky label"
    save_button_label = "Save Whisky"
    field_section_definitions = (
        {
            "title": "Details",
            "fields": (
                "name",
                "whisky_type",
                "distillery",
                "region",
                "country",
                "size",
            ),
        },
        {
            "title": "Character",
            "fields": (
                "age_statement",
                "abv",
                "peated_level",
                "cask_type",
                "cask_strength",
                "vintage_year",
                "bottled_year",
                "color",
            ),
        },
        {
            "title": "Bottling",
            "fields": (
                "bottler",
                "bottler_series",
                "cask_number",
                "batch_number",
                "bottle_number",
                "limited_edition",
            ),
        },
        {
            "title": "Origin & Price",
            "fields": ("source", "price", "barcode"),
        },
        {
            "title": "Personal Notes",
            "fields": ("rating", "owner", "comment"),
        },
    )
    cellar_extra_field_names = ("fill_level",)
    confidence_badge_labels = {
        "high": "High Confidence",
        "medium": "Please Verify",
        "low": "Low Confidence",
    }
    vision_field_map = {
        "name": "name",
        "whisky_type": "whisky_type",
        "distillery": "distillery",
        "region": "region",
        "country": "country",
        "age_statement": "age_statement",
        "abv": "abv",
        "peated_level": "peated_level",
        "cask_type": "cask_type",
        "size": "size",
        "vintage_year": "vintage_year",
        "bottled_year": "bottled_year",
        "cask_number": "cask_number",
        "batch_number": "batch_number",
        "bottle_number": "bottle_number",
        "bottler": "bottler",
        "bottler_series": "bottler_series",
        "barcode": "barcode",
    }
    vision_confidence_field_map = {
        "name": "name",
        "whisky_type": "whisky_type",
        "type": "whisky_type",
        "distillery": "distillery",
        "region": "region",
        "country": "country",
        "age_statement": "age_statement",
        "abv": "abv",
        "size": "size",
        "peated_level": "peated_level",
        "cask_type": "cask_type",
        "vintage_year": "vintage_year",
        "bottled_year": "bottled_year",
        "cask_number": "cask_number",
        "batch_number": "batch_number",
        "bottle_number": "bottle_number",
        "bottler": "bottler",
        "bottler_series": "bottler_series",
        "barcode": "barcode",
    }
    vision_create_fields = ("cask_type",)
    vision_fk_name_fields = {
        "distillery_name": "distillery",
        "region_name": "region",
        "bottler_name": "bottler",
    }
    extraction_log_model = WhiskyVisionExtractionLog
    extraction_log_fk_name = "whisky"

    def resolve_extracted_data(self, result_data, initial):
        _resolve_whisky_extracted_fks(result_data)

    @staticmethod
    @transaction.atomic
    def process_form_data(user, household, cleaned_data):
        abv = cleaned_data["abv"]
        size = cleaned_data["size"]
        barcode = cleaned_data.get("barcode")
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        price = cleaned_data["price"]
        name = cleaned_data["name"]
        rating = cleaned_data["rating"]
        whisky_type = cleaned_data["whisky_type"]
        distillery = cleaned_data.get("distillery")
        region = cleaned_data.get("region")
        age_statement = cleaned_data.get("age_statement")
        vintage_year = cleaned_data.get("vintage_year")
        bottled_year = cleaned_data.get("bottled_year")
        peated_level = cleaned_data.get("peated_level") or None
        cask_type = cleaned_data.get("cask_type") or ""
        cask_strength = cleaned_data.get("cask_strength", False)
        color = cleaned_data.get("color")
        bottler = cleaned_data.get("bottler")
        bottler_series = cleaned_data.get("bottler_series")
        cask_number = cleaned_data.get("cask_number")
        batch_number = cleaned_data.get("batch_number")
        bottle_number = cleaned_data.get("bottle_number")
        limited_edition = cleaned_data.get("limited_edition", False)
        release_year = cleaned_data.get("release_year")
        source = cleaned_data.get("source")
        owner = cleaned_data.get("owner", "")

        # Use get_or_create to handle duplicate whiskies gracefully
        whisky, created = Whisky.objects.get_or_create(
            name=name,
            whisky_type=whisky_type,
            abv=abv,
            size=size,
            vintage_year=vintage_year,
            bottled_year=bottled_year,
            user=user,
            household=household,
            deleted=False,
            defaults={
                "distillery": distillery,
                "region": region,
                "country": country,
                "age_statement": age_statement,
                "peated_level": peated_level,
                "cask_type": cask_type,
                "cask_strength": cask_strength,
                "color": color,
                "bottler": bottler,
                "bottler_series": bottler_series,
                "cask_number": cask_number,
                "batch_number": batch_number,
                "bottle_number": bottle_number,
                "limited_edition": limited_edition,
                "release_year": release_year,
                "comment": comment,
                "rating": rating,
                "price": price,
                "source": source,
                "owner": owner,
            },
        )

        # Create barcode entry if provided
        if barcode:
            WhiskyBarcode.objects.get_or_create(
                barcode=barcode,
                user=user,
                defaults={"whisky": whisky, "household": household},
            )

        # Handle storage (add bottle to cellar) if provided
        storage = cleaned_data.get("storage")
        if storage:
            import datetime

            row = cleaned_data.get("row")
            column = cleaned_data.get("column")
            bottle_price = cleaned_data.get("bottle_price") or price
            is_gift = cleaned_data.get("is_gift", False)
            gift_from = cleaned_data.get("gift_from")
            occasion = cleaned_data.get("occasion")
            fill_level = cleaned_data.get("fill_level", FillLevel.UNOPENED)
            dreg_date = datetime.date.today() if fill_level == FillLevel.DREG else None
            WhiskyStorageItem.objects.create(
                storage=storage,
                whisky=whisky,
                row=row,
                column=column,
                user=user,
                household=household,
                price=bottle_price,
                is_gift=is_gift,
                gift_from=gift_from,
                occasion=occasion,
                fill_level=fill_level,
                dreg_date=dreg_date,
            )

        return whisky, created


class WhiskyUpdateView(BaseBeverageUpdateView):
    template_name = "core/beverage_edit.html"
    form_class = WhiskyEditForm
    success_url = reverse_lazy("whisky-list")
    beverage_model = Whisky
    beverage_fk_name = "whisky"
    image_related_name = "images"
    detail_url_name = "whisky-detail"

    @staticmethod
    @transaction.atomic
    def process_form_data(whisky, user, cleaned_data):
        abv = cleaned_data["abv"]
        size = cleaned_data["size"]
        barcode = cleaned_data.get("barcode")
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        price = cleaned_data["price"]
        name = cleaned_data["name"]
        rating = cleaned_data["rating"]
        whisky_type = cleaned_data["whisky_type"]
        distillery = cleaned_data.get("distillery")
        region = cleaned_data.get("region")
        age_statement = cleaned_data.get("age_statement")
        vintage_year = cleaned_data.get("vintage_year")
        bottled_year = cleaned_data.get("bottled_year")
        peated_level = cleaned_data.get("peated_level") or None
        cask_type = cleaned_data.get("cask_type") or ""
        cask_strength = cleaned_data.get("cask_strength", False)
        color = cleaned_data.get("color")
        bottler = cleaned_data.get("bottler")
        bottler_series = cleaned_data.get("bottler_series")
        cask_number = cleaned_data.get("cask_number")
        batch_number = cleaned_data.get("batch_number")
        bottle_number = cleaned_data.get("bottle_number")
        limited_edition = cleaned_data.get("limited_edition", False)
        release_year = cleaned_data.get("release_year")

        source = cleaned_data.get("source")
        owner = cleaned_data.get("owner", "")

        whisky.abv = abv
        whisky.size = size
        whisky.comment = comment
        whisky.country = country
        whisky.name = name
        whisky.rating = rating
        whisky.whisky_type = whisky_type
        whisky.distillery = distillery
        whisky.region = region
        whisky.age_statement = age_statement
        whisky.vintage_year = vintage_year
        whisky.bottled_year = bottled_year
        whisky.peated_level = peated_level
        whisky.cask_type = cask_type
        whisky.cask_strength = cask_strength
        whisky.color = color
        whisky.bottler = bottler
        whisky.bottler_series = bottler_series
        whisky.cask_number = cask_number
        whisky.batch_number = batch_number
        whisky.bottle_number = bottle_number
        whisky.limited_edition = limited_edition
        whisky.release_year = release_year
        whisky.price = price
        whisky.source = source
        whisky.owner = owner
        whisky.save()

        # Create barcode entry if provided
        if barcode:
            WhiskyBarcode.objects.get_or_create(
                barcode=barcode,
                user=user,
                defaults={"whisky": whisky, "household": whisky.household},
            )


class WhiskyDetailView(BaseDetailView):
    template_name = "whisky/whisky_detail.html"
    model = Whisky
    select_related_fields = ("distillery", "region", "bottler", "source")
    prefetch_related_fields = ("cask_history", "images", "barcodes", "collections")
    storage_item_reverse = "whiskystorageitem"
    extraction_log_model = WhiskyVisionExtractionLog
    extraction_log_fk_name = "whisky"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["all_collections"] = Collection.objects.filter(
            household=household
        ).order_by("name")
        price_history_qs = self.object.whiskypricehistory_set.select_related("source")
        price_history_entries = list(price_history_qs[:5])
        latest_entry = price_history_entries[0] if price_history_entries else None
        average_market_price = price_history_qs.aggregate(avg_price=Avg("price"))[
            "avg_price"
        ]
        oldest_market_price = (
            price_history_qs.order_by("recorded_at")
            .values_list("price", flat=True)
            .first()
        )
        purchase_price_baseline = self.object.whiskystorageitem_set.aggregate(
            avg_price=Avg("price")
        )["avg_price"]
        if purchase_price_baseline is None:
            purchase_price_baseline = self.object.price
        context["price_history_form"] = kwargs.get("price_history_form") or (
            WhiskyPriceHistoryForm(user=self.request.user)
        )
        context["price_history_entries"] = price_history_entries
        context["price_history_latest"] = latest_entry
        context["price_history_average_with_currency"] = self.object.format_currency(
            average_market_price
        )
        context["price_history_purchase_baseline_with_currency"] = (
            self.object.format_currency(purchase_price_baseline)
        )
        context["price_history_vs_purchase_with_currency"] = _format_price_delta(
            self.object,
            (
                average_market_price - purchase_price_baseline
                if average_market_price is not None
                and purchase_price_baseline is not None
                else None
            ),
        )
        context["price_history_trend_with_currency"] = _format_price_delta(
            self.object,
            (
                latest_entry.price - oldest_market_price
                if latest_entry is not None and oldest_market_price is not None
                else None
            ),
        )
        return context


@login_required
@require_member
@require_POST
def add_price_history(request, pk):
    household = get_active_household(request.user)
    whisky = get_object_or_404(Whisky, pk=pk, household=household, deleted=False)
    form = WhiskyPriceHistoryForm(request.POST, user=request.user)

    if form.is_valid():
        WhiskyPriceHistory.objects.create(
            whisky=whisky,
            source=form.cleaned_data["source"],
            price=form.cleaned_data["price"],
            user=request.user,
            household=household,
        )
        messages.success(request, "Tracked market price saved.")
    else:
        messages.error(
            request,
            "Could not save tracked market price. "
            + "; ".join(error for errors in form.errors.values() for error in errors),
        )

    return redirect(
        f"{reverse('whisky-detail', kwargs={'pk': whisky.pk})}#price-tracking"
    )


@login_required
@require_member
@require_POST
def add_whisky_to_collection(request, pk):
    household = get_active_household(request.user)
    whisky = get_object_or_404(Whisky, pk=pk, household=household)
    collection_id = request.POST.get("collection_id")
    new_collection_name = (request.POST.get("new_collection_name") or "").strip()[:100]

    collection = None
    if collection_id:
        try:
            collection = Collection.objects.filter(
                pk=int(collection_id), household=household
            ).first()
        except (ValueError, TypeError):
            pass
    elif new_collection_name:
        collection, _ = Collection.objects.get_or_create(
            name=new_collection_name,
            household=household,
            defaults={"user": request.user},
        )

    if collection:
        collection.whiskies.add(whisky)

    return redirect("whisky-detail", pk=whisky.pk)


@login_required
@require_member
@require_POST
def remove_whisky_from_collection(request, pk, collection_pk):
    household = get_active_household(request.user)
    whisky = get_object_or_404(Whisky, pk=pk, household=household)
    collection = get_object_or_404(Collection, pk=collection_pk, household=household)
    collection.whiskies.remove(whisky)
    return redirect("whisky-detail", pk=whisky.pk)


class WhiskyDeleteView(BaseBeverageDeleteView):
    model = Whisky
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("whisky-list")
    context_object_name = "beverage"


class WhiskyListView(BaseListView, FilterView):
    model = Whisky
    template_name = "core/beverage_list.html"
    context_object_name = "whiskies"
    filterset_class = WhiskyFilter
    default_filter_data = {"has_stock": "1", "order": "created"}
    storage_item_reverse = "whiskystorageitem"
    select_related_fields = ("distillery", "region", "bottler")
    prefetch_related_fields = ("images",)
    card_template = "whisky/whisky_card.html"
    filter_field_template = "whisky/whisky_filter_field.html"
    beverage_icon = "whiskey-glass"


class WhiskyScanView(BaseScanView):
    template_name = "whisky/scan_whisky.html"


class WhiskyScannedView(RequireHouseholdMixin, TemplateView):
    template_name = "core/scanned_beverage.html"

    def dispatch(self, request, *args, **kwargs):
        code = self.kwargs["code"]
        # Placeholder barcode lookup
        household = get_active_household(request.user)
        whiskies = Whisky.objects.filter(
            barcodes__barcode=code, household=household, deleted=False
        )

        if whiskies.exists():
            if whiskies.count() == 1:
                whisky = whiskies.first()
                return redirect(reverse("whisky-detail", kwargs={"pk": whisky.pk}))
            # Multiple matches
            self.extra_context = {
                "scanned_beverages": whiskies,
                "barcode": code,
                "card_template": "whisky/whisky_card.html",
            }
            return super().dispatch(request, *args, **kwargs)

        # No matches
        request.session["pending_barcode"] = code
        self.extra_context = {
            "add_url": reverse("whisky-add"),
        }
        return super().dispatch(request, *args, **kwargs)


class WhiskyMapView(RequireHouseholdMixin, TemplateView):
    template_name = "whisky/whisky_map.html"

    def get_context_data(self, **kwargs):
        import json as json_module

        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)

        # Get distilleries that have whiskies in stock
        distilleries_with_stock = (
            Distillery.objects.filter(
                whisky__household=household,
                whisky__deleted=False,
                whisky__whiskystorageitem__isnull=False,
                whisky__whiskystorageitem__deleted=False,
            )
            .distinct()
            .select_related("region")
        )

        # Also include all distilleries with coordinates for the full map
        all_distilleries = Distillery.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        ).select_related("region")

        # Count bottles per distillery for this household
        bottle_counts = {}
        for d in distilleries_with_stock:
            bottle_counts[d.pk] = WhiskyStorageItem.objects.filter(
                whisky__distillery=d,
                household=household,
                deleted=False,
            ).count()

        distilleries_json = json_module.dumps(
            [
                {
                    "id": d.pk,
                    "name": d.name,
                    "region": d.region.name if d.region else "",
                    "region_id": d.region_id or 0,
                    "latitude": d.latitude,
                    "longitude": d.longitude,
                    "status": d.status,
                    "status_display": d.get_status_display(),
                    "founded_year": d.founded_year,
                    "bottle_count": bottle_counts.get(d.pk, 0),
                    "url": None,
                }
                for d in all_distilleries
            ]
        )

        context["distilleries_json"] = distilleries_json
        context["map_base_url"] = settings.MAP_BASEURL
        return context


class LabelScanView(BaseLabelScanView):
    template_name = "core/label_scan.html"
    add_url_name = "whisky-add"


@ratelimit(key="user", rate="10/m", method="POST", block=True)
@login_required
def extract_whisky_vision_ajax(request):
    """AJAX endpoint for whisky data extraction from uploaded images."""
    from wine_cellar.apps.core.views import extract_vision_ajax
    from wine_cellar.apps.whisky.services.barcode_service import WhiskyBarcodeScanner

    def resolve_fks(data):
        """Resolve distillery, region, and bottler strings to PKs for TomSelect."""
        _resolve_whisky_extracted_fks(data, preserve_unmatched_names=True)

    return extract_vision_ajax(
        request,
        barcode_scanner_factory=WhiskyBarcodeScanner,
        vision_extractor_path=(
            "wine_cellar.apps.whisky.services.vision_extraction.WhiskyVisionExtractor"
        ),
        beverage_label="whisky",
        resolve_extracted_fks=resolve_fks,
    )


@ratelimit(key="user", rate="60/m", method="GET", block=True)
@login_required
def whisky_check_duplicate_ajax(request):
    """AJAX endpoint to check for whiskies with similar names."""
    return check_beverage_duplicate_ajax(
        request,
        beverage_model=Whisky,
        detail_url_name="whisky-detail",
    )


@ratelimit(key="user", rate="30/m", method="POST", block=True)
@login_required
def scan_barcode_ajax(request):
    """
    AJAX endpoint for server-side barcode scanning from captured images.

    Rate limited to 30 requests per minute per user.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        images = []
        image_fields = [
            "image_front_label",
            "image_back_label",
            "image_front",
            "image_back",
        ]

        for field_name in image_fields:
            image_file = request.FILES.get(field_name)
            if image_file:
                if image_file.size > MAX_IMAGE_SIZE:
                    return JsonResponse(
                        {"error": f"Image {field_name} is too large."},
                        status=400,
                    )
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                images.append(base64_image)
                image_file.seek(0)

        if not images:
            return JsonResponse(
                {"error": "No images uploaded."},
                status=400,
            )

        from wine_cellar.apps.whisky.services.barcode_service import (
            WhiskyBarcodeScanner,
        )

        scanner = WhiskyBarcodeScanner()
        barcodes = scanner.scan_images_for_barcodes(images)

        return JsonResponse(
            {
                "success": True,
                "barcodes": barcodes,
            }
        )

    except Exception:
        logger.exception("Error in whisky barcode scanning")
        return JsonResponse({"error": "Barcode scanning failed"}, status=500)


class DrinkRecordCreateView(BaseDrinkRecordCreateView):
    template_name = "core/drink_record_create.html"
    form_class = WhiskyDrinkRecordForm
    beverage_model = Whisky
    drink_record_model = WhiskyDrinkRecord
    beverage_fk_name = "whisky"
    detail_url_name = "whisky-detail"

    def handle_bottle_update(self, form, storage_item):
        post_drink_status = form.cleaned_data.get("post_drink_status")
        date_consumed = form.cleaned_data["date_consumed"]

        if post_drink_status == POST_DRINK_STATUS_CONSUMED:
            storage_item.deleted = True
            storage_item.finished_date = date_consumed
            storage_item.removal_reason = WhiskyStorageItem.RemovalReason.CONSUMED
            storage_item.given_date = None
            storage_item.recipient = ""
            storage_item.given_occasion = ""
            storage_item.save(
                update_fields=[
                    "deleted",
                    "finished_date",
                    "removal_reason",
                    "given_date",
                    "recipient",
                    "given_occasion",
                ]
            )
        elif post_drink_status in (FillLevel.OPENED, FillLevel.DREG):
            old_fill_level = storage_item.fill_level
            storage_item.fill_level = post_drink_status
            update_fields = ["fill_level"]

            if not storage_item.opened_date:
                storage_item.opened_date = date_consumed
                update_fields.append("opened_date")

            if post_drink_status == FillLevel.DREG and old_fill_level != FillLevel.DREG:
                storage_item.dreg_date = date_consumed
                update_fields.append("dreg_date")
            elif (
                post_drink_status != FillLevel.DREG and old_fill_level == FillLevel.DREG
            ):
                storage_item.dreg_date = None
                update_fields.append("dreg_date")

            storage_item.save(update_fields=update_fields)


class DrinkRecordListView(BaseDrinkRecordListView):
    template_name = "core/drink_record_list.html"
    drink_record_model = WhiskyDrinkRecord
    beverage_fk_name = "whisky"
    beverage_icon = "whiskey-glass"


class JourneyTimelineView(BaseJourneyTimelineView):
    template_name = "core/journey_timeline.html"
    storage_item_model = WhiskyStorageItem
    drink_record_model = WhiskyDrinkRecord
    beverage_fk_name = "whisky"
    beverage_icon = "whiskey-glass"


class DrinkRecordEditView(BaseDrinkRecordEditView):
    template_name = "core/drink_record_edit.html"
    form_class = WhiskyDrinkRecordForm
    drink_record_model = WhiskyDrinkRecord
    beverage_fk_name = "whisky"


class DrinkRecordDeleteView(BaseDrinkRecordDeleteView):
    model = WhiskyDrinkRecord
    template_name = "whisky/drink_record_confirm_delete.html"


class WishlistListView(BaseWishlistListView):
    template_name = "core/wishlist_list.html"
    wishlist_model = WhiskyWishlist
    wishlist_columns_header = "whisky/includes/wishlist_columns_header.html"
    wishlist_columns_row = "whisky/includes/wishlist_columns_row.html"


class WishlistCreateView(BaseWishlistCreateView):
    template_name = "core/wishlist_create.html"
    form_class = WhiskyWishlistForm
    wishlist_model = WhiskyWishlist

    def get_extra_create_kwargs(self, form):
        return {
            "whisky_type": form.cleaned_data.get("whisky_type") or None,
            "distillery": form.cleaned_data.get("distillery"),
            "region": form.cleaned_data.get("region"),
            "age_statement": form.cleaned_data.get("age_statement"),
        }


class WishlistDeleteView(BaseWishlistDeleteView):
    model = WhiskyWishlist
    template_name = "whisky/wishlist_confirm_delete.html"


class WishlistPurchasedView(BaseWishlistPurchasedView):
    wishlist_model = WhiskyWishlist


class CellarValueView(BaseCellarValueView):
    template_name = "core/cellar_value.html"
    storage_item_model = WhiskyStorageItem
    price_fallback_path = "whisky__price"
    beverage_fk_name = "whisky"
    select_related_fields = ("whisky__distillery",)
    group_label = "Distillery"

    def get_groupings(self, item):
        return {
            "by_group": (
                item.whisky.distillery.name if item.whisky.distillery else "Unknown"
            ),
            "by_type": item.whisky.get_whisky_type_display(),
        }


class ConsumptionStatsView(BaseConsumptionStatsView):
    template_name = "core/consumption_stats.html"
    drink_record_model = WhiskyDrinkRecord
    beverage_fk_name = "whisky"
    select_related_fields = ("whisky__distillery",)
    group_label = "Distillery"

    def get_type_display(self, beverage):
        return beverage.get_whisky_type_display()

    def get_secondary_stats(self, records):
        from collections import defaultdict

        by_distillery = defaultdict(int)
        for record in records:
            distillery = (
                record.whisky.distillery.name if record.whisky.distillery else "Unknown"
            )
            by_distillery[distillery] += 1
        return {"by_group": dict(by_distillery)}


class StatsDashboardView(BaseStatsDashboardView):
    template_name = "core/stats_dashboard.html"
    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    price_fallback_path = "whisky__price"
    select_related_fields = ("whisky",)

    def get_type_display(self, beverage):
        return beverage.get_whisky_type_display()

    def get_country_name(self, beverage):
        return beverage.country_name if beverage.country else "Unknown"


class BottleNoteCreateView(BaseBottleNoteCreateView):
    template_name = "core/bottle_note_create.html"
    storage_item_model = WhiskyStorageItem
    note_model = WhiskyBottleNote
    beverage_fk_name = "whisky"
    detail_url_name = "whisky-detail"


class DrinkingWindowAlertsView(RequireHouseholdMixin, TemplateView):
    template_name = "whisky/drinking_window_alerts.html"

    def get_context_data(self, **kwargs):
        import datetime

        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)

        # Dreg alerts
        dreg_cutoff_warning = datetime.date.today() - datetime.timedelta(days=335)
        dreg_cutoff_expired = datetime.date.today() - datetime.timedelta(days=365)

        dreg_expired = WhiskyStorageItem.objects.filter(
            household=household,
            deleted=False,
            fill_level="DR",
            dreg_date__lte=dreg_cutoff_expired,
        ).select_related("whisky", "storage")

        dreg_warning = WhiskyStorageItem.objects.filter(
            household=household,
            deleted=False,
            fill_level="DR",
            dreg_date__lte=dreg_cutoff_warning,
            dreg_date__gt=dreg_cutoff_expired,
        ).select_related("whisky", "storage")

        # Low stock reminders
        reminders = (
            WhiskyReorderReminder.objects.filter(household=household, is_active=True)
            .select_related("whisky")
            .annotate(
                current_stock=Count(
                    "whisky__whiskystorageitem",
                    filter=Q(whisky__whiskystorageitem__deleted=False),
                )
            )
        )
        needs_reorder = [r for r in reminders if r.current_stock <= r.min_stock]

        context.update(
            {
                "dreg_expired": dreg_expired,
                "dreg_warning": dreg_warning,
                "needs_reorder": needs_reorder,
            }
        )
        return context


class ReorderRemindersView(BaseReorderRemindersView):
    template_name = "core/reorder_reminders.html"
    reminder_model = WhiskyReorderReminder
    beverage_fk_name = "whisky"
    stock_reverse_path = "whisky__whiskystorageitem"
    beverage_icon = "whiskey-glass"


class ReorderReminderCreateView(BaseReorderReminderCreateView):
    template_name = "core/reorder_reminder_create.html"
    beverage_model = Whisky
    reminder_model = WhiskyReorderReminder
    beverage_fk_name = "whisky"
    detail_url_name = "whisky-detail"


class ReorderReminderDeleteView(BaseReorderReminderDeleteView):
    model = WhiskyReorderReminder
    template_name = "whisky/reorder_reminder_confirm_delete.html"


class StorageItemAddView(BaseStorageItemAddView):
    """Add a bottle to storage."""

    template_name = "whisky/stock_add.html"
    form_class = WhiskyStockAddForm
    beverage_model = Whisky
    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    beverage_context_name = "whisky"
    beverage_label = "whisky"
    detail_url_name = "whisky-detail"
    extra_stock_field_names = ("owner", "fill_level")

    def get_add_form_kwargs(self, whisky):
        return {"whisky": whisky}

    def get_extra_create_kwargs(self, cleaned_data):
        fill_level = cleaned_data["fill_level"]
        return {
            "fill_level": fill_level,
            "dreg_date": timezone.localdate() if fill_level == FillLevel.DREG else None,
            "owner": cleaned_data.get("owner", ""),
        }


class StorageItemDeleteView(BaseMarkBottleBrokenOrLostView):
    """Mark a bottle as broken or lost."""

    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    detail_url_name = "whisky-detail"
    list_url_name = "bottle-list"


class StorageItemMarkGivenView(BaseMarkBottleGivenView):
    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    detail_url_name = "whisky-detail"
    list_url_name = "bottle-list"


class StorageItemListView(RequireHouseholdMixin, FilterView):
    """List all bottles in storage with filtering."""

    model = WhiskyStorageItem
    template_name = "whisky/bottle_list.html"
    context_object_name = "bottles"
    filterset_class = WhiskyStorageItemFilter
    paginate_by = 20

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return (
            WhiskyStorageItem.objects.filter(household=household)
            .select_related("whisky", "storage")
            .order_by("-created")
        )


class StorageItemUpdateView(BaseStorageItemUpdateView):
    """Edit a bottle (e.g., update fill level)."""

    template_name = "whisky/bottle_edit.html"
    form_class = WhiskyStockAddForm
    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    beverage_context_name = "whisky"
    detail_url_name = "whisky-detail"
    move_history_model = WhiskyBottleMoveHistory
    extra_initial_field_names = ("fill_level", "owner")

    def get_update_form_kwargs(self, item):
        return {"whisky": item.whisky}

    def apply_extra_updates(self, item, cleaned_data):
        old_fill_level = item.fill_level
        new_fill_level = cleaned_data["fill_level"]
        item.fill_level = new_fill_level

        if new_fill_level == FillLevel.DREG and old_fill_level != FillLevel.DREG:
            item.dreg_date = timezone.localdate()
        elif new_fill_level != FillLevel.DREG and old_fill_level == FillLevel.DREG:
            item.dreg_date = None

        item.owner = cleaned_data.get("owner", "")


class StorageItemHistoryView(RequireHouseholdMixin, ListView):
    """List deleted (removed) whisky storage items."""

    model = WhiskyStorageItem
    template_name = "whisky/stock_history.html"
    context_object_name = "storage_items"
    paginate_by = 10

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return with_removal_sort_date(
            WhiskyStorageItem.objects.filter(
                household=household, deleted=True
            ).select_related("whisky", "storage")
        ).order_by("-removal_sort_date", "-created", "-pk")


class WhiskyMergeConfirmView(BaseMergeConfirmView):
    template_name = "core/merge_confirm.html"
    beverage_model = Whisky
    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    detail_url_name = "whisky-detail"
    image_model = WhiskyImage
    m2m_fields = ("attributes", "collections")
    related_models = (
        (WhiskyDrinkRecord, "whisky"),
        (WhiskyDrinkingWindowAlert, "whisky"),
        (WhiskyPriceHistory, "whisky"),
        (WhiskyVisionExtractionLog, "whisky"),
    )
    reminder_model = WhiskyReorderReminder


class WhiskyImagesView(BaseImagesView):
    template_name = "core/beverage_images.html"
    model = Whisky
    context_object_name = "whisky"
    images_prefetch_name = "images"
    image_api_prefix = "/whisky/image"


@login_required
def set_primary_image(request, pk):
    """Set a WhiskyImage as the primary image for its whisky."""
    return set_primary_image_ajax(request, pk, WhiskyImage)


@login_required
def crop_whisky_image(request, pk):
    """Apply manual crop to a WhiskyImage and create a new thumbnail."""
    return crop_image_ajax(request, pk, WhiskyImage)


class WhiskyBottleHistoryView(RequireHouseholdMixin, DetailView):
    """Show the lifecycle history timeline for a single whisky bottle."""

    model = WhiskyStorageItem
    template_name = "bottle_history.html"
    context_object_name = "item"

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return WhiskyStorageItem.objects.filter(household=household).select_related(
            "whisky", "storage"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.object
        events = []

        events.append(
            {
                "type": "added",
                "date": item.created.date(),
                "label": "Added to collection",
                "detail": format_bottle_location(item.storage, item.row, item.column),
            }
        )

        moves = item.move_history.select_related("from_storage", "to_storage").all()
        for move in moves:
            events.append(
                {
                    "type": "move",
                    "date": move.moved_at.date(),
                    "label": "Moved",
                    "detail": format_move_detail(
                        move.from_storage,
                        move.from_row,
                        move.from_column,
                        move.to_storage,
                        move.to_row,
                        move.to_column,
                    ),
                }
            )

        if item.opened_date:
            events.append(
                {
                    "type": "opened",
                    "date": item.opened_date,
                    "label": "Opened",
                    "detail": "",
                }
            )

        if item.dreg_date:
            events.append(
                {
                    "type": "dreg",
                    "date": item.dreg_date,
                    "label": "Reached dreg",
                    "detail": "",
                }
            )

        drinks = WhiskyDrinkRecord.objects.filter(storage_item=item).order_by(
            "date_consumed"
        )
        for drink in drinks:
            events.append(
                {
                    "type": "drink",
                    "date": drink.date_consumed,
                    "label": "Drink recorded",
                    "detail": drink.tasting_notes or "",
                }
            )

        if (
            item.removal_reason == WhiskyStorageItem.RemovalReason.GIVEN
            and item.given_date
        ):
            events.append(
                {
                    "type": "given",
                    "date": item.given_date,
                    "label": "Given away",
                    "detail": format_given_detail(item.recipient, item.given_occasion),
                }
            )
        elif item.finished_date:
            event_type = "finished"
            label = "Broken or lost"
            if item.removal_reason in ("", WhiskyStorageItem.RemovalReason.CONSUMED):
                label = "Finished"
            elif item.removal_reason != WhiskyStorageItem.RemovalReason.REMOVED:
                label = "Removed from inventory"
            else:
                event_type = "removed"
            events.append(
                {
                    "type": event_type,
                    "date": item.finished_date,
                    "label": label,
                    "detail": "",
                }
            )

        context["events"] = sorted(events, key=lambda e: e["date"])
        context["beverage"] = item.whisky
        context["beverage_detail_url"] = reverse(
            "whisky-detail", kwargs={"pk": item.whisky.pk}
        )
        context["is_whisky"] = True
        return context

import base64
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.forms import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, FormView, ListView, TemplateView
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
    BaseMergeConfirmView,
    BaseQRCodeView,
    BaseRandomBottleView,
    BaseReorderReminderCreateView,
    BaseReorderReminderDeleteView,
    BaseReorderRemindersView,
    BaseScanView,
    BaseStatsDashboardView,
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
    RequireMemberMixin,
    require_member,
)
from wine_cellar.apps.storage.models import Storage, get_app_type
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.whisky.filters import WhiskyFilter, WhiskyStorageItemFilter
from wine_cellar.apps.whisky.forms import (
    POST_DRINK_STATUS_CONSUMED,
    WhiskyDrinkRecordForm,
    WhiskyEditForm,
    WhiskyForm,
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

    def resolve_extracted_data(self, result_data, initial):
        if "distillery" in result_data and isinstance(result_data["distillery"], str):
            match = Distillery.objects.filter(
                name__iexact=result_data["distillery"]
            ).first()
            if match:
                result_data["distillery"] = match.pk
            else:
                result_data.pop("distillery")
        if "region" in result_data and isinstance(result_data["region"], str):
            match = WhiskyRegion.objects.filter(
                name__iexact=result_data["region"]
            ).first()
            if match:
                result_data["region"] = match.pk
            else:
                result_data.pop("region")
        if "bottler" in result_data and isinstance(result_data["bottler"], str):
            match = Bottler.objects.filter(name__iexact=result_data["bottler"]).first()
            if match:
                result_data["bottler"] = match.pk
            else:
                result_data.pop("bottler")

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

        # Handle images
        image_front_label = cleaned_data.get("image_front_label")
        if image_front_label:
            WhiskyImage.objects.get_or_create(
                image=image_front_label,
                whisky=whisky,
                user=user,
                image_type=WhiskyImage.ImageType.LABEL_FRONT,
            )

        image_back_label = cleaned_data.get("image_back_label")
        if image_back_label:
            WhiskyImage.objects.get_or_create(
                image=image_back_label,
                whisky=whisky,
                user=user,
                image_type=WhiskyImage.ImageType.LABEL_BACK,
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

    def _link_extraction_log(self, beverage, cleaned_data, extraction_result):
        """Link the most recent WhiskyVisionExtractionLog to the created whisky."""
        from wine_cellar.apps.whisky.models import WhiskyVisionExtractionLog

        try:
            log = (
                WhiskyVisionExtractionLog.objects.filter(
                    user=self.request.user, whisky__isnull=True
                )
                .order_by("-created")
                .first()
            )
            if log:
                extracted_data = extraction_result.get("extracted_data", {})
                corrections = self._detect_corrections(cleaned_data, extracted_data)
                log.whisky = beverage
                log.was_successful = True
                if corrections:
                    log.user_corrections = corrections
                log.save(update_fields=["whisky", "was_successful", "user_corrections"])
        except Exception:
            logger.exception("Failed to link extraction log to whisky %s", beverage.pk)


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

        # Handle images
        image_front_label = cleaned_data.get("image_front_label")
        existing_front = WhiskyImage.objects.filter(
            whisky=whisky, user=user, image_type=WhiskyImage.ImageType.LABEL_FRONT
        ).first()

        if image_front_label is False:
            # User explicitly cleared the image
            if existing_front:
                existing_front.image.delete()
                existing_front.delete()
        elif image_front_label and not hasattr(image_front_label, "instance"):
            # User uploaded a new image
            if existing_front:
                existing_front.image.delete()
                existing_front.delete()
            WhiskyImage.objects.create(
                image=image_front_label,
                whisky=whisky,
                user=user,
                image_type=WhiskyImage.ImageType.LABEL_FRONT,
            )

        image_back_label = cleaned_data.get("image_back_label")
        existing_back = WhiskyImage.objects.filter(
            whisky=whisky, user=user, image_type=WhiskyImage.ImageType.LABEL_BACK
        ).first()

        if image_back_label is False:
            if existing_back:
                existing_back.image.delete()
                existing_back.delete()
        elif image_back_label and not hasattr(image_back_label, "instance"):
            if existing_back:
                existing_back.image.delete()
                existing_back.delete()
            WhiskyImage.objects.create(
                image=image_back_label,
                whisky=whisky,
                user=user,
                image_type=WhiskyImage.ImageType.LABEL_BACK,
            )


class WhiskyDetailView(BaseDetailView):
    template_name = "whisky/whisky_detail.html"
    model = Whisky
    select_related_fields = ("distillery", "region", "bottler", "source")
    prefetch_related_fields = ("cask_history", "images", "barcodes", "collections")
    storage_item_reverse = "whiskystorageitem"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["all_collections"] = Collection.objects.filter(
            household=household
        ).order_by("name")
        from wine_cellar.apps.whisky.models import WhiskyVisionExtractionLog

        extraction_log = (
            WhiskyVisionExtractionLog.objects.filter(
                whisky=self.object, was_successful=True
            )
            .order_by("-created")
            .first()
        )
        if extraction_log:
            context["extraction_log"] = extraction_log
        return context


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
        """Resolve distillery, region, bottler strings to PKs for TomSelect."""
        if "distillery" in data and isinstance(data["distillery"], str):
            match = Distillery.objects.filter(name__iexact=data["distillery"]).first()
            if match:
                data["distillery"] = match.pk
            else:
                data["distillery_name"] = data.pop("distillery")
        if "region" in data and isinstance(data["region"], str):
            match = WhiskyRegion.objects.filter(name__iexact=data["region"]).first()
            if match:
                data["region"] = match.pk
            else:
                data["region_name"] = data.pop("region")
        if "bottler" in data and isinstance(data["bottler"], str):
            match = Bottler.objects.filter(name__iexact=data["bottler"]).first()
            if match:
                data["bottler"] = match.pk
            else:
                data["bottler_name"] = data.pop("bottler")

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
            storage_item.save(update_fields=["deleted"])
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


class StorageItemAddView(RequireMemberMixin, FormView):
    """Add a bottle to storage."""

    template_name = "whisky/stock_add.html"
    form_class = WhiskyStockAddForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        household = get_active_household(self.request.user)
        kwargs["whisky"] = get_object_or_404(
            Whisky, pk=self.kwargs["pk"], household=household
        )
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        context["whisky"] = whisky

        # Provide free cells for storage dropdown
        user_storages = Storage.objects.filter(
            household=household, app_type=get_app_type()
        )
        free_cells_by_storage = {
            storage.pk: storage.get_free_cells_by_row() for storage in user_storages
        }
        context["free_cells_by_storage"] = free_cells_by_storage
        return context

    def form_valid(self, form):
        import datetime

        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        fill_level = form.cleaned_data["fill_level"]
        dreg_date = datetime.date.today() if fill_level == FillLevel.DREG else None

        WhiskyStorageItem.objects.create(
            storage=form.cleaned_data["storage"],
            whisky=whisky,
            row=form.cleaned_data.get("row"),
            column=form.cleaned_data.get("column"),
            user=self.request.user,
            household=household,
            price=form.cleaned_data.get("price"),
            is_gift=form.cleaned_data.get("is_gift", False),
            gift_from=form.cleaned_data.get("gift_from"),
            occasion=form.cleaned_data.get("occasion"),
            rating=form.cleaned_data.get("rating"),
            fill_level=fill_level,
            dreg_date=dreg_date,
            owner=form.cleaned_data.get("owner", ""),
        )

        self.success_url = reverse_lazy("whisky-detail", kwargs={"pk": whisky.pk})
        return super().form_valid(form)


class StorageItemDeleteView(RequireMemberMixin, DeleteView):
    """Remove a bottle from storage."""

    template_name = "whisky/stock_confirm_delete.html"

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return WhiskyStorageItem.objects.filter(household=household)

    def get_success_url(self):
        return reverse_lazy("whisky-detail", kwargs={"pk": self.object.whisky.pk})


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
            WhiskyStorageItem.objects.filter(household=household, deleted=False)
            .select_related("whisky", "storage")
            .order_by("-created")
        )


class StorageItemUpdateView(RequireMemberMixin, FormView):
    """Edit a bottle (e.g., update fill level)."""

    template_name = "whisky/bottle_edit.html"
    form_class = WhiskyStockAddForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        household = get_active_household(self.request.user)
        item = get_object_or_404(
            WhiskyStorageItem, pk=self.kwargs["pk"], household=household
        )
        kwargs["whisky"] = item.whisky
        return kwargs

    def get_initial(self):
        household = get_active_household(self.request.user)
        item = get_object_or_404(
            WhiskyStorageItem, pk=self.kwargs["pk"], household=household
        )
        return model_to_dict(item)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        item = get_object_or_404(
            WhiskyStorageItem, pk=self.kwargs["pk"], household=household
        )
        context["storage_item"] = item
        context["whisky"] = item.whisky

        # Provide free cells for storage dropdown - exclude current item so its
        # position shows as available
        user_storages = Storage.objects.filter(
            household=household, app_type=get_app_type()
        )
        free_cells_by_storage = {
            storage.pk: storage.get_free_cells_by_row(exclude_item=item)
            for storage in user_storages
        }
        context["free_cells_by_storage"] = free_cells_by_storage
        return context

    def form_valid(self, form):
        import datetime

        household = get_active_household(self.request.user)
        item = get_object_or_404(
            WhiskyStorageItem, pk=self.kwargs["pk"], household=household
        )

        old_fill_level = item.fill_level
        new_fill_level = form.cleaned_data["fill_level"]

        item.storage = form.cleaned_data["storage"]
        item.row = form.cleaned_data.get("row")
        item.column = form.cleaned_data.get("column")
        item.price = form.cleaned_data.get("price")
        item.is_gift = form.cleaned_data.get("is_gift", False)
        item.gift_from = form.cleaned_data.get("gift_from")
        item.occasion = form.cleaned_data.get("occasion")
        item.rating = form.cleaned_data.get("rating")
        item.fill_level = new_fill_level

        # Track dreg_date transitions
        if new_fill_level == FillLevel.DREG and old_fill_level != FillLevel.DREG:
            item.dreg_date = datetime.date.today()
        elif new_fill_level != FillLevel.DREG and old_fill_level == FillLevel.DREG:
            item.dreg_date = None

        item.owner = form.cleaned_data.get("owner", "")
        item.save()

        self.success_url = reverse_lazy("whisky-detail", kwargs={"pk": item.whisky.pk})
        return super().form_valid(form)


class StorageItemHistoryView(RequireHouseholdMixin, ListView):
    """List deleted (removed) whisky storage items."""

    model = WhiskyStorageItem
    template_name = "whisky/stock_history.html"
    context_object_name = "storage_items"
    paginate_by = 10

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return (
            WhiskyStorageItem.objects.filter(household=household, deleted=True)
            .select_related("whisky", "storage")
            .order_by("-created")
        )


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

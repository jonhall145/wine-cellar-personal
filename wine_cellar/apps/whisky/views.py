import base64
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models.functions import Coalesce
from django.forms import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.formats import number_format
from django.views.generic import DeleteView, FormView, ListView, TemplateView
from django_filters.views import FilterView
from django_ratelimit.decorators import ratelimit

from wine_cellar.apps.core.views import (
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
    BaseImagesView,
    BaseListView,
    BaseReorderReminderCreateView,
    BaseReorderReminderDeleteView,
    BaseReorderRemindersView,
    BaseScanView,
    BaseWishlistCreateView,
    BaseWishlistDeleteView,
    BaseWishlistListView,
    BaseWishlistPurchasedView,
    crop_image_ajax,
    set_primary_image_ajax,
)
from wine_cellar.apps.household.mixins import RequireHouseholdMixin, RequireMemberMixin
from wine_cellar.apps.storage.models import Storage, get_app_type
from wine_cellar.apps.user.views import get_active_household, get_user_settings
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

# Maximum allowed image upload size (10MB)
MAX_IMAGE_SIZE = 10 * 1024 * 1024

logger = logging.getLogger(__name__)


class HomePageView(RequireHouseholdMixin, TemplateView):
    template_name = "whisky/homepage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        household = get_active_household(user)

        # Get total whiskies count separately
        whiskies = Whisky.objects.filter(household=household).count()

        # Get other whisky stats
        whisky_stats = Whisky.objects.filter(household=household).aggregate(
            whiskies_in_stock=Count(
                "id", filter=Q(whiskystorageitem__deleted=False), distinct=True
            ),
            distilleries=Count("distillery", distinct=True),
            oldest_vintage=Min("vintage_year", filter=Q(vintage_year__isnull=False)),
            youngest_vintage=Max("vintage_year", filter=Q(vintage_year__isnull=False)),
        )

        whiskies_in_stock = whisky_stats["whiskies_in_stock"]
        distilleries_count = whisky_stats["distilleries"]
        oldest = whisky_stats["oldest_vintage"] or "-"
        youngest = whisky_stats["youngest_vintage"] or "-"

        total_value = WhiskyStorageItem.objects.aggregate(
            total=Sum(
                Coalesce("price", "whisky__price"),
                filter=Q(deleted=False, household=household),
            )
        )["total"] or Decimal("0")
        total_value = total_value.quantize(Decimal("0"))
        user_settings = get_user_settings(self.request.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )

        formatted_price = number_format(total_value, use_l10n=True)
        total_value = f"{currency}{formatted_price}"

        # Calculate bottles in stock
        bottles_in_stock = WhiskyStorageItem.objects.filter(
            household=household, deleted=False
        ).count()

        # Open bottles (not Unopened fill level)
        open_bottles = (
            WhiskyStorageItem.objects.filter(household=household, deleted=False)
            .exclude(fill_level="UN")
            .count()
        )

        # Oldest age statement
        oldest_age_result = Whisky.objects.filter(
            household=household,
            age_statement__isnull=False,
        ).aggregate(Max("age_statement"))
        oldest_age = oldest_age_result["age_statement__max"] or 0

        # Dreg alerts
        import datetime

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

        context.update(
            {
                "whiskies": whiskies,
                "whiskies_in_stock": whiskies_in_stock,
                "bottles_in_stock": bottles_in_stock,
                "distilleries_count": distilleries_count,
                "open_bottles": open_bottles,
                "oldest_age": oldest_age,
                "oldest": oldest,
                "youngest": youngest,
                "total_value": total_value,
                "dreg_expired_count": dreg_expired_count,
                "dreg_warning_count": dreg_warning_count,
            }
        )

        # Low stock reminders
        low_stock_count = (
            WhiskyReorderReminder.objects.filter(household=household, is_active=True)
            .annotate(
                current_stock=Count(
                    "whisky__whiskystorageitem",
                    filter=Q(whisky__whiskystorageitem__deleted=False),
                )
            )
            .filter(current_stock__lte=F("min_stock"))
            .count()
        )

        # Recent drinks
        recent_drinks = (
            WhiskyDrinkRecord.objects.filter(household=household)
            .select_related("whisky")
            .order_by("-date_consumed")[:3]
        )

        # Wishlist
        wishlist_items = WhiskyWishlist.objects.filter(
            household=household, purchased=False
        ).order_by("-priority")[:3]

        # Stats
        drink_stats = WhiskyDrinkRecord.objects.filter(household=household).aggregate(
            total_consumed=Count("id"),
            avg_rating=Avg("rating", filter=Q(rating__isnull=False)),
        )
        total_consumed = drink_stats["total_consumed"]
        avg_rating = (
            round(drink_stats["avg_rating"], 1) if drink_stats["avg_rating"] else None
        )

        context.update(
            {
                "low_stock_count": low_stock_count,
                "recent_drinks": recent_drinks,
                "wishlist_items": wishlist_items,
                "total_consumed": total_consumed,
                "total_bottles": bottles_in_stock,
                "avg_rating": avg_rating,
            }
        )

        return context


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


class WhiskyUpdateView(BaseBeverageUpdateView):
    template_name = "whisky/whisky_edit.html"
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
    prefetch_related_fields = ("cask_history", "images", "barcodes")
    storage_item_reverse = "whiskystorageitem"


class WhiskyDeleteView(BaseBeverageDeleteView):
    model = Whisky
    template_name = "whisky/whisky_confirm_delete.html"
    success_url = reverse_lazy("whisky-list")


class WhiskyListView(BaseListView, FilterView):
    model = Whisky
    template_name = "whisky/whisky_list.html"
    context_object_name = "whiskies"
    filterset_class = WhiskyFilter
    storage_item_reverse = "whiskystorageitem"
    select_related_fields = ("distillery", "region", "bottler")
    prefetch_related_fields = ("images",)


class WhiskyScanView(BaseScanView):
    template_name = "whisky/scan_whisky.html"


class WhiskyScannedView(RequireHouseholdMixin, TemplateView):
    template_name = "whisky/scanned_whisky.html"

    def dispatch(self, request, *args, **kwargs):
        code = self.kwargs["code"]
        # Placeholder barcode lookup
        household = get_active_household(request.user)
        whiskies = Whisky.objects.filter(barcodes__barcode=code, household=household)

        if whiskies.exists():
            if whiskies.count() == 1:
                whisky = whiskies.first()
                return redirect(reverse("whisky-detail", kwargs={"pk": whisky.pk}))
            # Multiple matches
            self.extra_context = {"whiskies": whiskies, "barcode": code}
            return super().dispatch(request, *args, **kwargs)

        # No matches
        request.session["pending_barcode"] = code
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


class LabelScanView(RequireHouseholdMixin, TemplateView):
    template_name = "whisky/label_scan.html"

    def post(self, request, *args, **kwargs):
        import base64

        # Clear any previous extraction results
        if "extraction_result" in request.session:
            del request.session["extraction_result"]

        # Handle camera capture data (multiple images from React component)
        image_count = request.POST.get("image_count")
        if image_count:
            images = []
            for i in range(int(image_count)):
                image_data = request.POST.get(f"image_data_{i}")
                if image_data:
                    if "," in image_data:
                        image_data = image_data.split(",")[1]
                    images.append(image_data)

            if images:
                request.session["scanned_label"] = {
                    "filename": "camera_captures.jpg",
                    "size": sum(len(base64.b64decode(img)) for img in images),
                    "data": images,
                    "multi_image": True,
                }
                return redirect("whisky-add")

        # Handle file uploads
        images = []
        for field_name in ["barcode_image", "front_image", "back_image"]:
            image = request.FILES.get(field_name)
            if image:
                image_data = image.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                images.append(base64_image)

        if images:
            request.session["scanned_label"] = {
                "filename": "uploaded_images",
                "size": sum(len(base64.b64decode(img)) for img in images),
                "data": images,
                "multi_image": len(images) > 1,
            }
            return redirect("whisky-add")

        # No images submitted, re-render the page
        return self.get(request, *args, **kwargs)


@ratelimit(key="user", rate="10/m", method="POST", block=True)
@login_required
def extract_whisky_vision_ajax(request):
    """
    AJAX endpoint for whisky data extraction from uploaded images.

    Attempts barcode scanning first (non-AI, faster), then falls back
    to AI vision extraction if no barcode match is found.

    Rate limited to 10 requests per minute per user.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        # Collect uploaded images
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
                        {
                            "error": f"Image {field_name} is too large. "
                            f"Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)}MB."
                        },
                        status=400,
                    )
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                images.append(base64_image)
                image_file.seek(0)

        if not images:
            return JsonResponse(
                {"error": "No images uploaded. Please select at least one image."},
                status=400,
            )

        # Step 1: Try barcode scanning first (non-AI, faster)
        from wine_cellar.apps.whisky.services.barcode_service import (
            WhiskyBarcodeScanner,
        )

        barcode_scanner = WhiskyBarcodeScanner()
        barcode_result = barcode_scanner.scan_and_match(images, request.user)

        if barcode_result.get("matched"):
            if barcode_result.get("multiple_matches"):
                return JsonResponse(
                    {
                        "success": True,
                        "multiple_matches": True,
                        "match_type": "barcode",
                        "matched_barcode": barcode_result["barcode"],
                        "whiskies": barcode_result["whiskies"],
                        "message": "Multiple whiskies found with this barcode",
                    }
                )

            whisky_data = barcode_result["whisky_data"]
            extracted_fields = list(whisky_data.keys())

            return JsonResponse(
                {
                    "success": True,
                    "data": whisky_data,
                    "confidence": "high",
                    "extracted_fields": extracted_fields,
                    "errors": [],
                    "match_type": "barcode",
                    "matched_barcode": barcode_result["barcode"],
                    "message": (
                        f"Matched whisky via barcode: " f"{barcode_result['barcode']}"
                    ),
                }
            )

        # Step 2: No barcode match, use AI vision extraction
        from wine_cellar.apps.whisky.services.vision_extraction import (
            WhiskyVisionExtractor,
        )

        extractor = WhiskyVisionExtractor()
        result = extractor.extract_from_images(images, user=request.user)

        # Resolve FK fields (distillery, region, bottler) to PKs for TomSelect
        data = result.get("data", {})
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

        response_data = {
            "success": True,
            "data": data,
            "confidence": result.get("confidence", "low"),
            "extracted_fields": result.get("extracted_fields", []),
            "errors": result.get("errors", []),
            "match_type": "vision",
        }

        # If barcodes were found but didn't match, include them
        if barcode_result.get("all_barcodes"):
            barcodes = barcode_result["all_barcodes"]
            if barcodes and "barcode" not in response_data["data"]:
                response_data["data"]["barcode"] = barcodes[0]
                if "barcode" not in response_data["extracted_fields"]:
                    response_data["extracted_fields"].append("barcode")

        return JsonResponse(response_data)

    except Exception:
        logger.exception("Error in whisky AJAX vision extraction")
        return JsonResponse({"error": "Vision extraction failed"}, status=500)


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
    template_name = "whisky/drink_record_create.html"
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
    template_name = "whisky/drink_record_list.html"
    drink_record_model = WhiskyDrinkRecord
    beverage_fk_name = "whisky"


class DrinkRecordEditView(BaseDrinkRecordEditView):
    template_name = "whisky/drink_record_edit.html"
    form_class = WhiskyDrinkRecordForm
    drink_record_model = WhiskyDrinkRecord
    beverage_fk_name = "whisky"


class DrinkRecordDeleteView(BaseDrinkRecordDeleteView):
    model = WhiskyDrinkRecord
    template_name = "whisky/drink_record_confirm_delete.html"


class WishlistListView(BaseWishlistListView):
    template_name = "whisky/wishlist_list.html"
    wishlist_model = WhiskyWishlist


class WishlistCreateView(BaseWishlistCreateView):
    template_name = "whisky/wishlist_create.html"
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
    template_name = "whisky/cellar_value.html"
    storage_item_model = WhiskyStorageItem
    price_fallback_path = "whisky__price"
    beverage_fk_name = "whisky"
    select_related_fields = ("whisky__distillery",)

    def get_groupings(self, item):
        return {
            "by_distillery": (
                item.whisky.distillery.name if item.whisky.distillery else "Unknown"
            ),
            "by_type": item.whisky.get_whisky_type_display(),
        }


class ConsumptionStatsView(BaseConsumptionStatsView):
    template_name = "whisky/consumption_stats.html"
    drink_record_model = WhiskyDrinkRecord
    beverage_fk_name = "whisky"
    select_related_fields = ("whisky__distillery",)

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
        return {"by_distillery": dict(by_distillery)}


class BottleNoteCreateView(BaseBottleNoteCreateView):
    template_name = "whisky/bottle_note_create.html"
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
    template_name = "whisky/reorder_reminders.html"
    reminder_model = WhiskyReorderReminder
    beverage_fk_name = "whisky"
    stock_reverse_path = "whisky__whiskystorageitem"


class ReorderReminderCreateView(BaseReorderReminderCreateView):
    template_name = "whisky/reorder_reminder_create.html"
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


class WhiskyMergeConfirmView(RequireMemberMixin, TemplateView):
    template_name = "whisky/whisky_merge_confirm.html"

    def get_whiskies(self):
        household = get_active_household(self.request.user)
        qs = Whisky.objects.filter(household=household)
        primary = get_object_or_404(qs, pk=self.kwargs["primary_pk"])
        duplicate = get_object_or_404(qs, pk=self.kwargs["pk"])
        return primary, duplicate

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        primary, duplicate = self.get_whiskies()
        dup_stock = WhiskyStorageItem.objects.filter(
            whisky=duplicate, deleted=False
        ).count()
        dup_barcodes = duplicate.barcodes.count()
        context.update(
            {
                "primary": primary,
                "duplicate": duplicate,
                "dup_stock": dup_stock,
                "dup_barcodes": dup_barcodes,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        primary, duplicate = self.get_whiskies()

        with transaction.atomic():
            # Move bottles
            WhiskyStorageItem.objects.filter(whisky=duplicate).update(whisky=primary)

            # Move barcodes (skip duplicates)
            for barcode in duplicate.barcodes.all():
                if not primary.barcodes.filter(barcode=barcode.barcode).exists():
                    barcode.whisky = primary
                    barcode.save()

            # Move images
            WhiskyImage.objects.filter(whisky=duplicate).update(whisky=primary)

            # Merge M2M fields
            primary.attributes.add(*duplicate.attributes.all())

            # Move FK references
            WhiskyDrinkRecord.objects.filter(whisky=duplicate).update(whisky=primary)
            WhiskyDrinkingWindowAlert.objects.filter(whisky=duplicate).update(
                whisky=primary
            )
            WhiskyPriceHistory.objects.filter(whisky=duplicate).update(whisky=primary)
            WhiskyVisionExtractionLog.objects.filter(whisky=duplicate).update(
                whisky=primary
            )
            # Handle ReorderReminder (unique on whisky+user)
            for reminder in WhiskyReorderReminder.objects.filter(whisky=duplicate):
                if not WhiskyReorderReminder.objects.filter(
                    whisky=primary, user=reminder.user
                ).exists():
                    reminder.whisky = primary
                    reminder.save()
                else:
                    reminder.delete()

            # Delete the duplicate
            duplicate.delete()

        messages.success(
            request,
            f'Merged "{duplicate.name}" into "{primary.name}".',
        )
        return redirect("whisky-detail", pk=primary.pk)


class WhiskyImagesView(BaseImagesView):
    template_name = "whisky/whisky_images.html"
    model = Whisky
    context_object_name = "whisky"
    images_prefetch_name = "images"


@login_required
def set_primary_image(request, pk):
    """Set a WhiskyImage as the primary image for its whisky."""
    return set_primary_image_ajax(request, pk, WhiskyImage)


@login_required
def crop_whisky_image(request, pk):
    """Apply manual crop to a WhiskyImage and create a new thumbnail."""
    return crop_image_ajax(request, pk, WhiskyImage)

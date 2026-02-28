import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.db import connections, transaction
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.formats import number_format
from django.views.generic import FormView, TemplateView
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
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.user.views import get_active_household, get_user_settings
from wine_cellar.apps.wine.filters import WineFilter
from wine_cellar.apps.wine.forms import WineBaseForm, WineEditForm, WineForm
from wine_cellar.apps.wine.models import (
    BottleNote,
    DrinkRecord,
    ReorderReminder,
    Wine,
    WineBarcode,
    WineImage,
    Wishlist,
)
from wine_cellar.apps.wine.services import BarcodeScanner, WineVisionExtractor

logger = logging.getLogger(__name__)

# Form step constants - no longer used for multi-step, kept for compatibility
FINAL_FORM_STEP = 4

# Maximum allowed image upload size (10MB) to prevent memory exhaustion
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB in bytes


class HomePageView(RequireHouseholdMixin, TemplateView):
    template_name = "homepage.html"

    def get_context_data(self, **kwargs):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord, ReorderReminder, Wishlist

        context = super().get_context_data(**kwargs)
        user = self.request.user
        household = get_active_household(user)

        # Get total wines count separately to avoid JOIN issues
        wines = Wine.objects.filter(household=household).count()

        # Get other wine stats
        wine_stats = Wine.objects.filter(household=household).aggregate(
            wines_in_stock=Count(
                "id", filter=Q(storageitem__deleted=False), distinct=True
            ),
            countries=Count("country", distinct=True),
            oldest_vintage=Min("vintage", filter=Q(vintage__isnull=False)),
            youngest_vintage=Max("vintage", filter=Q(vintage__isnull=False)),
            overdue_count=Count(
                "id",
                filter=Q(
                    drink_to__isnull=False,
                    drink_to__gt=0,  # Not "now"
                    drink_to__lt=date.today().year,
                    storageitem__deleted=False,
                ),
                distinct=True,
            ),
            upcoming_count=Count(
                "id",
                filter=Q(
                    drink_to__isnull=False,
                    drink_to__gt=0,  # Not "now"
                    drink_to__gte=date.today().year,
                    drink_to__lte=date.today().year + 1,  # This year or next
                    storageitem__deleted=False,
                ),
                distinct=True,
            ),
        )

        wines_in_stock = wine_stats["wines_in_stock"]
        countries = wine_stats["countries"]
        oldest = wine_stats["oldest_vintage"] or "-"
        youngest = wine_stats["youngest_vintage"] or "-"
        overdue_count = wine_stats["overdue_count"]
        upcoming_count = wine_stats["upcoming_count"]
        total_value = StorageItem.objects.aggregate(
            total=Sum(
                Coalesce("price", "wine__price"),
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
        bottles_in_stock = StorageItem.objects.filter(
            household=household, deleted=False
        ).count()

        context.update(
            {
                "wines": wines,
                "wines_in_stock": wines_in_stock,
                "bottles_in_stock": bottles_in_stock,
                "countries": countries,
                "oldest": oldest,
                "youngest": youngest,
                "total_value": total_value,
            }
        )

        # Low stock reminders - filter at database level for efficiency
        low_stock_count = (
            ReorderReminder.objects.filter(household=household, is_active=True)
            .annotate(
                current_stock=Count(
                    "wine__storageitem", filter=Q(wine__storageitem__deleted=False)
                )
            )
            .filter(current_stock__lte=F("min_stock"))
            .count()
        )

        # Recent drinks
        recent_drinks = (
            DrinkRecord.objects.filter(household=household)
            .select_related("wine")
            .order_by("-date_consumed")[:3]
        )

        # Wishlist
        wishlist_items = Wishlist.objects.filter(
            household=household, purchased=False
        ).order_by("-priority")[:3]

        # Stats - consolidate into single query per model
        drink_stats = DrinkRecord.objects.filter(household=household).aggregate(
            total_consumed=Count("id"),
            avg_rating=Avg("rating", filter=Q(rating__isnull=False)),
        )
        total_consumed = drink_stats["total_consumed"]
        avg_rating = (
            round(drink_stats["avg_rating"], 1) if drink_stats["avg_rating"] else None
        )

        # Pending hardware position reviews (gracefully handle if hardware not set up)
        pending_reviews_count = 0
        try:
            from wine_cellar.apps.hardware.models import (
                PositionChangeReview,
                ReviewStatus,
            )

            pending_reviews_count = PositionChangeReview.objects.filter(
                household=household,
                status=ReviewStatus.PENDING,
            ).count()
        except Exception:
            # Hardware app not configured or migration not run - skip silently
            pass

        context.update(
            {
                "overdue_count": overdue_count,
                "upcoming_count": upcoming_count,
                "low_stock_count": low_stock_count,
                "recent_drinks": recent_drinks,
                "wishlist_items": wishlist_items,
                "total_consumed": total_consumed,
                "total_bottles": bottles_in_stock,
                "avg_rating": avg_rating,
                "pending_reviews_count": pending_reviews_count,
            }
        )

        return context


@method_decorator(
    ratelimit(key="user", rate="20/m", method="POST", block=True), name="post"
)
class WineCreateView(BaseBeverageCreateView):
    """View for creating new wines. Rate limited to 20 creations/minute per user."""

    template_name = "wine_create.html"
    form_class = WineForm
    success_url = reverse_lazy("wine-list")
    vision_extractor_path = "wine_cellar.apps.wine.services.WineVisionExtractor"
    add_url_name = "wine-add"
    beverage_label = "wine"

    def resolve_extracted_data(self, result_data, initial):
        # Vineyard: wrap string in list for form
        if "vineyard" in result_data and isinstance(result_data["vineyard"], str):
            result_data["vineyard"] = [result_data["vineyard"]]
        # Appellation: convert PK to model instance for ModelChoiceField
        if "appellation" in result_data and result_data["appellation"]:
            try:
                from wine_cellar.apps.wine.models import Appellation

                result_data["appellation"] = Appellation.objects.get(
                    pk=result_data["appellation"]
                )
            except (Appellation.DoesNotExist, TypeError):
                result_data.pop("appellation", None)

    def post(self, request, *args, **kwargs):
        """Handle optional vision-based auto-fill before normal form submission."""
        import base64

        if "extract_vision" in request.POST:
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
                    image_data = image_file.read()
                    base64_image = base64.b64encode(image_data).decode("utf-8")
                    images.append(base64_image)
                    image_file.seek(0)

            if images:
                self.request.session["scanned_label"] = {
                    "filename": "uploaded_images.jpg",
                    "size": sum(len(base64.b64decode(img)) for img in images),
                    "data": images,
                    "multi_image": True,
                }
                if "extraction_result" in self.request.session:
                    del self.request.session["extraction_result"]
                return redirect("wine-add")
            else:
                messages.warning(
                    request, "Please upload at least one image before using auto-fill."
                )
                return self.render_to_response(self.get_context_data())

        return super().post(request, *args, **kwargs)

    def post_create(self, beverage, created):
        """Apply AI label bounds as auto-crop thumbnails if confidence is sufficient."""
        if created:
            extraction_result = self.request.session.get("extraction_result")
            if extraction_result:
                confidence = extraction_result.get("confidence", "low")
                if confidence in ("high", "medium"):
                    extracted_data = extraction_result.get("extracted_data", {})
                    self._apply_auto_crop(beverage, extracted_data)

    @staticmethod
    def _apply_auto_crop(wine, extracted_data):
        """Apply AI-extracted label bounds as auto-crop thumbnails."""
        from PIL import Image

        from wine_cellar.apps.wine.models import ImageType
        from wine_cellar.apps.wine.utils import apply_manual_crop

        bounds_map = {
            ImageType.LABEL_FRONT: extracted_data.get("label_bounds_front"),
            ImageType.LABEL_BACK: extracted_data.get("label_bounds_back"),
        }

        for image_type, bounds in bounds_map.items():
            if not bounds:
                continue
            wine_image = wine.wineimage_set.filter(image_type=image_type).first()
            if not wine_image or not wine_image.image:
                continue
            try:
                import os

                from django.conf import settings as django_settings

                full_path = os.path.join(
                    django_settings.MEDIA_ROOT, wine_image.image.name
                )
                with Image.open(full_path) as img:
                    img_width, img_height = img.size

                x = int((bounds["x1"] / 100) * img_width)
                y = int((bounds["y1"] / 100) * img_height)
                width = int(((bounds["x2"] - bounds["x1"]) / 100) * img_width)
                height = int(((bounds["y2"] - bounds["y1"]) / 100) * img_height)

                if width > 0 and height > 0:
                    thumb_path = apply_manual_crop(wine_image, x, y, width, height)
                    wine_image.thumbnail = thumb_path
                    wine_image.save(update_fields=["thumbnail"])
            except Exception:
                logger.exception(
                    f"Auto-crop failed for wine {wine.pk} image type {image_type}"
                )

    @staticmethod
    @transaction.atomic
    def process_form_data(user, household, cleaned_data):
        from wine_cellar.apps.wine.models import Size

        abv = cleaned_data["abv"]
        size_code = cleaned_data["size"]
        # Get or create the Size object for this user
        size = None
        if size_code:
            size, _ = Size.objects.get_or_create(name=size_code, user=None)
        category = cleaned_data["category"] or None  # Convert empty string to None
        barcode = cleaned_data["barcode"]
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        subregion = cleaned_data["subregion"]
        appellation = cleaned_data.get("appellation")
        food_pairings = cleaned_data["food_pairings"]
        source = cleaned_data["source"]
        price = cleaned_data["price"]
        vineyards = cleaned_data["vineyard"]
        grapes = cleaned_data["grapes"]
        name = cleaned_data["name"]
        rating = cleaned_data["rating"]
        vintage = cleaned_data["vintage"]
        wine_type = cleaned_data["wine_type"]
        attributes = cleaned_data["attributes"]
        drink_from = cleaned_data["drink_from"]
        drink_to = cleaned_data["drink_to"]

        # Use get_or_create to handle duplicate wines gracefully
        # Unique constraint fields: name, wine_type, abv, size, vintage, country, user
        wine, created = Wine.objects.get_or_create(
            name=name,
            wine_type=wine_type,
            abv=abv,
            size=size,
            vintage=vintage,
            country=country,
            user=user,
            household=household,
            defaults={
                "category": category,
                "subregion": subregion,
                "appellation": appellation,
                "drink_from": drink_from,
                "drink_to": drink_to,
                "comment": comment,
                "rating": rating,
                "price": price,
            },
        )

        # Create barcode entry if provided
        if barcode:
            WineBarcode.objects.get_or_create(
                barcode=barcode,
                user=user,
                defaults={"wine": wine, "household": household},
            )

        wine.vineyard.set(vineyards)
        wine.grapes.set(grapes)
        wine.food_pairings.set(food_pairings)
        wine.source.set(source)
        wine.attributes.set(attributes)

        for form_field, image_type in WineBaseForm.image_fields_map.items():
            image = cleaned_data.get(form_field)
            if image:
                WineImage.objects.get_or_create(
                    image=image, wine=wine, user=user, image_type=image_type
                )

        # Handle storage (add bottle to cellar) if provided
        storage = cleaned_data.get("storage")
        if storage:
            row = cleaned_data.get("row")
            column = cleaned_data.get("column")
            bottle_price = cleaned_data.get("bottle_price") or price
            is_gift = cleaned_data.get("is_gift", False)
            gift_from = cleaned_data.get("gift_from")
            occasion = cleaned_data.get("occasion")
            StorageItem.objects.create(
                storage=storage,
                wine=wine,
                row=row,
                column=column,
                user=user,
                household=household,
                price=bottle_price,
                is_gift=is_gift,
                gift_from=gift_from,
                occasion=occasion,
            )

        return wine, created


class WineUpdateView(BaseBeverageUpdateView):
    template_name = "wine_edit.html"
    form_class = WineEditForm
    success_url = reverse_lazy("wine-list")
    beverage_model = Wine
    beverage_fk_name = "wine"
    image_related_name = "wineimage_set"
    detail_url_name = "wine-detail"

    @staticmethod
    @transaction.atomic
    def process_form_data(wine, user, cleaned_data):
        from wine_cellar.apps.wine.models import Size

        abv = cleaned_data["abv"]
        size_code = cleaned_data["size"]
        # Get or create the Size object
        size = None
        if size_code:
            size, _ = Size.objects.get_or_create(name=size_code, user=None)
        category = cleaned_data["category"] or None  # Convert empty string to None
        barcode = cleaned_data["barcode"]
        barcode_2 = cleaned_data.get("barcode_2")
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        subregion = cleaned_data["subregion"]
        appellation = cleaned_data.get("appellation")
        food_pairings = cleaned_data["food_pairings"]
        source = cleaned_data["source"]
        price = cleaned_data["price"]
        vineyards = cleaned_data["vineyard"]
        grapes = cleaned_data["grapes"]
        name = cleaned_data["name"]
        rating = cleaned_data["rating"]
        vintage = cleaned_data["vintage"]
        drink_from = cleaned_data["drink_from"]
        drink_to = cleaned_data["drink_to"]
        wine_type = cleaned_data["wine_type"]
        attributes = cleaned_data["attributes"]

        wine.abv = abv
        wine.size = size
        wine.category = category
        wine.comment = comment
        wine.country = country
        wine.subregion = subregion
        wine.appellation = appellation
        wine.name = name
        wine.rating = rating
        wine.vintage = vintage
        wine.drink_from = drink_from
        wine.drink_to = drink_to
        wine.wine_type = wine_type
        wine.price = price
        wine.save()

        # Create barcode entries if provided
        if barcode:
            WineBarcode.objects.get_or_create(
                barcode=barcode,
                user=user,
                defaults={"wine": wine, "household": wine.household},
            )
        if barcode_2:
            WineBarcode.objects.get_or_create(
                barcode=barcode_2,
                user=user,
                defaults={"wine": wine, "household": wine.household},
            )

        wine.vineyard.set(vineyards)
        wine.grapes.set(grapes)
        wine.food_pairings.set(food_pairings)
        wine.attributes.set(attributes)
        wine.source.set(source)

        for form_field, image_type in WineBaseForm.image_fields_map.items():
            image = cleaned_data.get(form_field)
            existing_image = WineImage.objects.filter(
                wine=wine, user=user, image_type=image_type
            ).first()

            # image is False: user checked "clear" checkbox - delete existing
            # image is None: no action taken - preserve existing
            # image has "instance" attr: existing file unchanged - preserve
            # image is new file (InMemoryUploadedFile): replace existing
            if image is False:
                # User explicitly cleared the image
                if existing_image:
                    existing_image.image.delete()
                    existing_image.delete()
            elif image and not hasattr(image, "instance"):
                # User uploaded a new image - delete old and create new
                if existing_image:
                    existing_image.image.delete()
                    existing_image.delete()
                WineImage.objects.create(
                    image=image, wine=wine, user=user, image_type=image_type
                )


class WineDetailView(BaseDetailView):
    template_name = "wine_detail.html"
    model = Wine
    select_related_fields = ("size", "appellation")
    prefetch_related_fields = (
        "grapes",
        "attributes",
        "food_pairings",
        "wineimage_set",
        "vineyard",
        "source",
        "barcodes",
    )
    storage_item_reverse = "storageitem"


class WineImagesView(BaseImagesView):
    template_name = "wine_images.html"
    model = Wine
    context_object_name = "wine"
    images_prefetch_name = "wineimage_set"


class WineListView(BaseListView, FilterView):
    model = Wine
    template_name = "wine_list.html"
    context_object_name = "wines"
    filterset_class = WineFilter
    storage_item_reverse = "storageitem"
    select_related_fields = ("size", "appellation")
    prefetch_related_fields = ("grapes", "attributes", "food_pairings", "wineimage_set")


class WineScanView(BaseScanView):
    template_name = "scan_wine.html"


class WineScannedView(RequireHouseholdMixin, TemplateView):
    template_name = "scanned_wine.html"

    def dispatch(self, request, *args, **kwargs):
        code = self.kwargs["code"]
        scanner = BarcodeScanner()
        wines = scanner.get_wines_by_barcode(code, self.request.user)

        if wines is not None and wines.exists():
            if wines.count() == 1:
                return redirect(reverse("wine-detail", kwargs={"pk": wines.first().pk}))
            # Multiple matches — fall through to render selection template
            self.extra_context = {"wines": wines, "barcode": code}
            return super().dispatch(request, *args, **kwargs)

        # No matches — store barcode in session for label scan flow
        request.session["pending_barcode"] = code
        return super().dispatch(request, *args, **kwargs)


class WineDeleteView(BaseBeverageDeleteView):
    model = Wine
    template_name = "wine_confirm_delete.html"
    success_url = reverse_lazy("wine-list")


class WineMergeConfirmView(RequireMemberMixin, TemplateView):
    template_name = "wine_merge_confirm.html"

    def get_wines(self):
        household = get_active_household(self.request.user)
        qs = Wine.objects.filter(household=household)
        primary = get_object_or_404(qs, pk=self.kwargs["primary_pk"])
        duplicate = get_object_or_404(qs, pk=self.kwargs["pk"])
        return primary, duplicate

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        primary, duplicate = self.get_wines()
        dup_stock = StorageItem.objects.filter(wine=duplicate, deleted=False).count()
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
        from wine_cellar.apps.wine.models import (
            DrinkingWindowAlert,
            DrinkRecord,
            PriceHistory,
            ReorderReminder,
            VisionExtractionLog,
        )

        primary, duplicate = self.get_wines()

        with transaction.atomic():
            # Move bottles
            StorageItem.objects.filter(wine=duplicate).update(wine=primary)

            # Move barcodes (skip duplicates)
            for barcode in duplicate.barcodes.all():
                if not primary.barcodes.filter(barcode=barcode.barcode).exists():
                    barcode.wine = primary
                    barcode.save()

            # Move images
            WineImage.objects.filter(wine=duplicate).update(wine=primary)

            # Merge M2M fields
            primary.grapes.add(*duplicate.grapes.all())
            primary.attributes.add(*duplicate.attributes.all())
            primary.food_pairings.add(*duplicate.food_pairings.all())
            primary.vineyard.add(*duplicate.vineyard.all())
            primary.source.add(*duplicate.source.all())

            # Move FK references
            DrinkRecord.objects.filter(wine=duplicate).update(wine=primary)
            DrinkingWindowAlert.objects.filter(wine=duplicate).update(wine=primary)
            PriceHistory.objects.filter(wine=duplicate).update(wine=primary)
            VisionExtractionLog.objects.filter(wine=duplicate).update(wine=primary)

            # Handle ReorderReminder (unique on wine+user)
            for reminder in ReorderReminder.objects.filter(wine=duplicate):
                if not ReorderReminder.objects.filter(
                    wine=primary, user=reminder.user
                ).exists():
                    reminder.wine = primary
                    reminder.save()
                else:
                    reminder.delete()

            # Delete the duplicate
            duplicate.delete()

        messages.success(
            request,
            f'Merged "{duplicate.name}" into "{primary.name}".',
        )
        return redirect("wine-detail", pk=primary.pk)


class WineMapView(RequireHouseholdMixin, TemplateView):
    template_name = "wine_map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        # Only show wines that are currently in stock (have non-deleted storage items)
        wines = Wine.objects.filter(
            household=household,
            storageitem__isnull=False,
            storageitem__deleted=False,
        ).distinct()

        context.update(
            {
                "wines": wines,
            }
        )
        return context


@login_not_required
def health_check(request):
    """Health check endpoint for container orchestration and monitoring.

    Checks:
    - Database connectivity
    - Disk space for media uploads
    """
    import shutil

    health = {
        "status": "ok",
        "database": "ok",
        "disk": "ok",
    }
    status_code = 200

    # Check database connectivity
    try:
        for conn in connections.all():
            conn.ensure_connection()
    except Exception:
        health["database"] = "unhealthy"
        health["status"] = "unhealthy"
        status_code = 503

    # Check disk space for media uploads
    try:
        media_root = getattr(settings, "MEDIA_ROOT", "/tmp")
        disk_usage = shutil.disk_usage(media_root)
        free_gb = disk_usage.free / (1024**3)
        health["disk_free_gb"] = round(free_gb, 2)
        # Warn if less than 1GB free
        if free_gb < 1:
            health["disk"] = "low"
            if free_gb < 0.1:  # Critical if less than 100MB
                health["disk"] = "critical"
                health["status"] = "unhealthy"
                status_code = 503
    except Exception:
        health["disk"] = "unknown"

    return JsonResponse(health, status=status_code)


class DrinkRecordCreateView(BaseDrinkRecordCreateView):
    template_name = "drink_record_create.html"
    beverage_model = Wine
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import DrinkRecordForm

        return DrinkRecordForm


class DrinkRecordListView(BaseDrinkRecordListView):
    template_name = "drink_record_list.html"
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"


class DrinkRecordEditView(BaseDrinkRecordEditView):
    template_name = "drink_record_edit.html"
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import DrinkRecordForm

        return DrinkRecordForm


class DrinkRecordDeleteView(BaseDrinkRecordDeleteView):
    model = DrinkRecord
    template_name = "drink_record_confirm_delete.html"


class WishlistListView(BaseWishlistListView):
    template_name = "wishlist_list.html"
    wishlist_model = Wishlist


class WishlistCreateView(BaseWishlistCreateView):
    template_name = "wishlist_create.html"
    wishlist_model = Wishlist

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import WishlistForm

        return WishlistForm

    def get_extra_create_kwargs(self, form):
        return {
            "wine_type": form.cleaned_data.get("wine_type") or None,
            "country": form.cleaned_data.get("country") or None,
            "subregion": form.cleaned_data.get("subregion"),
            "vintage": form.cleaned_data.get("vintage"),
        }


class WishlistDeleteView(BaseWishlistDeleteView):
    model = Wishlist
    template_name = "wishlist_confirm_delete.html"


class WishlistPurchasedView(BaseWishlistPurchasedView):
    wishlist_model = Wishlist


class CellarValueView(BaseCellarValueView):
    template_name = "cellar_value.html"
    storage_item_model = StorageItem
    price_fallback_path = "wine__price"
    beverage_fk_name = "wine"
    select_related_fields = ("wine",)

    def get_groupings(self, item):
        return {
            "by_country": item.wine.country_name if item.wine.country else "Unknown",
            "by_type": item.wine.get_type if item.wine.wine_type else "Unknown",
        }


class BottleNoteCreateView(BaseBottleNoteCreateView):
    template_name = "bottle_note_create.html"
    storage_item_model = StorageItem
    note_model = BottleNote
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"


class DrinkingWindowAlertsView(RequireHouseholdMixin, TemplateView):
    template_name = "drinking_window_alerts.html"

    def get_context_data(self, **kwargs):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkingWindowAlert

        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)

        # Get existing alerts
        alerts = DrinkingWindowAlert.objects.filter(
            household=household, is_read=False
        ).select_related("wine")

        current_year = date.today().year

        # Find wines approaching end of drinking window (this year or next)
        upcoming_wines = (
            Wine.objects.filter(
                household=household,
                drink_to__isnull=False,
                drink_to__gt=0,  # Not "now"
                drink_to__gte=current_year,
                drink_to__lte=current_year + 1,
            )
            .filter(storageitem__deleted=False)
            .distinct()
        )

        # Wines past drinking window
        overdue_wines = (
            Wine.objects.filter(
                household=household,
                drink_to__isnull=False,
                drink_to__gt=0,  # Not "now"
                drink_to__lt=current_year,
            )
            .filter(storageitem__deleted=False)
            .distinct()
        )

        context.update(
            {
                "alerts": alerts,
                "upcoming_wines": upcoming_wines,
                "overdue_wines": overdue_wines,
            }
        )
        return context


class ConsumptionStatsView(BaseConsumptionStatsView):
    template_name = "consumption_stats.html"
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"
    select_related_fields = ("wine",)

    def get_type_display(self, beverage):
        return beverage.get_type if beverage.wine_type else "Unknown"

    def get_secondary_stats(self, records):
        from collections import defaultdict

        by_country = defaultdict(int)
        for record in records:
            country = record.wine.country_name if record.wine.country else "Unknown"
            by_country[country] += 1
        return {"by_country": dict(by_country)}


class ReorderRemindersView(BaseReorderRemindersView):
    template_name = "reorder_reminders.html"
    reminder_model = ReorderReminder
    beverage_fk_name = "wine"
    stock_reverse_path = "wine__storageitem"


class ReorderReminderCreateView(BaseReorderReminderCreateView):
    template_name = "reorder_reminder_create.html"
    beverage_model = Wine
    reminder_model = ReorderReminder
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"


class ReorderReminderDeleteView(BaseReorderReminderDeleteView):
    model = ReorderReminder
    template_name = "reorder_reminder_confirm_delete.html"


class LabelScanView(RequireHouseholdMixin, FormView):
    template_name = "label_scan.html"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import LabelScanForm

        return LabelScanForm

    def post(self, request, *args, **kwargs):
        import base64

        # Clear any previous extraction results when starting a new scan
        if "extraction_result" in self.request.session:
            del self.request.session["extraction_result"]

        # Handle camera capture data - check for multiple images
        image_count = request.POST.get("image_count")
        if image_count:
            # Multiple images submitted
            images = []
            for i in range(int(image_count)):
                image_data = request.POST.get(f"image_data_{i}")
                if image_data:
                    # Remove data URL prefix if present
                    if "," in image_data:
                        image_data = image_data.split(",")[1]
                    images.append(image_data)

            if images:
                # Store all images in session
                self.request.session["scanned_label"] = {
                    "filename": "camera_captures.jpg",
                    "size": sum(len(base64.b64decode(img)) for img in images),
                    "data": images,  # List of base64 images
                    "multi_image": True,
                }
                return redirect("wine-add")

        # Handle single camera capture (legacy)
        image_data = request.POST.get("image_data")
        if image_data:
            # Remove data URL prefix if present
            if "," in image_data:
                image_data = image_data.split(",")[1]

            # Decode base64 image
            image_bytes = base64.b64decode(image_data)

            # Store in session for the create view to use
            self.request.session["scanned_label"] = {
                "filename": "camera_capture.jpg",
                "size": len(image_bytes),
                "data": [image_data],  # Wrap in list for consistency
                "multi_image": False,
            }

            return redirect("wine-add")

        # Fallback to form handling for file uploads
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        import base64

        # Clear any previous extraction results when starting a new scan
        if "extraction_result" in self.request.session:
            del self.request.session["extraction_result"]

        images = []

        # Process all uploaded images in order: barcode, front, back
        for field_name in ["barcode_image", "front_image", "back_image"]:
            image = form.cleaned_data.get(field_name)
            if image:
                image_data = image.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                images.append(base64_image)

        if images:
            # Store in session for the create view to use
            self.request.session["scanned_label"] = {
                "filename": "uploaded_images",
                "size": sum(len(base64.b64decode(img)) for img in images),
                "data": images,
                "multi_image": len(images) > 1,
            }

        return redirect("wine-add")


class LabelScanResultView(RequireHouseholdMixin, TemplateView):
    """Process OCR results and pre-fill wine form."""

    template_name = "label_scan_result.html"

    def extract_wine_info(self, text):
        """Extract wine information from OCR text."""
        import re

        info = {}

        # Try to extract vintage year (4 digit number between 1900-2030)
        year_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", text)
        if year_match:
            info["vintage"] = int(year_match.group(1))

        # Try to extract ABV
        abv_match = re.search(r"(\d+\.?\d*)\s*%?\s*(alc|abv|vol)", text, re.IGNORECASE)
        if abv_match:
            info["abv"] = float(abv_match.group(1))

        # Try to extract volume
        vol_match = re.search(r"(\d+\.?\d*)\s*(ml|cl|l)\b", text, re.IGNORECASE)
        if vol_match:
            vol = float(vol_match.group(1))
            unit = vol_match.group(2).lower()
            if unit == "ml":
                vol = vol / 1000
            elif unit == "cl":
                vol = vol / 100
            info["size"] = vol

        return info


@ratelimit(key="user", rate="10/m", method="POST", block=True)
@login_required
def extract_wine_vision_ajax(request):
    """
    AJAX endpoint for wine data extraction from uploaded images.

    This endpoint first attempts to detect barcodes in the uploaded images
    using non-AI tooling (pyzbar). If a barcode is found and matches an
    existing wine in the user's collection, that wine's data is returned.
    Otherwise, AI vision extraction is used to extract wine details from
    the label images.

    Rate limited to 10 requests per minute per user.
    """
    import base64

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
                # Validate file size before processing
                if image_file.size > MAX_IMAGE_SIZE:
                    return JsonResponse(
                        {
                            "error": f"Image {field_name} is too large. "
                            f"Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)}MB."
                        },
                        status=400,
                    )
                # Read and encode to base64
                image_data = image_file.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                images.append(base64_image)
                # Reset file pointer so Django can read it again later
                image_file.seek(0)

        if not images:
            return JsonResponse(
                {"error": "No images uploaded. Please select at least one image."},
                status=400,
            )

        # Step 1: Try barcode scanning first (non-AI, faster)
        barcode_scanner = BarcodeScanner()
        barcode_result = barcode_scanner.scan_and_match(images, request.user)

        if barcode_result.get("matched"):
            if barcode_result.get("multiple_matches"):
                # Multiple wines share this barcode
                return JsonResponse(
                    {
                        "success": True,
                        "multiple_matches": True,
                        "match_type": "barcode",
                        "matched_barcode": barcode_result["barcode"],
                        "wines": barcode_result["wines"],
                        "message": "Multiple wines found with this barcode",
                    }
                )

            # Single match — return wine data as before
            wine_data = barcode_result["wine_data"]
            extracted_fields = list(wine_data.keys())

            return JsonResponse(
                {
                    "success": True,
                    "data": wine_data,
                    "confidence": "high",
                    "extracted_fields": extracted_fields,
                    "errors": [],
                    "match_type": "barcode",
                    "matched_barcode": barcode_result["barcode"],
                    "message": f"Matched wine via barcode: {barcode_result['barcode']}",
                }
            )

        # Step 2: No barcode match, use AI vision extraction
        extractor = WineVisionExtractor()
        result = extractor.extract_from_images(images, user=request.user)

        # Include any barcodes found (even if no match) in the result
        response_data = {
            "success": True,
            "data": result.get("data", {}),
            "confidence": result.get("confidence", "low"),
            "extracted_fields": result.get("extracted_fields", []),
            "errors": result.get("errors", []),
            "match_type": "vision",
        }

        # If barcodes were found but didn't match, include them
        if barcode_result.get("all_barcodes"):
            barcodes = barcode_result["all_barcodes"]
            # Add first barcode to data if not already extracted by vision
            if barcodes and "barcode" not in response_data["data"]:
                response_data["data"]["barcode"] = barcodes[0]
                if "barcode" not in response_data["extracted_fields"]:
                    response_data["extracted_fields"].append("barcode")

        return JsonResponse(response_data)

    except Exception:
        logger.exception("Error in AJAX vision extraction")
        return JsonResponse({"error": "Vision extraction failed"}, status=500)


@ratelimit(key="user", rate="30/m", method="POST", block=True)
@login_required
def scan_barcode_ajax(request):
    """
    AJAX endpoint for server-side barcode scanning from captured images.

    This endpoint uses pyzbar to scan barcodes from base64-encoded images.
    Returns detected barcodes without AI processing.

    Accepts both formats:
    - Single image: { "image": "base64..." }
    - Multiple images: { "images": ["base64...", ...] }

    Rate limited to 30 requests per minute per user.
    """
    import json

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        # Parse JSON body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # Accept both single image and array of images
        images = data.get("images", [])
        single_image = data.get("image")
        if single_image:
            images.append(single_image)

        if not images:
            return JsonResponse({"error": "No image data provided"}, status=400)

        # Remove data URL prefix if present (e.g., "data:image/png;base64,")
        cleaned_images = []
        for img in images:
            if "," in img:
                img = img.split(",", 1)[1]
            cleaned_images.append(img)

        # Scan the images for barcodes
        barcode_scanner = BarcodeScanner()
        barcodes = barcode_scanner.scan_images_for_barcodes(cleaned_images)

        if barcodes:
            return JsonResponse(
                {
                    "success": True,
                    "barcodes": barcodes,
                    "barcode": barcodes[0],  # Primary barcode
                }
            )
        else:
            return JsonResponse(
                {
                    "success": False,
                    "barcodes": [],
                    "message": "No barcode detected in image",
                }
            )

    except Exception:
        logger.exception("Error in barcode scanning")
        return JsonResponse(
            {"error": "An internal error occurred while scanning the barcode."},
            status=500,
        )


@login_required
def set_primary_image(request, pk):
    """Set a WineImage as the primary image for its wine."""
    return set_primary_image_ajax(request, pk, WineImage)


@login_required
def delete_wine_barcode(request, pk):
    """Delete a WineBarcode by pk (POST only)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    household = get_active_household(request.user)
    barcode = get_object_or_404(WineBarcode, pk=pk, household=household)
    barcode.delete()
    return JsonResponse({"success": True})


@login_required
def crop_wine_image(request, pk):
    """Apply manual crop to a WineImage and create a new thumbnail."""
    return crop_image_ajax(request, pk, WineImage)

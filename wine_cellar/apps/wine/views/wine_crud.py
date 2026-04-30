import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django_ratelimit.decorators import ratelimit

from wine_cellar.apps.core.views import (
    BaseBeverageCreateView,
    BaseBeverageDeleteView,
    BaseBeverageUpdateView,
    BaseDetailView,
    BaseImagesView,
    BaseListView,
    BaseMergeConfirmView,
)
from wine_cellar.apps.household.mixins import require_member
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.storage.utils import with_removal_sort_date
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.filters import WineFilter
from wine_cellar.apps.wine.forms import WineEditForm, WineForm
from wine_cellar.apps.wine.models import (
    Collection,
    VisionExtractionLog,
    Wine,
    WineBarcode,
    WineImage,
    Wishlist,
)

logger = logging.getLogger(__name__)

# Form step constants - no longer used for multi-step, kept for compatibility
FINAL_FORM_STEP = 4


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
    page_title = "Add Wine"
    scan_url_name = "wine-scan"
    rescan_url_name = "label-scan"
    duplicate_check_url_name = "wine-check-duplicate"
    extract_vision_url_name = "wine-extract-vision"
    quick_add_description = "Use your camera to scan the wine label and barcode:"
    image_autofill_hint = (
        "Upload images and click 'Auto-fill from Images' to extract wine details "
        "using AI vision."
    )
    image_extract_hint = "Extract wine details from uploaded images"
    scanned_label_alt = "Scanned wine label"
    save_button_label = "Save Wine"
    field_section_definitions = (
        {
            "title": "Details",
            "fields": (
                "name",
                "wine_type",
                "country",
                "subregion",
                "appellation",
                "size",
            ),
        },
        {
            "title": "Characteristics",
            "fields": (
                "attributes",
                "grapes",
                "vintage",
                "abv",
                "category",
            ),
        },
        {
            "title": "Origin & Price",
            "fields": ("vineyard", "source", "price", "barcode"),
        },
        {
            "title": "Personal Notes",
            "fields": ("food_pairings", "rating", "comment"),
        },
    )
    cellar_extra_field_names = ()
    confidence_badge_labels = {
        "high": "✓ High Confidence",
        "medium": "⚠ Please Verify",
        "low": "⚡ Low Confidence",
    }
    wishlist_model = Wishlist
    wishlist_initial_field_map = {
        "name": "name",
        "wine_type": "wine_type",
        "country": "country",
        "subregion": "subregion",
        "vintage": "vintage",
        "comment": "notes",
        "price_url": "external_url",
    }
    vision_field_map = {
        "name": "name",
        "wine_type": "wine_type",
        "vintage": "vintage",
        "country": "country",
        "subregion": "subregion",
        "grapes": "grapes",
        "vineyard": "vineyard",
        "abv": "abv",
        "size": "size",
        "category": "category",
        "barcode": "barcode",
    }
    vision_confidence_field_map = {
        "name": "name",
        "wine_type": "wine_type",
        "type": "wine_type",
        "vintage": "vintage",
        "country": "country",
        "subregion": "subregion",
        "region": "subregion",
        "grapes": "grapes",
        "vineyard": "vineyard",
        "abv": "abv",
        "size": "size",
        "volume": "size",
        "category": "category",
        "sweetness": "category",
        "barcode": "barcode",
        "appellation": "appellation",
    }
    vision_create_fields = ("grapes", "vineyard")
    extraction_log_model = VisionExtractionLog
    extraction_log_fk_name = "wine"

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
        size = None
        if size_code:
            size, _ = Size.objects.get_or_create(name=size_code, user=None)
        category = cleaned_data["category"] or None
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

        wine, created = Wine.objects.get_or_create(
            name=name,
            wine_type=wine_type,
            abv=abv,
            size=size,
            vintage=vintage,
            country=country,
            user=user,
            household=household,
            deleted=False,
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
    template_name = "core/beverage_edit.html"
    form_class = WineEditForm
    success_url = reverse_lazy("wine-list")
    beverage_model = Wine
    beverage_fk_name = "wine"
    image_related_name = "wineimage_set"
    detail_url_name = "wine-detail"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["barcode_delete_url_pattern"] = reverse("wine-barcode-delete", args=[0])
        return context

    @staticmethod
    @transaction.atomic
    def process_form_data(wine, user, cleaned_data):
        from wine_cellar.apps.wine.models import Size

        abv = cleaned_data["abv"]
        size_code = cleaned_data["size"]
        size = None
        if size_code:
            size, _ = Size.objects.get_or_create(name=size_code, user=None)
        category = cleaned_data["category"] or None
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
        "collections",
    )
    storage_item_reverse = "storageitem"
    extraction_log_model = VisionExtractionLog
    extraction_log_fk_name = "wine"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["all_collections"] = Collection.objects.filter(
            household=household
        ).order_by("name")

        removed_bottles = with_removal_sort_date(
            self.object.storageitem_set.filter(deleted=True)
            .select_related("storage")
            .prefetch_related("notes")
        ).order_by("-removal_sort_date", "-created", "-pk")
        consumed_bottles = removed_bottles.exclude(
            removal_reason=StorageItem.RemovalReason.GIVEN
        )
        gifted_bottles = removed_bottles.filter(
            removal_reason=StorageItem.RemovalReason.GIVEN
        )
        broken_lost_bottles = consumed_bottles.filter(
            removal_reason=StorageItem.RemovalReason.REMOVED
        )
        context["consumed_bottle_count"] = consumed_bottles.count()
        context["gifted_bottle_count"] = gifted_bottles.count()
        context["broken_lost_bottle_count"] = broken_lost_bottles.count()
        context["actual_consumed_bottle_count"] = (
            context["consumed_bottle_count"] - context["broken_lost_bottle_count"]
        )
        context["show_consumed_bottles"] = self.request.GET.get(
            "show_consumed"
        ) == "1" and (
            context["consumed_bottle_count"] > 0 or context["gifted_bottle_count"] > 0
        )
        context["consumed_bottles"] = (
            consumed_bottles
            if context["show_consumed_bottles"]
            else self.object.storageitem_set.none()
        )
        context["gifted_bottles"] = (
            gifted_bottles
            if context["show_consumed_bottles"]
            else self.object.storageitem_set.none()
        )
        return context


class WineImagesView(BaseImagesView):
    template_name = "core/beverage_images.html"
    model = Wine
    context_object_name = "wine"
    images_prefetch_name = "wineimage_set"
    image_api_prefix = "/wine/image"


class WineListView(BaseListView, FilterView):
    model = Wine
    template_name = "core/beverage_list.html"
    context_object_name = "wines"
    filterset_class = WineFilter
    default_filter_data = {"stock": "1", "order": "created"}
    storage_item_reverse = "storageitem"
    select_related_fields = ("size", "appellation")
    prefetch_related_fields = ("grapes", "attributes", "food_pairings", "wineimage_set")
    card_template = "wine_card.html"
    filter_field_template = "wine_filter_field.html"
    beverage_icon = "wine-glass"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["export_csv_url"] = reverse("wine-export-csv")
        context["export_json_url"] = reverse("wine-export-json")
        return context


class WineDeleteView(BaseBeverageDeleteView):
    model = Wine
    template_name = "core/confirm_delete.html"
    success_url = reverse_lazy("wine-list")
    context_object_name = "beverage"


class WineMergeConfirmView(BaseMergeConfirmView):
    template_name = "core/merge_confirm.html"
    beverage_model = Wine
    storage_item_model = StorageItem
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"
    image_model = WineImage
    m2m_fields = (
        "grapes",
        "attributes",
        "food_pairings",
        "vineyard",
        "source",
        "collections",
    )
    reminder_model = None  # Lazy-loaded

    @property
    def related_models(self):
        from wine_cellar.apps.wine.models import (
            DrinkingWindowAlert,
            DrinkRecord,
            PriceHistory,
            VisionExtractionLog,
        )

        return (
            (DrinkRecord, "wine"),
            (DrinkingWindowAlert, "wine"),
            (PriceHistory, "wine"),
            (VisionExtractionLog, "wine"),
        )

    def post(self, request, *args, **kwargs):
        from wine_cellar.apps.wine.models import ReorderReminder

        self.reminder_model = ReorderReminder
        return super().post(request, *args, **kwargs)


@login_required
@require_member
@require_POST
def add_wine_to_collection(request, pk):
    household = get_active_household(request.user)
    wine = get_object_or_404(Wine, pk=pk, household=household)
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
        collection.wines.add(wine)

    return redirect("wine-detail", pk=wine.pk)


@login_required
@require_member
@require_POST
def remove_wine_from_collection(request, pk, collection_pk):
    household = get_active_household(request.user)
    wine = get_object_or_404(Wine, pk=pk, household=household)
    collection = get_object_or_404(Collection, pk=collection_pk, household=household)
    collection.wines.remove(wine)
    return redirect("wine-detail", pk=wine.pk)

import logging

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
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
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.filters import WineFilter
from wine_cellar.apps.wine.forms import WineBaseForm, WineEditForm, WineForm
from wine_cellar.apps.wine.models import Wine, WineBarcode, WineImage

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

    def _link_extraction_log(self, beverage, cleaned_data, extraction_result):
        """Link the most recent VisionExtractionLog to the created wine."""
        from wine_cellar.apps.wine.models import VisionExtractionLog

        try:
            log = (
                VisionExtractionLog.objects.filter(
                    user=self.request.user, wine__isnull=True
                )
                .order_by("-created")
                .first()
            )
            if log:
                extracted_data = extraction_result.get("extracted_data", {})
                corrections = self._detect_corrections(cleaned_data, extracted_data)
                log.wine = beverage
                log.was_successful = True
                if corrections:
                    log.user_corrections = corrections
                log.save(update_fields=["wine", "was_successful", "user_corrections"])
        except Exception:
            logger.exception("Failed to link extraction log to wine %s", beverage.pk)

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

        for form_field, image_type in WineBaseForm.image_fields_map.items():
            image = cleaned_data.get(form_field)
            if image:
                WineImage.objects.get_or_create(
                    image=image, wine=wine, user=user, image_type=image_type
                )

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

        for form_field, image_type in WineBaseForm.image_fields_map.items():
            image = cleaned_data.get(form_field)
            existing_image = WineImage.objects.filter(
                wine=wine, user=user, image_type=image_type
            ).first()

            if image is False:
                if existing_image:
                    existing_image.image.delete()
                    existing_image.delete()
            elif image and not hasattr(image, "instance"):
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from wine_cellar.apps.wine.models import VisionExtractionLog

        extraction_log = (
            VisionExtractionLog.objects.filter(wine=self.object, was_successful=True)
            .order_by("-created")
            .first()
        )
        if extraction_log:
            context["extraction_log"] = extraction_log
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
    m2m_fields = ("grapes", "attributes", "food_pairings", "vineyard", "source")
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

import base64
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import connections, transaction
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.db.models.functions import Coalesce
from django.forms import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.formats import number_format
from django.views.generic import DeleteView, DetailView, FormView, TemplateView
from django_filters.views import FilterView
from django_ratelimit.decorators import ratelimit

from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.filters import WineFilter
from wine_cellar.apps.wine.forms import WineEditForm, WineForm, image_fields_map
from wine_cellar.apps.wine.models import Wine, WineImage
from wine_cellar.apps.wine.services import BarcodeScanner, WineVisionExtractor

# Form step constants - no longer used for multi-step, kept for compatibility
FINAL_FORM_STEP = 4

# Maximum allowed image upload size (10MB) to prevent memory exhaustion
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB in bytes


def base64_to_uploaded_file(base64_data: str, filename: str) -> InMemoryUploadedFile:
    """Convert base64 string to Django InMemoryUploadedFile.

    Args:
        base64_data: Base64-encoded image data (without data URL prefix)
        filename: Desired filename for the uploaded file

    Returns:
        InMemoryUploadedFile suitable for use with Django image fields
    """
    # Decode base64 to bytes
    image_bytes = base64.b64decode(base64_data)
    image_io = BytesIO(image_bytes)

    # Create InMemoryUploadedFile
    return InMemoryUploadedFile(
        file=image_io,
        field_name=None,
        name=filename,
        content_type="image/jpeg",
        size=len(image_bytes),
        charset=None,
    )


class HomePageView(TemplateView):
    template_name = "homepage.html"

    def get_context_data(self, **kwargs):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkRecord, ReorderReminder, Wishlist

        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get total wines count separately to avoid JOIN issues
        wines = Wine.objects.filter(user=user).count()

        # Get other wine stats
        wine_stats = Wine.objects.filter(user=user).aggregate(
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
                filter=Q(deleted=False, wine__user=self.request.user),
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
        bottles_in_stock = StorageItem.objects.filter(user=user, deleted=False).count()

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

        # Low stock reminders
        reminders = ReorderReminder.objects.filter(
            user=self.request.user, is_active=True
        ).annotate(
            current_stock=Count(
                "wine__storageitem", filter=Q(wine__storageitem__deleted=False)
            )
        )
        low_stock_count = sum(1 for r in reminders if r.current_stock <= r.min_stock)

        # Recent drinks
        recent_drinks = (
            DrinkRecord.objects.filter(user=self.request.user)
            .select_related("wine")
            .order_by("-date_consumed")[:3]
        )

        # Wishlist
        wishlist_items = Wishlist.objects.filter(
            user=self.request.user, purchased=False
        ).order_by("-priority")[:3]

        # Stats - consolidate into single query per model
        drink_stats = DrinkRecord.objects.filter(user=user).aggregate(
            total_consumed=Count("id"),
            avg_rating=Avg("rating", filter=Q(rating__isnull=False)),
        )
        total_consumed = drink_stats["total_consumed"]
        avg_rating = (
            round(drink_stats["avg_rating"], 1) if drink_stats["avg_rating"] else None
        )

        total_bottles = StorageItem.objects.filter(user=user, deleted=False).count()

        # Pending hardware position reviews (gracefully handle if hardware not set up)
        pending_reviews_count = 0
        try:
            from wine_cellar.apps.hardware.models import (
                PositionChangeReview,
                ReviewStatus,
            )

            pending_reviews_count = PositionChangeReview.objects.filter(
                user=self.request.user,
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
                "total_bottles": total_bottles,
                "avg_rating": avg_rating,
                "pending_reviews_count": pending_reviews_count,
            }
        )

        return context


@method_decorator(
    ratelimit(key="user", rate="20/m", method="POST", block=True), name="post"
)
class WineCreateView(FormView):
    """View for creating new wines. Rate limited to 20 creations/minute per user."""

    template_name = "wine_create.html"
    form_class = WineForm
    success_url = reverse_lazy("wine-list")

    def get_initial(self):
        """Pre-fill form with data from scanned wine label if available."""
        initial = super().get_initial()

        # Check for scanned label in session
        scanned_label = self.request.session.get("scanned_label")

        # Check if we've already processed this scan
        extraction_result = self.request.session.get("extraction_result")

        # Determine if we should (re-)extract:
        # - Extract if we have a scanned label and no extraction result
        # - Re-extract if previous extraction had errors (don't get stuck on errors)
        should_extract = scanned_label and (
            not extraction_result
            or extraction_result.get("errors")  # Retry if there were errors
        )

        if should_extract:
            # Process extraction (or retry after error)
            try:
                from wine_cellar.apps.wine.services import WineVisionExtractor

                # Extract wine data using vision service
                extractor = WineVisionExtractor()

                # Handle both single and multiple images
                image_data = scanned_label.get("data")
                user = self.request.user
                if isinstance(image_data, list):
                    # Multiple images
                    result = extractor.extract_from_images(image_data, user=user)
                else:
                    # Legacy single image (backwards compatibility)
                    result = extractor.extract_from_image(image_data, user=user)

                # Store extraction metadata for template display
                self.request.session["extraction_result"] = {
                    "confidence": result.get("confidence", "low"),
                    "extracted_fields": result.get("extracted_fields", []),
                    "errors": result.get("errors", []),
                    "scanned_image": (
                        image_data[0] if isinstance(image_data, list) else image_data
                    ),  # Show first image
                    "image_count": (
                        len(image_data) if isinstance(image_data, list) else 1
                    ),
                    "extracted_data": result.get("data", {}),  # Store for reuse
                }
                # Update local variable for use below
                extraction_result = self.request.session["extraction_result"]

            except Exception as e:
                # Log error but don't break the page
                import logging

                logger = logging.getLogger(__name__)
                logger.exception("Error extracting wine data from scanned label")
                self.request.session["extraction_result"] = {
                    "confidence": "low",
                    "extracted_fields": [],
                    "errors": [f"Extraction failed: {str(e)}"],
                    "scanned_image": scanned_label.get("data"),
                    "extracted_data": {},
                }
                extraction_result = self.request.session["extraction_result"]

        # If we have extraction results, use them
        if extraction_result:
            result_data = extraction_result.get("extracted_data", {})
            if result_data:
                # Map extracted data to form fields
                initial.update(result_data)

                # Handle special fields that need processing
                # Grapes: convert list to initial format expected by form
                if "grapes" in result_data and isinstance(result_data["grapes"], list):
                    # Store as list for form to handle
                    initial["grapes"] = result_data["grapes"]

                # Vineyard: convert to list if string
                if "vineyard" in result_data:
                    if isinstance(result_data["vineyard"], str):
                        initial["vineyard"] = [result_data["vineyard"]]
                    elif isinstance(result_data["vineyard"], list):
                        initial["vineyard"] = result_data["vineyard"]

                # Size field mapping (already handled by service)
                # wine_type field (already handled by service)
                # category field (already handled by service)

        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "user" not in kwargs:
            kwargs["user"] = self.request.user
        if "code" in self.kwargs:
            kwargs["initial"].update({"barcode": self.kwargs["code"]})
        elif self.request.session.get("pending_barcode"):
            # Use barcode from previous scan if available
            kwargs["initial"].update(
                {"barcode": self.request.session.pop("pending_barcode")}
            )
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Provide free cells for storage dropdown (for stock_add.js)
        user_storages = Storage.objects.filter(user=self.request.user)
        free_cells_by_storage = {}
        for storage in user_storages:
            if storage.rows == 0:
                free_cells_by_storage[storage.pk] = {}
                continue
            used_cells = set(
                storage.items.filter(deleted=False).values_list("row", "column")
            )
            all_rows = range(1, storage.rows + 1)
            all_columns = range(1, storage.columns + 1)
            free_cells_by_storage[storage.pk] = {}
            for row in all_rows:
                free = []
                for column in all_columns:
                    if (row, column) not in used_cells:
                        free.append(column)
                free_cells_by_storage[storage.pk][row] = free
        context["free_cells_by_storage"] = free_cells_by_storage

        # Add extraction result to context if available
        extraction_result = self.request.session.get("extraction_result")
        if extraction_result:
            context["extraction_result"] = extraction_result
            context["scanned_image"] = extraction_result.get("scanned_image")
            context["extracted_fields"] = extraction_result.get("extracted_fields", [])
            context["confidence"] = extraction_result.get("confidence", "low")

        # Pass scanned front/back images for automatic attachment
        scanned_label = self.request.session.get("scanned_label")
        if scanned_label:
            image_data = scanned_label.get("data")
            if isinstance(image_data, list):
                # Index 0 = barcode, index 1 = back label, index 2 = front label
                if len(image_data) > 1:
                    context["scanned_back_image"] = image_data[1]
                if len(image_data) > 2:
                    context["scanned_front_image"] = image_data[2]

        return context

    def post(self, request, *args, **kwargs):
        """
        Handle wine creation form submission and optional vision-based auto-fill.

        This method has two behaviors depending on the submitted POST data:

        * Vision extraction mode: If the ``extract_vision`` key is present in
          ``request.POST`` (e.g. when the user clicks an "Auto-fill from Images"
          button), the form is validated and the configured image fields
          (``image_front_label``, ``image_back_label``, ``image_front``,
          ``image_back``) are read, base64-encoded, and sent to the external
          vision API configured via ``settings.WINE_VISION_API_URL`` and
          ``settings.WINE_VISION_API_KEY``. The response is stored in the
          session under the ``"extraction_result"`` key, including the
          ``scanned_image``, any ``extracted_fields``, and a ``confidence``
          level. The user is then redirected back to this view so that the
          extraction result can be displayed and used to pre-fill form fields.
          If no images were uploaded, a warning message is added and the form
          is treated as invalid.

        * Normal submission mode: If ``extract_vision`` is not present in
          ``request.POST``, this method delegates to ``FormView.post`` for the
          standard form submission and validation flow, ultimately creating the
          wine record on success.
        """
        import base64

        # Check if user clicked "Auto-fill from Images" button
        if "extract_vision" in request.POST:
            # Don't validate the form - just collect uploaded images
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
                    # Read and encode to base64
                    image_data = image_file.read()
                    base64_image = base64.b64encode(image_data).decode("utf-8")
                    images.append(base64_image)
                    # Reset file pointer for later use
                    image_file.seek(0)

            if images:
                # Store images in session for vision extraction
                self.request.session["scanned_label"] = {
                    "filename": "uploaded_images.jpg",
                    "size": sum(len(base64.b64decode(img)) for img in images),
                    "data": images,
                    "multi_image": True,
                }
                # Clear any previous extraction results to trigger new extraction
                if "extraction_result" in self.request.session:
                    del self.request.session["extraction_result"]

                # Reload the page to trigger vision extraction in get_initial()
                return redirect("wine-add")
            else:
                # No images uploaded, show error
                from django.contrib import messages

                messages.warning(
                    request, "Please upload at least one image before using auto-fill."
                )
                # Return to form without validation
                return self.render_to_response(self.get_context_data())

        # Normal form submission
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        # Use scanned images if available and user hasn't uploaded/cleared them
        scanned_label = self.request.session.get("scanned_label")
        if scanned_label:
            image_data = scanned_label.get("data")
            if isinstance(image_data, list):
                # Check hidden inputs for user intent
                use_scanned_front = self.request.POST.get("use_scanned_front", "0")
                use_scanned_back = self.request.POST.get("use_scanned_back", "0")

                # Back label: use scanned if available and user wants it (index 1)
                if (
                    use_scanned_back == "1"
                    and len(image_data) > 1
                    and not form.cleaned_data.get("image_back_label")
                ):
                    form.cleaned_data["image_back_label"] = base64_to_uploaded_file(
                        image_data[1], "scanned_back_label.jpg"
                    )

                # Front label: use scanned if available and user wants it (index 2)
                if (
                    use_scanned_front == "1"
                    and len(image_data) > 2
                    and not form.cleaned_data.get("image_front_label")
                ):
                    form.cleaned_data["image_front_label"] = base64_to_uploaded_file(
                        image_data[2], "scanned_front_label.jpg"
                    )

        wine, created = self.process_form_data(self.request.user, form.cleaned_data)

        # Clear scanned label data from session after successful save
        if "scanned_label" in self.request.session:
            del self.request.session["scanned_label"]
        if "extraction_result" in self.request.session:
            del self.request.session["extraction_result"]

        if not created:
            messages.info(
                self.request, "Wine already exists. Added bottle to your cellar."
            )

        return super().form_valid(form)

    @staticmethod
    @transaction.atomic
    def process_form_data(user, cleaned_data):
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
        food_pairings = cleaned_data["food_pairings"]
        source = cleaned_data["source"]
        price = cleaned_data["price"]
        rrp = cleaned_data["rrp"]
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
            defaults={
                "category": category,
                "subregion": subregion,
                "barcode": barcode,
                "drink_from": drink_from,
                "drink_to": drink_to,
                "comment": comment,
                "rating": rating,
                "price": price,
                "rrp": rrp,
            },
        )

        wine.vineyard.set(vineyards)
        wine.grapes.set(grapes)
        wine.food_pairings.set(food_pairings)
        wine.source.set(source)
        wine.attributes.set(attributes)

        for form_field, image_type in image_fields_map.items():
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
                price=bottle_price,
                is_gift=is_gift,
                gift_from=gift_from,
                occasion=occasion,
            )

        return wine, created


class WineUpdateView(FormView):
    template_name = "wine_edit.html"
    form_class = WineEditForm
    success_url = reverse_lazy("wine-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "user" not in kwargs:
            kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        wine = get_object_or_404(Wine, pk=self.kwargs["pk"], user=self.request.user)
        initial.update(model_to_dict(wine))
        return initial

    def form_valid(self, form):
        wine = get_object_or_404(Wine, pk=self.kwargs["pk"], user=self.request.user)
        self.process_form_data(wine, self.request.user, form.cleaned_data)
        self.success_url = reverse_lazy("wine-detail", kwargs={"pk": wine.pk})
        return super().form_valid(form)

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
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        subregion = cleaned_data["subregion"]
        food_pairings = cleaned_data["food_pairings"]
        source = cleaned_data["source"]
        price = cleaned_data["price"]
        rrp = cleaned_data["rrp"]
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
        wine.name = name
        wine.barcode = barcode
        wine.rating = rating
        wine.vintage = vintage
        wine.drink_from = drink_from
        wine.drink_to = drink_to
        wine.wine_type = wine_type
        wine.price = price
        wine.rrp = rrp
        wine.save()

        wine.vineyard.set(vineyards)
        wine.grapes.set(grapes)
        wine.food_pairings.set(food_pairings)
        wine.attributes.set(attributes)
        wine.source.set(source)

        for form_field, image_type in image_fields_map.items():
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


class WineDetailView(DetailView):
    template_name = "wine_detail.html"
    model = Wine

    def get_queryset(self):
        qs = super().get_queryset()
        return (
            qs.prefetch_related(
                "grapes",
                "attributes",
                "food_pairings",
                "wineimage_set",
                "vineyard",
                "source",
            )
            .annotate(
                stock_count=Count(
                    "storageitem", filter=Q(storageitem__deleted=False), distinct=True
                )
            )
            .filter(user=self.request.user)
        )


class WineListView(FilterView):
    model = Wine
    template_name = "wine_list.html"
    context_object_name = "wines"
    filterset_class = WineFilter
    paginate_by = 10
    per_page_options = [10, 25, 50, 100]

    def get_paginate_by(self, queryset):
        """Allow user to select number of items per page via URL parameter."""
        per_page = self.request.GET.get("per_page")
        if per_page:
            try:
                per_page = int(per_page)
                if per_page in self.per_page_options:
                    return per_page
            except (ValueError, TypeError):
                pass
        return self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["per_page_options"] = self.per_page_options
        context["current_per_page"] = self.get_paginate_by(self.object_list)
        return context

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .prefetch_related("grapes", "attributes", "food_pairings", "wineimage_set")
            .order_by("-created")
        )
        qs = qs.annotate(
            effective_price=Coalesce(
                Avg("storageitem__price"),
                "price",
            ),
            stock_count=Count(
                "storageitem", filter=Q(storageitem__deleted=False), distinct=True
            ),
        )
        return qs.filter(user=self.request.user).distinct()


class WineScanView(TemplateView):
    template_name = "scan_wine.html"


class WineScannedView(TemplateView):
    template_name = "scanned_wine.html"

    def dispatch(self, request, *args, **kwargs):
        code = self.kwargs["code"]
        # Use robust barcode matching from service
        scanner = BarcodeScanner()
        wine = scanner.get_wine_object_by_barcode(code, self.request.user)

        if wine:
            return redirect(reverse("wine-detail", kwargs={"pk": wine.pk}))

        # Store barcode in session for use if user continues to label scan
        request.session["pending_barcode"] = code

        return super().dispatch(request, *args, **kwargs)


class WineDeleteView(DeleteView):
    model = Wine
    template_name = "wine_confirm_delete.html"
    success_url = reverse_lazy("wine-list")

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


class WineMapView(TemplateView):
    template_name = "wine_map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only show wines that are currently in stock (have non-deleted storage items)
        wines = Wine.objects.filter(
            user=self.request.user,
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
    - Celery worker status (if configured)
    """
    import shutil

    health = {
        "status": "ok",
        "database": "ok",
        "disk": "ok",
        "celery": "unknown",
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

    # Check Celery worker status (optional)
    try:
        from django_celery_beat.models import PeriodicTask

        # Just check if celery beat tables are accessible
        PeriodicTask.objects.exists()
        health["celery"] = "configured"
    except Exception:
        health["celery"] = "not_configured"

    return JsonResponse(health, status=status_code)


class DrinkRecordCreateView(FormView):
    template_name = "drink_record_create.html"
    form_class = None  # Set dynamically

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import DrinkRecordForm

        return DrinkRecordForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        wine = get_object_or_404(Wine, pk=self.kwargs["pk"], user=self.request.user)
        kwargs["wine"] = wine
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wine"] = get_object_or_404(
            Wine, pk=self.kwargs["pk"], user=self.request.user
        )
        return context

    def form_valid(self, form):
        from wine_cellar.apps.wine.models import DrinkRecord

        wine = get_object_or_404(Wine, pk=self.kwargs["pk"], user=self.request.user)
        storage_item = form.cleaned_data.get("storage_item")

        # Create drink record
        DrinkRecord.objects.create(
            wine=wine,
            user=self.request.user,
            date_consumed=form.cleaned_data["date_consumed"],
            tasting_notes=form.cleaned_data.get("tasting_notes"),
            rating=form.cleaned_data.get("rating"),
            shared_with=form.cleaned_data.get("shared_with"),
            occasion=form.cleaned_data.get("occasion"),
            storage_item=storage_item,
        )

        # Mark bottle as consumed if selected
        if storage_item:
            storage_item.deleted = True
            storage_item.save(update_fields=["deleted"])

        self.success_url = reverse_lazy("wine-detail", kwargs={"pk": wine.pk})
        return super().form_valid(form)


class DrinkRecordListView(TemplateView):
    template_name = "drink_record_list.html"

    def get_context_data(self, **kwargs):
        from wine_cellar.apps.wine.models import DrinkRecord

        context = super().get_context_data(**kwargs)
        context["drink_records"] = DrinkRecord.objects.filter(
            user=self.request.user
        ).select_related("wine")
        return context


class DrinkRecordEditView(FormView):
    template_name = "drink_record_edit.html"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import DrinkRecordForm

        return DrinkRecordForm

    def get_object(self):
        from wine_cellar.apps.wine.models import DrinkRecord

        return get_object_or_404(
            DrinkRecord, pk=self.kwargs["pk"], user=self.request.user
        )

    def get_initial(self):
        record = self.get_object()
        return {
            "date_consumed": record.date_consumed,
            "tasting_notes": record.tasting_notes,
            "rating": record.rating,
            "shared_with": record.shared_with,
            "occasion": record.occasion,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.get_object()
        context["record"] = record
        context["wine"] = record.wine
        return context

    def form_valid(self, form):
        record = self.get_object()
        record.date_consumed = form.cleaned_data["date_consumed"]
        record.tasting_notes = form.cleaned_data.get("tasting_notes")
        record.rating = form.cleaned_data.get("rating")
        record.shared_with = form.cleaned_data.get("shared_with")
        record.occasion = form.cleaned_data.get("occasion")
        record.save()
        self.success_url = reverse_lazy("drink-history")
        return super().form_valid(form)


class DrinkRecordDeleteView(DeleteView):
    template_name = "drink_record_confirm_delete.html"
    success_url = reverse_lazy("drink-history")

    def get_queryset(self):
        from wine_cellar.apps.wine.models import DrinkRecord

        return DrinkRecord.objects.filter(user=self.request.user)


class WishlistListView(TemplateView):
    template_name = "wishlist_list.html"

    def get_context_data(self, **kwargs):
        from wine_cellar.apps.wine.models import Wishlist

        context = super().get_context_data(**kwargs)
        context["wishlist_items"] = Wishlist.objects.filter(
            user=self.request.user, purchased=False
        )
        return context


class WishlistCreateView(FormView):
    template_name = "wishlist_create.html"
    success_url = reverse_lazy("wishlist-list")

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import WishlistForm

        return WishlistForm

    def form_valid(self, form):
        from wine_cellar.apps.wine.models import Wishlist

        Wishlist.objects.create(
            user=self.request.user,
            name=form.cleaned_data["name"],
            wine_type=form.cleaned_data.get("wine_type") or None,
            country=form.cleaned_data.get("country") or None,
            subregion=form.cleaned_data.get("subregion"),
            vintage=form.cleaned_data.get("vintage"),
            price_limit=form.cleaned_data.get("price_limit"),
            notes=form.cleaned_data.get("notes"),
            priority=form.cleaned_data.get("priority", 1),
        )
        return super().form_valid(form)


class WishlistDeleteView(DeleteView):
    template_name = "wishlist_confirm_delete.html"
    success_url = reverse_lazy("wishlist-list")

    def get_queryset(self):
        from wine_cellar.apps.wine.models import Wishlist

        return Wishlist.objects.filter(user=self.request.user)


class WishlistPurchasedView(TemplateView):
    """Mark a wishlist item as purchased."""

    def get(self, request, *args, **kwargs):
        from wine_cellar.apps.wine.models import Wishlist

        item = get_object_or_404(Wishlist, pk=kwargs["pk"], user=request.user)
        item.purchased = True
        item.save()
        return redirect("wishlist-list")


class CellarValueView(TemplateView):
    template_name = "cellar_value.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        user_settings = get_user_settings(user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )

        # Total value from storage items
        storage_items = StorageItem.objects.filter(user=user, deleted=False)
        total_value = storage_items.aggregate(
            total=Coalesce(Sum("price"), Decimal("0.00"))
        )["total"]
        total_bottles = storage_items.count()

        # Value by country and type - single iteration
        wines_by_country = {}
        wines_by_type = {}
        for item in storage_items.select_related("wine"):
            country = item.wine.country_name if item.wine.country else "Unknown"
            wine_type = item.wine.get_type if item.wine.wine_type else "Unknown"

            # Country stats
            if country not in wines_by_country:
                wines_by_country[country] = {"count": 0, "value": Decimal("0")}
            wines_by_country[country]["count"] += 1
            if item.price:
                wines_by_country[country]["value"] += item.price

            # Type stats (same loop)
            if wine_type not in wines_by_type:
                wines_by_type[wine_type] = {"count": 0, "value": Decimal("0")}
            wines_by_type[wine_type]["count"] += 1
            if item.price:
                wines_by_type[wine_type]["value"] += item.price

        # Format values as integers (no pence)
        for data in wines_by_country.values():
            data["value"] = int(data["value"])
        for data in wines_by_type.values():
            data["value"] = int(data["value"])

        context.update(
            {
                "total_value": int(total_value),
                "total_bottles": total_bottles,
                "currency": currency,
                "by_country": wines_by_country,
                "by_type": wines_by_type,
            }
        )
        return context


class BottleNoteCreateView(FormView):
    template_name = "bottle_note_create.html"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import BottleNoteForm

        return BottleNoteForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["storage_item"] = get_object_or_404(
            StorageItem, pk=self.kwargs["pk"], user=self.request.user
        )
        return context

    def form_valid(self, form):
        from wine_cellar.apps.wine.models import BottleNote

        storage_item = get_object_or_404(
            StorageItem, pk=self.kwargs["pk"], user=self.request.user
        )
        BottleNote.objects.create(
            storage_item=storage_item,
            user=self.request.user,
            note_date=form.cleaned_data["note_date"],
            note=form.cleaned_data["note"],
        )
        self.success_url = reverse_lazy(
            "wine-detail", kwargs={"pk": storage_item.wine.pk}
        )
        return super().form_valid(form)


class DrinkingWindowAlertsView(TemplateView):
    template_name = "drinking_window_alerts.html"

    def get_context_data(self, **kwargs):
        from datetime import date

        from wine_cellar.apps.wine.models import DrinkingWindowAlert

        context = super().get_context_data(**kwargs)

        # Get existing alerts
        alerts = DrinkingWindowAlert.objects.filter(
            user=self.request.user, is_read=False
        ).select_related("wine")

        current_year = date.today().year

        # Find wines approaching end of drinking window (this year or next)
        upcoming_wines = (
            Wine.objects.filter(
                user=self.request.user,
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
                user=self.request.user,
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


class ConsumptionStatsView(TemplateView):
    template_name = "consumption_stats.html"

    def get_context_data(self, **kwargs):
        from collections import defaultdict

        from django.db.models import Count
        from django.db.models.functions import TruncMonth

        from wine_cellar.apps.wine.models import DrinkRecord

        context = super().get_context_data(**kwargs)
        user = self.request.user

        records = DrinkRecord.objects.filter(user=user).select_related("wine")

        # Drinks by month (last 12 months)
        by_month = (
            records.annotate(month=TruncMonth("date_consumed"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        # Drinks by wine type
        by_type = defaultdict(int)
        for record in records:
            wine_type = record.wine.get_type if record.wine.wine_type else "Unknown"
            by_type[wine_type] += 1

        # Drinks by country
        by_country = defaultdict(int)
        for record in records:
            country = record.wine.country_name if record.wine.country else "Unknown"
            by_country[country] += 1

        # Average rating
        avg_rating_result = records.filter(rating__isnull=False).aggregate(
            avg=Avg("rating")
        )
        avg_rating = (
            round(avg_rating_result["avg"], 1) if avg_rating_result["avg"] else None
        )

        # Top rated wines
        top_rated = records.filter(rating__isnull=False).order_by("-rating")[:5]

        context.update(
            {
                "total_consumed": records.count(),
                "by_month": list(by_month),
                "by_type": dict(by_type),
                "by_country": dict(by_country),
                "avg_rating": avg_rating,
                "top_rated": top_rated,
            }
        )
        return context


class ReorderRemindersView(TemplateView):
    template_name = "reorder_reminders.html"

    def get_context_data(self, **kwargs):
        from wine_cellar.apps.wine.models import ReorderReminder

        context = super().get_context_data(**kwargs)
        user = self.request.user

        reminders = (
            ReorderReminder.objects.filter(user=user, is_active=True)
            .select_related("wine")
            .annotate(
                current_stock=Count(
                    "wine__storageitem", filter=Q(wine__storageitem__deleted=False)
                )
            )
        )

        # Find wines that need reordering
        needs_reorder = []
        for reminder in reminders:
            if reminder.current_stock <= reminder.min_stock:
                needs_reorder.append(
                    {
                        "wine": reminder.wine,
                        "current_stock": reminder.current_stock,
                        "min_stock": reminder.min_stock,
                        "reminder": reminder,
                    }
                )

        context.update(
            {
                "reminders": reminders,
                "needs_reorder": needs_reorder,
            }
        )
        return context


class ReorderReminderCreateView(FormView):
    template_name = "reorder_reminder_create.html"

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import ReorderReminderForm

        return ReorderReminderForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wine"] = get_object_or_404(
            Wine, pk=self.kwargs["pk"], user=self.request.user
        )
        return context

    def form_valid(self, form):
        from wine_cellar.apps.wine.models import ReorderReminder

        wine = get_object_or_404(Wine, pk=self.kwargs["pk"], user=self.request.user)
        ReorderReminder.objects.update_or_create(
            wine=wine,
            user=self.request.user,
            defaults={
                "min_stock": form.cleaned_data["min_stock"],
                "is_active": True,
            },
        )
        self.success_url = reverse_lazy("wine-detail", kwargs={"pk": wine.pk})
        return super().form_valid(form)


class ReorderReminderDeleteView(DeleteView):
    template_name = "reorder_reminder_confirm_delete.html"
    success_url = reverse_lazy("reorder-reminders")

    def get_queryset(self):
        from wine_cellar.apps.wine.models import ReorderReminder

        return ReorderReminder.objects.filter(user=self.request.user)


class LabelScanView(FormView):
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


class LabelScanResultView(TemplateView):
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
            # Found a matching wine via barcode
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

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Error in AJAX vision extraction")
        return JsonResponse({"error": str(e)}, status=500)


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

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Error in barcode scanning")
        return JsonResponse({"error": str(e)}, status=500)

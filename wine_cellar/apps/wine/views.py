from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.db import connections, transaction
from django.db.models import Avg, Q, Sum
from django.db.models.functions import Coalesce
from django.forms import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.formats import number_format
from django.views.generic import DeleteView, DetailView, FormView, TemplateView
from django_filters.views import FilterView

from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.filters import WineFilter
from wine_cellar.apps.wine.forms import WineEditForm, WineForm, image_fields_map
from wine_cellar.apps.wine.models import Wine, WineImage

# Form step constants - no longer used for multi-step, kept for compatibility
FINAL_FORM_STEP = 4


class HomePageView(TemplateView):
    template_name = "homepage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wines = Wine.objects.filter(user=self.request.user).count()
        wines_in_stock = (
            Wine.objects.filter(storageitem__isnull=False, storageitem__deleted=False)
            .filter(user=self.request.user)
            .distinct()
            .count()
        )
        countries = (
            Wine.objects.filter(user=self.request.user)
            .values_list("country")
            .distinct()
            .count()
        )
        oldest = "-"
        youngest = "-"
        try:
            oldest = (
                Wine.objects.filter(user=self.request.user)
                .filter(vintage__isnull=False)
                .earliest("vintage")
                .vintage
            )
            youngest = (
                Wine.objects.filter(user=self.request.user)
                .filter(vintage__isnull=False)
                .latest("vintage")
                .vintage
            )
        except Wine.DoesNotExist:
            pass
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
        total_value = f"{formatted_price}{currency}"

        context.update(
            {
                "wines": wines,
                "wines_in_stock": wines_in_stock,
                "countries": countries,
                "oldest": oldest,
                "youngest": youngest,
                "total_value": total_value,
            }
        )

        # Dashboard widget data
        from datetime import date, timedelta

        from wine_cellar.apps.wine.models import DrinkRecord, ReorderReminder, Wishlist

        # Alerts
        overdue_count = (
            Wine.objects.filter(
                user=self.request.user,
                drink_by__isnull=False,
                drink_by__lt=date.today(),
                storageitem__deleted=False,
            )
            .distinct()
            .count()
        )

        upcoming_count = (
            Wine.objects.filter(
                user=self.request.user,
                drink_by__isnull=False,
                drink_by__lte=date.today() + timedelta(days=180),
                drink_by__gte=date.today(),
                storageitem__deleted=False,
            )
            .distinct()
            .count()
        )

        # Low stock reminders
        reminders = ReorderReminder.objects.filter(
            user=self.request.user, is_active=True
        )
        low_stock_count = sum(1 for r in reminders if r.wine.total_stock <= r.min_stock)

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

        # Stats
        total_consumed = DrinkRecord.objects.filter(user=self.request.user).count()
        total_bottles = StorageItem.objects.filter(
            user=self.request.user, deleted=False
        ).count()

        avg_rating = None
        rated = DrinkRecord.objects.filter(user=self.request.user, rating__isnull=False)
        if rated.exists():
            avg_rating = round(sum(r.rating for r in rated) / rated.count(), 1)

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
            }
        )

        return context


class WineCreateView(FormView):
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

        if scanned_label and not extraction_result:
            # Only process if we haven't already extracted data
            try:
                from wine_cellar.apps.wine.services import WineVisionExtractor

                # Extract wine data using vision service
                extractor = WineVisionExtractor()

                # Handle both single and multiple images
                image_data = scanned_label.get("data")
                if isinstance(image_data, list):
                    # Multiple images
                    result = extractor.extract_from_images(image_data)
                else:
                    # Legacy single image (backwards compatibility)
                    result = extractor.extract_from_image(image_data)

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

        # If we have extraction results (either just created or from previous load), use them
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

        return context

    def post(self, request, *args, **kwargs):
        """Handle form submission and vision extraction."""
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
        self.process_form_data(self.request.user, form.cleaned_data)

        # Clear scanned label data from session after successful save
        if "scanned_label" in self.request.session:
            del self.request.session["scanned_label"]
        if "extraction_result" in self.request.session:
            del self.request.session["extraction_result"]

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
        drink_by = cleaned_data["drink_by"]

        wine = Wine(
            abv=abv,
            size=size,
            category=category,
            country=country,
            subregion=subregion,
            name=name,
            barcode=barcode,
            user=user,
            vintage=vintage,
            drink_by=drink_by,
            wine_type=wine_type,
            comment=comment,
            rating=rating,
            price=price,
            rrp=rrp,
        )
        wine.save()

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
            StorageItem.objects.create(
                storage=storage,
                wine=wine,
                row=row,
                column=column,
                user=user,
                price=bottle_price,
            )

        return wine


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
        drink_by = cleaned_data["drink_by"]
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
        wine.drink_by = drink_by
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
            )
            if image is False or not hasattr(image, "instance"):
                if existing_image.exists():
                    existing_image.first().image.delete()
                    existing_image.delete()
            if image and not hasattr(image, "instance"):
                WineImage.objects.get_or_create(
                    image=image, wine=wine, user=user, image_type=image_type
                )


class WineDetailView(DetailView):
    template_name = "wine_detail.html"
    model = Wine

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


class WineListView(FilterView):
    model = Wine
    template_name = "wine_list.html"
    context_object_name = "wines"
    filterset_class = WineFilter
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().order_by("-created")
        qs = qs.annotate(
            effective_price=Coalesce(
                Avg("storageitem__price"),
                "price",
            )
        )
        return qs.filter(user=self.request.user)


class WineScanView(TemplateView):
    template_name = "scan_wine.html"


class WineScannedView(TemplateView):
    template_name = "scanned_wine.html"

    def dispatch(self, request, *args, **kwargs):
        code = self.kwargs["code"]
        wine = Wine.objects.filter(barcode=code).filter(user=self.request.user).first()
        if wine:
            return redirect(reverse("wine-detail", kwargs={"pk": wine.pk}))

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
        wines = Wine.objects.filter(user=self.request.user)

        context.update(
            {
                "wines": wines,
            }
        )
        return context


@login_not_required
def health_check(request):
    """Health check endpoint for container orchestration."""
    try:
        for conn in connections.all():
            conn.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    status_code = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "unhealthy"}, status=status_code)


class DrinkRecordCreateView(FormView):
    template_name = "drink_record_create.html"
    form_class = None  # Set dynamically

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import DrinkRecordForm

        return DrinkRecordForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wine"] = get_object_or_404(
            Wine, pk=self.kwargs["pk"], user=self.request.user
        )
        return context

    def form_valid(self, form):
        from wine_cellar.apps.wine.models import DrinkRecord

        wine = get_object_or_404(Wine, pk=self.kwargs["pk"], user=self.request.user)
        DrinkRecord.objects.create(
            wine=wine,
            user=self.request.user,
            date_consumed=form.cleaned_data["date_consumed"],
            tasting_notes=form.cleaned_data.get("tasting_notes"),
            rating=form.cleaned_data.get("rating"),
            shared_with=form.cleaned_data.get("shared_with"),
            occasion=form.cleaned_data.get("occasion"),
        )
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

        # Value by country
        wines_by_country = {}
        for item in storage_items.select_related("wine"):
            country = item.wine.country_name if item.wine.country else "Unknown"
            if country not in wines_by_country:
                wines_by_country[country] = {"count": 0, "value": Decimal("0.00")}
            wines_by_country[country]["count"] += 1
            if item.price:
                wines_by_country[country]["value"] += item.price

        # Value by type
        wines_by_type = {}
        for item in storage_items.select_related("wine"):
            wine_type = item.wine.get_type if item.wine.wine_type else "Unknown"
            if wine_type not in wines_by_type:
                wines_by_type[wine_type] = {"count": 0, "value": Decimal("0.00")}
            wines_by_type[wine_type]["count"] += 1
            if item.price:
                wines_by_type[wine_type]["value"] += item.price

        context.update(
            {
                "total_value": number_format(total_value, use_l10n=True),
                "total_bottles": storage_items.count(),
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
        from datetime import date, timedelta

        from wine_cellar.apps.wine.models import DrinkingWindowAlert

        context = super().get_context_data(**kwargs)

        # Get existing alerts
        alerts = DrinkingWindowAlert.objects.filter(
            user=self.request.user, is_read=False
        ).select_related("wine")

        # Also find wines approaching drink_by date (within 6 months)
        upcoming_wines = (
            Wine.objects.filter(
                user=self.request.user,
                drink_by__isnull=False,
                drink_by__lte=date.today() + timedelta(days=180),
                drink_by__gte=date.today(),
            )
            .filter(storageitem__deleted=False)
            .distinct()
        )

        # Wines past drink_by
        overdue_wines = (
            Wine.objects.filter(
                user=self.request.user,
                drink_by__isnull=False,
                drink_by__lt=date.today(),
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
        from datetime import date

        from django.db.models import Count
        from django.db.models.functions import TruncMonth

        from wine_cellar.apps.wine.models import DrinkRecord, WineType

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

        # Average rating over time
        rated_records = records.filter(rating__isnull=False).order_by("date_consumed")
        avg_rating = None
        if rated_records.exists():
            total_rating = sum(r.rating for r in rated_records)
            avg_rating = round(total_rating / rated_records.count(), 1)

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

        reminders = ReorderReminder.objects.filter(
            user=user, is_active=True
        ).select_related("wine")

        # Find wines that need reordering
        needs_reorder = []
        for reminder in reminders:
            current_stock = reminder.wine.total_stock
            if current_stock <= reminder.min_stock:
                needs_reorder.append(
                    {
                        "wine": reminder.wine,
                        "current_stock": current_stock,
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

        image = form.cleaned_data["image"]

        # Read image and encode to base64
        image_data = image.read()
        base64_image = base64.b64encode(image_data).decode("utf-8")

        # Store in session for the create view to use
        self.request.session["scanned_label"] = {
            "filename": image.name,
            "size": len(image_data),
            "data": [base64_image],  # Wrap in list for consistency
            "multi_image": False,
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

import base64
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models.functions import Coalesce
from django.forms import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.formats import number_format
from django.views.generic import (
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
)
from django_filters.views import FilterView
from django_ratelimit.decorators import ratelimit

from wine_cellar.apps.storage.models import Storage, get_app_type
from wine_cellar.apps.user.views import get_active_household, get_user_settings
from wine_cellar.apps.whisky.filters import WhiskyFilter
from wine_cellar.apps.whisky.forms import (
    BottleNoteForm,
    ReorderReminderForm,
    WhiskyDrinkRecordForm,
    WhiskyEditForm,
    WhiskyForm,
    WhiskySaleAlertForm,
    WhiskyStockAddForm,
    WhiskyWishlistForm,
)
from wine_cellar.apps.whisky.models import (
    FillLevel,
    Whisky,
    WhiskyBarcode,
    WhiskyBottleNote,
    WhiskyDrinkingWindowAlert,
    WhiskyDrinkRecord,
    WhiskyImage,
    WhiskyPriceHistory,
    WhiskyReorderReminder,
    WhiskySaleAlert,
    WhiskyStorageItem,
    WhiskyVisionExtractionLog,
    WhiskyWishlist,
)

# Maximum allowed image upload size (10MB)
MAX_IMAGE_SIZE = 10 * 1024 * 1024


def base64_to_uploaded_file(base64_data: str, filename: str) -> InMemoryUploadedFile:
    """Convert base64 string to Django InMemoryUploadedFile."""
    image_bytes = base64.b64decode(base64_data)
    image_io = BytesIO(image_bytes)

    return InMemoryUploadedFile(
        file=image_io,
        field_name=None,
        name=filename,
        content_type="image/jpeg",
        size=len(image_bytes),
        charset=None,
    )


class HomePageView(TemplateView):
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

        # Drinking window alerts (drink_to is a year integer)
        import datetime

        current_year = datetime.date.today().year
        overdue_count = (
            Whisky.objects.filter(
                household=household,
                drink_to__lt=current_year,
                whiskystorageitem__deleted=False,
            )
            .distinct()
            .count()
        )
        upcoming_count = (
            Whisky.objects.filter(
                household=household,
                drink_to__gte=current_year,
                drink_to__lte=current_year + 1,
                whiskystorageitem__deleted=False,
            )
            .distinct()
            .count()
        )

        # Dreg alerts
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
                "overdue_count": overdue_count,
                "upcoming_count": upcoming_count,
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
class WhiskyCreateView(FormView):
    """View for creating new whiskies. Rate limited to 20 creations/minute per user."""

    template_name = "whisky/whisky_create.html"
    form_class = WhiskyForm
    success_url = reverse_lazy("whisky-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "user" not in kwargs:
            kwargs["user"] = self.request.user
        if "code" in self.kwargs:
            kwargs["initial"].update({"barcode": self.kwargs["code"]})
        elif self.request.session.get("pending_barcode"):
            kwargs["initial"].update(
                {"barcode": self.request.session.pop("pending_barcode")}
            )
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        user_storages = Storage.objects.filter(
            household=household, app_type=get_app_type()
        )
        free_cells_by_storage = {
            storage.pk: storage.get_free_cells_by_row() for storage in user_storages
        }
        context["free_cells_by_storage"] = free_cells_by_storage
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        whisky, created = self.process_form_data(
            self.request.user, household, form.cleaned_data
        )

        if not created:
            messages.info(
                self.request, "Whisky already exists. Added bottle to your cellar."
            )

        return super().form_valid(form)

    @staticmethod
    @transaction.atomic
    def process_form_data(user, household, cleaned_data):
        abv = cleaned_data["abv"]
        size = cleaned_data["size"]
        barcode = cleaned_data.get("barcode")
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        price = cleaned_data["price"]
        rrp = cleaned_data["rrp"]
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
                "rrp": rrp,
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


class WhiskyUpdateView(FormView):
    template_name = "whisky/whisky_edit.html"
    form_class = WhiskyEditForm
    success_url = reverse_lazy("whisky-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "user" not in kwargs:
            kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        initial.update(model_to_dict(whisky))
        # Populate barcode from related WhiskyBarcode model
        first_barcode = whisky.barcodes.first()
        if first_barcode:
            initial["barcode"] = first_barcode.barcode
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        context["whisky"] = whisky
        context["whisky_images"] = whisky.images.all()
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        self.process_form_data(whisky, self.request.user, form.cleaned_data)
        self.success_url = reverse_lazy("whisky-detail", kwargs={"pk": whisky.pk})
        return super().form_valid(form)

    @staticmethod
    @transaction.atomic
    def process_form_data(whisky, user, cleaned_data):
        abv = cleaned_data["abv"]
        size = cleaned_data["size"]
        barcode = cleaned_data.get("barcode")
        comment = cleaned_data["comment"]
        country = cleaned_data["country"]
        price = cleaned_data["price"]
        rrp = cleaned_data["rrp"]
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
        whisky.color = color
        whisky.bottler = bottler
        whisky.bottler_series = bottler_series
        whisky.cask_number = cask_number
        whisky.batch_number = batch_number
        whisky.bottle_number = bottle_number
        whisky.limited_edition = limited_edition
        whisky.release_year = release_year
        whisky.price = price
        whisky.rrp = rrp
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


class WhiskyDetailView(DetailView):
    template_name = "whisky/whisky_detail.html"
    model = Whisky

    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return (
            qs.select_related("distillery", "region", "bottler", "source")
            .prefetch_related(
                "cask_history",
                "images",
                "barcodes",
            )
            .annotate(
                stock_count=Count(
                    "whiskystorageitem",
                    filter=Q(whiskystorageitem__deleted=False),
                    distinct=True,
                )
            )
            .filter(household=household)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        whisky = self.object
        household = get_active_household(self.request.user)
        duplicates = (
            Whisky.objects.filter(household=household, name=whisky.name)
            .exclude(pk=whisky.pk)
            .annotate(
                stock_count=Count(
                    "whiskystorageitem",
                    filter=Q(whiskystorageitem__deleted=False),
                    distinct=True,
                ),
                barcode_count=Count("barcodes", distinct=True),
            )
        )
        context["duplicates"] = duplicates
        return context


class WhiskyDeleteView(DeleteView):
    model = Whisky
    template_name = "whisky/whisky_confirm_delete.html"
    success_url = reverse_lazy("whisky-list")

    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return qs.filter(household=household)


class WhiskyListView(FilterView):
    model = Whisky
    template_name = "whisky/whisky_list.html"
    context_object_name = "whiskies"
    filterset_class = WhiskyFilter
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
            .select_related("distillery", "region", "bottler")
            .prefetch_related("images")
            .order_by("-created")
        )
        qs = qs.annotate(
            effective_price=Coalesce(
                Avg("whiskystorageitem__price"),
                "price",
            ),
            stock_count=Count(
                "whiskystorageitem",
                filter=Q(whiskystorageitem__deleted=False),
                distinct=True,
            ),
        )
        household = get_active_household(self.request.user)
        return qs.filter(household=household).distinct()


class WhiskyScanView(TemplateView):
    template_name = "whisky/scan_whisky.html"


class WhiskyScannedView(TemplateView):
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


class WhiskyMapView(TemplateView):
    template_name = "whisky/whisky_map.html"

    def get_context_data(self, **kwargs):
        import json as json_module

        from wine_cellar.apps.whisky.models import Distillery

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
        return context


class LabelScanView(TemplateView):
    template_name = "whisky/label_scan.html"


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
            if barcodes and "barcode" not in response_data["data"]:
                response_data["data"]["barcode"] = barcodes[0]
                if "barcode" not in response_data["extracted_fields"]:
                    response_data["extracted_fields"].append("barcode")

        return JsonResponse(response_data)

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Error in whisky AJAX vision extraction")
        return JsonResponse({"error": str(e)}, status=500)


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

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Error in whisky barcode scanning")
        return JsonResponse({"error": str(e)}, status=500)


class DrinkRecordCreateView(FormView):
    template_name = "whisky/drink_record_create.html"
    form_class = WhiskyDrinkRecordForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        kwargs["whisky"] = whisky
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["whisky"] = get_object_or_404(
            Whisky, pk=self.kwargs["pk"], household=household
        )
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        storage_item = form.cleaned_data.get("storage_item")

        # Create drink record
        WhiskyDrinkRecord.objects.create(
            whisky=whisky,
            user=self.request.user,
            household=household,
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

        self.success_url = reverse_lazy("whisky-detail", kwargs={"pk": whisky.pk})
        return super().form_valid(form)


class DrinkRecordListView(TemplateView):
    template_name = "whisky/drink_record_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["drink_records"] = WhiskyDrinkRecord.objects.filter(
            household=household
        ).select_related("whisky")
        return context


class DrinkRecordEditView(FormView):
    template_name = "whisky/drink_record_edit.html"
    form_class = WhiskyDrinkRecordForm

    def get_object(self):
        household = get_active_household(self.request.user)
        return get_object_or_404(
            WhiskyDrinkRecord, pk=self.kwargs["pk"], household=household
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
        context["whisky"] = record.whisky
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
    template_name = "whisky/drink_record_confirm_delete.html"
    success_url = reverse_lazy("drink-history")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return WhiskyDrinkRecord.objects.filter(household=household)


class WishlistListView(TemplateView):
    template_name = "whisky/wishlist_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["wishlist_items"] = WhiskyWishlist.objects.filter(
            household=household, purchased=False
        )
        return context


class WishlistCreateView(FormView):
    template_name = "whisky/wishlist_create.html"
    form_class = WhiskyWishlistForm
    success_url = reverse_lazy("wishlist-list")

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        WhiskyWishlist.objects.create(
            user=self.request.user,
            household=household,
            name=form.cleaned_data["name"],
            whisky_type=form.cleaned_data.get("whisky_type") or None,
            distillery=form.cleaned_data.get("distillery"),
            region=form.cleaned_data.get("region"),
            age_statement=form.cleaned_data.get("age_statement"),
            price_limit=form.cleaned_data.get("price_limit"),
            notes=form.cleaned_data.get("notes"),
            priority=form.cleaned_data.get("priority", 1),
        )
        return super().form_valid(form)


class WishlistDeleteView(DeleteView):
    template_name = "whisky/wishlist_confirm_delete.html"
    success_url = reverse_lazy("wishlist-list")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return WhiskyWishlist.objects.filter(household=household)


class WishlistPurchasedView(TemplateView):
    """Mark a wishlist item as purchased."""

    def get(self, request, *args, **kwargs):
        household = get_active_household(request.user)
        item = get_object_or_404(WhiskyWishlist, pk=kwargs["pk"], household=household)
        item.purchased = True
        item.save()
        return redirect("wishlist-list")


class CellarValueView(TemplateView):
    template_name = "whisky/cellar_value.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        household = get_active_household(user)
        user_settings = get_user_settings(user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )

        # Total value from storage items
        storage_items = WhiskyStorageItem.objects.filter(
            household=household, deleted=False
        )
        total_value = storage_items.aggregate(
            total=Coalesce(Sum("price"), Decimal("0.00"))
        )["total"]
        total_bottles = storage_items.count()

        # Value by distillery and type
        whiskies_by_distillery = {}
        whiskies_by_type = {}
        for item in storage_items.select_related("whisky__distillery"):
            distillery = (
                item.whisky.distillery.name if item.whisky.distillery else "Unknown"
            )
            whisky_type = item.whisky.get_whisky_type_display()

            # Distillery stats
            if distillery not in whiskies_by_distillery:
                whiskies_by_distillery[distillery] = {"count": 0, "value": Decimal("0")}
            whiskies_by_distillery[distillery]["count"] += 1
            if item.price:
                whiskies_by_distillery[distillery]["value"] += item.price

            # Type stats
            if whisky_type not in whiskies_by_type:
                whiskies_by_type[whisky_type] = {"count": 0, "value": Decimal("0")}
            whiskies_by_type[whisky_type]["count"] += 1
            if item.price:
                whiskies_by_type[whisky_type]["value"] += item.price

        # Format values as integers
        for data in whiskies_by_distillery.values():
            data["value"] = int(data["value"])
        for data in whiskies_by_type.values():
            data["value"] = int(data["value"])

        context.update(
            {
                "total_value": int(total_value),
                "total_bottles": total_bottles,
                "currency": currency,
                "by_distillery": whiskies_by_distillery,
                "by_type": whiskies_by_type,
            }
        )
        return context


class ConsumptionStatsView(TemplateView):
    template_name = "whisky/consumption_stats.html"

    def get_context_data(self, **kwargs):
        from collections import defaultdict

        from django.db.models import Count
        from django.db.models.functions import TruncMonth

        context = super().get_context_data(**kwargs)
        user = self.request.user
        household = get_active_household(user)

        records = WhiskyDrinkRecord.objects.filter(household=household).select_related(
            "whisky__distillery"
        )

        # Drinks by month
        by_month = (
            records.annotate(month=TruncMonth("date_consumed"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        # Drinks by type
        by_type = defaultdict(int)
        for record in records:
            whisky_type = record.whisky.get_whisky_type_display()
            by_type[whisky_type] += 1

        # Drinks by distillery
        by_distillery = defaultdict(int)
        for record in records:
            distillery = (
                record.whisky.distillery.name if record.whisky.distillery else "Unknown"
            )
            by_distillery[distillery] += 1

        # Average rating
        avg_rating_result = records.filter(rating__isnull=False).aggregate(
            avg=Avg("rating")
        )
        avg_rating = (
            round(avg_rating_result["avg"], 1) if avg_rating_result["avg"] else None
        )

        # Top rated whiskies
        top_rated = records.filter(rating__isnull=False).order_by("-rating")[:5]

        context.update(
            {
                "total_consumed": records.count(),
                "by_month": list(by_month),
                "by_type": dict(by_type),
                "by_distillery": dict(by_distillery),
                "avg_rating": avg_rating,
                "top_rated": top_rated,
            }
        )
        return context


class BottleNoteCreateView(FormView):
    template_name = "whisky/bottle_note_create.html"
    form_class = BottleNoteForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["storage_item"] = get_object_or_404(
            WhiskyStorageItem, pk=self.kwargs["pk"], household=household
        )
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        storage_item = get_object_or_404(
            WhiskyStorageItem, pk=self.kwargs["pk"], household=household
        )
        WhiskyBottleNote.objects.create(
            storage_item=storage_item,
            user=self.request.user,
            household=household,
            note_date=form.cleaned_data["note_date"],
            note=form.cleaned_data["note"],
        )
        self.success_url = reverse_lazy(
            "whisky-detail", kwargs={"pk": storage_item.whisky.pk}
        )
        return super().form_valid(form)


class DrinkingWindowAlertsView(TemplateView):
    template_name = "whisky/drinking_window_alerts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)

        # Get existing alerts
        alerts = WhiskyDrinkingWindowAlert.objects.filter(
            household=household, is_read=False
        ).select_related("whisky")

        context.update(
            {
                "alerts": alerts,
            }
        )
        return context


class ReorderRemindersView(TemplateView):
    template_name = "whisky/reorder_reminders.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        household = get_active_household(user)

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

        # Find whiskies that need reordering
        needs_reorder = []
        for reminder in reminders:
            if reminder.current_stock <= reminder.min_stock:
                needs_reorder.append(
                    {
                        "whisky": reminder.whisky,
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
    template_name = "whisky/reorder_reminder_create.html"
    form_class = ReorderReminderForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["whisky"] = get_object_or_404(
            Whisky, pk=self.kwargs["pk"], household=household
        )
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        WhiskyReorderReminder.objects.update_or_create(
            whisky=whisky,
            user=self.request.user,
            household=household,
            defaults={
                "min_stock": form.cleaned_data["min_stock"],
                "is_active": True,
            },
        )
        self.success_url = reverse_lazy("whisky-detail", kwargs={"pk": whisky.pk})
        return super().form_valid(form)


class ReorderReminderDeleteView(DeleteView):
    template_name = "whisky/reorder_reminder_confirm_delete.html"
    success_url = reverse_lazy("reorder-reminders")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return WhiskyReorderReminder.objects.filter(household=household)


class SaleAlertsView(TemplateView):
    """View and manage sale alerts."""

    template_name = "whisky/sale_alerts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["alerts"] = (
            WhiskySaleAlert.objects.filter(household=household)
            .select_related("whisky", "source")
            .order_by("-is_active", "-created")
        )
        return context


class SaleAlertCreateView(FormView):
    """Create a new sale alert."""

    template_name = "whisky/sale_alert_create.html"
    form_class = WhiskySaleAlertForm
    success_url = reverse_lazy("sale-alerts")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["whisky"] = get_object_or_404(
            Whisky, pk=self.kwargs["pk"], household=household
        )
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        whisky = get_object_or_404(Whisky, pk=self.kwargs["pk"], household=household)
        WhiskySaleAlert.objects.create(
            user=self.request.user,
            household=household,
            whisky=whisky,
            source=form.cleaned_data.get("source"),
            threshold_percent=form.cleaned_data.get("threshold_percent", 10),
            threshold_price=form.cleaned_data.get("threshold_price"),
        )
        self.success_url = reverse_lazy("whisky-detail", kwargs={"pk": whisky.pk})
        return super().form_valid(form)


class SaleAlertDeleteView(DeleteView):
    """Delete a sale alert."""

    template_name = "whisky/sale_alert_confirm_delete.html"
    success_url = reverse_lazy("sale-alerts")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return WhiskySaleAlert.objects.filter(household=household)


class SaleAlertToggleView(TemplateView):
    """Toggle a sale alert's active status."""

    def get(self, request, *args, **kwargs):
        household = get_active_household(request.user)
        alert = get_object_or_404(WhiskySaleAlert, pk=kwargs["pk"], household=household)
        alert.is_active = not alert.is_active
        alert.save(update_fields=["is_active"])
        return redirect("sale-alerts")


class StorageItemAddView(FormView):
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
        )

        self.success_url = reverse_lazy("whisky-detail", kwargs={"pk": whisky.pk})
        return super().form_valid(form)


class StorageItemDeleteView(DeleteView):
    """Remove a bottle from storage."""

    template_name = "whisky/stock_confirm_delete.html"

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return WhiskyStorageItem.objects.filter(household=household)

    def get_success_url(self):
        return reverse_lazy("whisky-detail", kwargs={"pk": self.object.whisky.pk})


class StorageItemListView(TemplateView):
    """List all bottles in storage."""

    template_name = "whisky/bottle_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["storage_items"] = (
            WhiskyStorageItem.objects.filter(household=household, deleted=False)
            .select_related("whisky", "storage")
            .order_by("storage__order", "row", "column")
        )
        return context


class StorageItemUpdateView(FormView):
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

        item.save()

        self.success_url = reverse_lazy("whisky-detail", kwargs={"pk": item.whisky.pk})
        return super().form_valid(form)


class StorageItemHistoryView(ListView):
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


class WhiskyMergeConfirmView(TemplateView):
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
            WhiskySaleAlert.objects.filter(whisky=duplicate).update(whisky=primary)

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


class WhiskyImagesView(DetailView):
    """View for managing whisky images (set primary, crop)."""

    template_name = "whisky/whisky_images.html"
    model = Whisky
    context_object_name = "whisky"

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return Whisky.objects.filter(household=household).prefetch_related("images")


@login_required
def set_primary_image(request, pk):
    """Set a WhiskyImage as the primary image for its whisky."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    whisky_image = get_object_or_404(WhiskyImage, pk=pk, user=request.user)

    # Toggle: if already primary, unset it; otherwise set it as primary
    if whisky_image.is_primary:
        whisky_image.is_primary = False
        whisky_image.save(update_fields=["is_primary"])
        return JsonResponse({"success": True, "is_primary": False})
    else:
        # Clear other primary flags first
        WhiskyImage.objects.filter(whisky=whisky_image.whisky, is_primary=True).update(
            is_primary=False
        )
        whisky_image.is_primary = True
        whisky_image.save()
        return JsonResponse({"success": True, "is_primary": True})


@login_required
def crop_whisky_image(request, pk):
    """Apply manual crop to a WhiskyImage and create a new thumbnail."""
    import json

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    whisky_image = get_object_or_404(WhiskyImage, pk=pk, user=request.user)

    try:
        data = json.loads(request.body)
        width = int(data.get("width", 100))
        height = int(data.get("height", 100))

        # Validate crop dimensions
        if width <= 0 or height <= 0:
            return JsonResponse({"error": "Invalid crop dimensions"}, status=400)

        # Delete old thumbnail if exists
        old_thumbnail = whisky_image.thumbnail
        if old_thumbnail:
            try:
                old_thumbnail.delete(save=False)
            except Exception:
                pass

        # Apply the crop (placeholder - implement crop logic)
        # For now, just return success
        return JsonResponse(
            {
                "success": True,
                "message": "Crop not yet implemented",
            }
        )
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Error cropping image")
        return JsonResponse({"error": str(e)}, status=500)

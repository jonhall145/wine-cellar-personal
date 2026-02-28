import json
import logging
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.forms import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.formats import number_format
from django.views.generic import DeleteView, DetailView, FormView, TemplateView

from wine_cellar.apps.household.mixins import RequireHouseholdMixin, RequireMemberMixin
from wine_cellar.apps.storage.models import Storage, get_app_type
from wine_cellar.apps.user.views import get_active_household, get_user_settings

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

# --- Wishlist views ---


class BaseWishlistListView(RequireHouseholdMixin, TemplateView):
    wishlist_model = None  # Set by subclass

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["wishlist_items"] = self.wishlist_model.objects.filter(
            household=household, purchased=False
        )
        return context


class BaseWishlistDeleteView(RequireMemberMixin, DeleteView):
    success_url = reverse_lazy("wishlist-list")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return self.model.objects.filter(household=household)


class BaseWishlistPurchasedView(RequireHouseholdMixin, TemplateView):
    """Mark a wishlist item as purchased."""

    wishlist_model = None  # Set by subclass

    def get(self, request, *args, **kwargs):
        household = get_active_household(request.user)
        item = get_object_or_404(
            self.wishlist_model, pk=kwargs["pk"], household=household
        )
        item.purchased = True
        item.save()
        return redirect("wishlist-list")


# --- Drink record views ---


class BaseDrinkRecordListView(RequireHouseholdMixin, TemplateView):
    drink_record_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["drink_records"] = self.drink_record_model.objects.filter(
            household=household
        ).select_related(self.beverage_fk_name)
        return context


class BaseDrinkRecordEditView(RequireMemberMixin, FormView):
    drink_record_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"

    def get_object(self):
        household = get_active_household(self.request.user)
        return get_object_or_404(
            self.drink_record_model, pk=self.kwargs["pk"], household=household
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
        context[self.beverage_fk_name] = getattr(record, self.beverage_fk_name)
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


class BaseDrinkRecordDeleteView(RequireMemberMixin, DeleteView):
    success_url = reverse_lazy("drink-history")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return self.model.objects.filter(household=household)


# --- Bottle note views ---


class BaseBottleNoteCreateView(RequireMemberMixin, FormView):
    storage_item_model = None  # Set by subclass
    note_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    detail_url_name = None  # e.g. "wine-detail" or "whisky-detail"

    def get_form_class(self):
        from wine_cellar.apps.core.forms import BottleNoteForm

        return BottleNoteForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["storage_item"] = get_object_or_404(
            self.storage_item_model, pk=self.kwargs["pk"], household=household
        )
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        storage_item = get_object_or_404(
            self.storage_item_model, pk=self.kwargs["pk"], household=household
        )
        self.note_model.objects.create(
            storage_item=storage_item,
            user=self.request.user,
            household=household,
            note_date=form.cleaned_data["note_date"],
            note=form.cleaned_data["note"],
        )
        beverage = getattr(storage_item, self.beverage_fk_name)
        self.success_url = reverse_lazy(
            self.detail_url_name, kwargs={"pk": beverage.pk}
        )
        return super().form_valid(form)


# --- Reorder reminder views ---


class BaseReorderRemindersView(RequireHouseholdMixin, TemplateView):
    reminder_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    stock_reverse_path = None  # e.g. "wine__storageitem" or "whisky__whiskystorageitem"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)

        reminders = (
            self.reminder_model.objects.filter(household=household, is_active=True)
            .select_related(self.beverage_fk_name)
            .annotate(
                current_stock=Count(
                    self.stock_reverse_path,
                    filter=Q(**{f"{self.stock_reverse_path}__deleted": False}),
                )
            )
        )

        needs_reorder = []
        for reminder in reminders:
            if reminder.current_stock <= reminder.min_stock:
                beverage = getattr(reminder, self.beverage_fk_name)
                needs_reorder.append(
                    {
                        self.beverage_fk_name: beverage,
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


class BaseReorderReminderCreateView(RequireMemberMixin, FormView):
    beverage_model = None  # Set by subclass
    reminder_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    detail_url_name = None  # e.g. "wine-detail" or "whisky-detail"

    def get_form_class(self):
        from wine_cellar.apps.core.forms import ReorderReminderForm

        return ReorderReminderForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context[self.beverage_fk_name] = get_object_or_404(
            self.beverage_model, pk=self.kwargs["pk"], household=household
        )
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model, pk=self.kwargs["pk"], household=household
        )
        self.reminder_model.objects.update_or_create(
            **{self.beverage_fk_name: beverage},
            user=self.request.user,
            household=household,
            defaults={
                "min_stock": form.cleaned_data["min_stock"],
                "is_active": True,
            },
        )
        self.success_url = reverse_lazy(
            self.detail_url_name, kwargs={"pk": beverage.pk}
        )
        return super().form_valid(form)


# --- Drink record create view ---


class BaseDrinkRecordCreateView(RequireMemberMixin, FormView):
    beverage_model = None  # Set by subclass
    drink_record_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    detail_url_name = None  # e.g. "wine-detail" or "whisky-detail"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model, pk=self.kwargs["pk"], household=household
        )
        kwargs[self.beverage_fk_name] = beverage
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context[self.beverage_fk_name] = get_object_or_404(
            self.beverage_model, pk=self.kwargs["pk"], household=household
        )
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model, pk=self.kwargs["pk"], household=household
        )
        storage_item = form.cleaned_data.get("storage_item")

        self.drink_record_model.objects.create(
            **{self.beverage_fk_name: beverage},
            user=self.request.user,
            household=household,
            date_consumed=form.cleaned_data["date_consumed"],
            tasting_notes=form.cleaned_data.get("tasting_notes"),
            rating=form.cleaned_data.get("rating"),
            shared_with=form.cleaned_data.get("shared_with"),
            occasion=form.cleaned_data.get("occasion"),
            storage_item=storage_item,
        )

        if storage_item:
            self.handle_bottle_update(form, storage_item)

        self.success_url = reverse_lazy(
            self.detail_url_name, kwargs={"pk": beverage.pk}
        )
        return super().form_valid(form)

    def handle_bottle_update(self, form, storage_item):
        """Default: mark bottle as consumed. Override for custom behavior."""
        storage_item.deleted = True
        storage_item.save(update_fields=["deleted"])


class BaseReorderReminderDeleteView(RequireMemberMixin, DeleteView):
    success_url = reverse_lazy("reorder-reminders")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return self.model.objects.filter(household=household)


# --- Cellar value view ---


class BaseCellarValueView(RequireHouseholdMixin, TemplateView):
    storage_item_model = None  # Set by subclass
    price_fallback_path = None  # e.g. "wine__price" or "whisky__price"
    beverage_fk_name = None  # "wine" or "whisky"
    select_related_fields = ()  # e.g. ("wine",) or ("whisky__distillery",)

    def get_groupings(self, item):
        """Return {context_key: group_name} dict for this item.

        Subclasses must implement. Example return:
            {"by_country": "France", "by_type": "Red"}
        """
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        user_settings = get_user_settings(self.request.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )

        storage_items = self.storage_item_model.objects.filter(
            household=household, deleted=False
        )
        total_value = storage_items.aggregate(
            total=Coalesce(
                Sum(Coalesce("price", self.price_fallback_path)), Decimal("0.00")
            )
        )["total"]
        total_bottles = storage_items.count()

        groups = {}
        for item in storage_items.select_related(*self.select_related_fields):
            beverage = getattr(item, self.beverage_fk_name)
            if item.price is not None:
                item_price = item.price
            elif beverage.price is not None:
                item_price = beverage.price
            else:
                item_price = Decimal("0")

            for context_key, group_name in self.get_groupings(item).items():
                bucket = groups.setdefault(context_key, {})
                if group_name not in bucket:
                    bucket[group_name] = {"count": 0, "value": Decimal("0")}
                bucket[group_name]["count"] += 1
                bucket[group_name]["value"] += item_price

        for bucket in groups.values():
            for data in bucket.values():
                data["value"] = int(data["value"])

        context.update(
            {
                "total_value": int(total_value),
                "total_bottles": total_bottles,
                "currency": currency,
                **groups,
            }
        )
        return context


# --- Beverage delete view ---


class BaseBeverageDeleteView(RequireMemberMixin, DeleteView):
    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return qs.filter(household=household)


# --- Images view ---


class BaseImagesView(RequireHouseholdMixin, DetailView):
    """View for managing beverage images (set primary, crop)."""

    images_prefetch_name = None  # e.g. "wineimage_set" or "images"

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return self.model.objects.filter(household=household).prefetch_related(
            self.images_prefetch_name
        )


# --- List view with pagination ---


class BaseListView(RequireHouseholdMixin):
    """Mixin for paginated list views with stock/price annotations.

    Designed to be used with FilterView (django-filter).
    Subclasses must set: storage_item_reverse, select_related_fields,
    prefetch_related_fields.
    """

    paginate_by = 10
    per_page_options = [10, 25, 50, 100]
    storage_item_reverse = None  # e.g. "storageitem" or "whiskystorageitem"
    select_related_fields = ()  # e.g. ("size", "appellation")
    prefetch_related_fields = ()  # e.g. ("grapes", "wineimage_set")

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
        price_path = f"{self.storage_item_reverse}__price"
        qs = (
            super()
            .get_queryset()
            .select_related(*self.select_related_fields)
            .prefetch_related(*self.prefetch_related_fields)
            .order_by("-created")
        )
        qs = qs.annotate(
            effective_price=Coalesce(Avg(price_path), "price"),
            stock_count=Count(
                self.storage_item_reverse,
                filter=Q(**{f"{self.storage_item_reverse}__deleted": False}),
                distinct=True,
            ),
        )
        household = get_active_household(self.request.user)
        return qs.filter(household=household).distinct()


# --- Detail view ---


class BaseDetailView(RequireHouseholdMixin, DetailView):
    """Base detail view with household filtering and duplicate detection."""

    select_related_fields = ()
    prefetch_related_fields = ()
    storage_item_reverse = None  # e.g. "storageitem" or "whiskystorageitem"

    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return (
            qs.select_related(*self.select_related_fields)
            .prefetch_related(*self.prefetch_related_fields)
            .annotate(
                stock_count=Count(
                    self.storage_item_reverse,
                    filter=Q(**{f"{self.storage_item_reverse}__deleted": False}),
                    distinct=True,
                )
            )
            .filter(household=household)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        beverage = self.object
        household = get_active_household(self.request.user)
        duplicates = (
            self.model.objects.filter(household=household, name=beverage.name)
            .exclude(pk=beverage.pk)
            .annotate(
                stock_count=Count(
                    self.storage_item_reverse,
                    filter=Q(**{f"{self.storage_item_reverse}__deleted": False}),
                    distinct=True,
                ),
                barcode_count=Count("barcodes", distinct=True),
            )
        )
        context["duplicates"] = duplicates
        return context


# --- Scan view ---


class BaseScanView(RequireHouseholdMixin, TemplateView):
    """Base view for barcode scan page — subclasses only set template_name."""

    pass


# --- Consumption stats view ---


class BaseConsumptionStatsView(RequireHouseholdMixin, TemplateView):
    """Base view for consumption statistics with shared aggregations."""

    drink_record_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    select_related_fields = ()  # e.g. ("wine",) or ("whisky__distillery",)

    def get_secondary_stats(self, records):
        """Return app-specific groupings as {context_key: dict}.

        Subclasses must implement. Example return:
            {"by_country": {"France": 5, "Italy": 3}}
        """
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)

        records = self.drink_record_model.objects.filter(
            household=household
        ).select_related(*self.select_related_fields)

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
            beverage = getattr(record, self.beverage_fk_name)
            by_type[self.get_type_display(beverage)] += 1

        # Average rating
        avg_rating_result = records.filter(rating__isnull=False).aggregate(
            avg=Avg("rating")
        )
        avg_rating = (
            round(avg_rating_result["avg"], 1) if avg_rating_result["avg"] else None
        )

        # Top rated
        top_rated = records.filter(rating__isnull=False).order_by("-rating")[:5]

        context.update(
            {
                "total_consumed": records.count(),
                "by_month": list(by_month),
                "by_type": dict(by_type),
                "avg_rating": avg_rating,
                "top_rated": top_rated,
                **self.get_secondary_stats(records),
            }
        )
        return context

    def get_type_display(self, beverage):
        """Return display string for the beverage type. Override per app."""
        raise NotImplementedError


# --- Wishlist create view ---


class BaseWishlistCreateView(RequireMemberMixin, FormView):
    """Base view for creating wishlist items."""

    wishlist_model = None  # Set by subclass
    success_url = reverse_lazy("wishlist-list")

    def get_extra_create_kwargs(self, form):
        """Return app-specific field kwargs for wishlist creation.

        Subclasses must implement. Example return:
            {"wine_type": form.cleaned_data.get("wine_type") or None}
        """
        raise NotImplementedError

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        self.wishlist_model.objects.create(
            user=self.request.user,
            household=household,
            name=form.cleaned_data["name"],
            price_limit=form.cleaned_data.get("price_limit"),
            notes=form.cleaned_data.get("notes"),
            priority=form.cleaned_data.get("priority", 1),
            **self.get_extra_create_kwargs(form),
        )
        return super().form_valid(form)


# --- Shared AJAX helpers ---


def set_primary_image_ajax(request, pk, image_model):
    """Set/toggle primary image. Shared by wine and whisky apps."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    image = get_object_or_404(image_model, pk=pk, user=request.user)

    if image.is_primary:
        image.is_primary = False
        image.save(update_fields=["is_primary"])
        return JsonResponse({"success": True, "is_primary": False})
    else:
        # Clear other primary flags for the same parent beverage
        parent_field = _get_parent_field(image)
        parent_value = getattr(image, parent_field)
        image_model.objects.filter(
            **{parent_field: parent_value}, is_primary=True
        ).update(is_primary=False)
        image.is_primary = True
        image.save()
        return JsonResponse({"success": True, "is_primary": True})


def _get_parent_field(image):
    """Return the FK field name linking the image to its parent beverage."""
    if hasattr(image, "wine"):
        return "wine"
    return "whisky"


def crop_image_ajax(request, pk, image_model):
    """Apply manual crop to an image. Shared by wine and whisky apps."""
    from wine_cellar.apps.wine.utils import apply_manual_crop

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    image = get_object_or_404(image_model, pk=pk, user=request.user)

    try:
        data = json.loads(request.body)
        x = int(data.get("x", 0))
        y = int(data.get("y", 0))
        width = int(data.get("width", 100))
        height = int(data.get("height", 100))

        if width <= 0 or height <= 0:
            return JsonResponse({"error": "Invalid crop dimensions"}, status=400)

        old_thumbnail = image.thumbnail
        if old_thumbnail:
            try:
                old_thumbnail.delete(save=False)
            except Exception:
                pass

        thumb_path = apply_manual_crop(image, x, y, width, height)
        image.thumbnail = thumb_path
        image.save(update_fields=["thumbnail"])

        return JsonResponse({"success": True, "thumbnail_url": image.thumbnail.url})
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid request data"}, status=400)
    except Exception:
        logger.exception("Error cropping image")
        return JsonResponse(
            {"error": "An internal error occurred while processing the image."},
            status=500,
        )


# --- Beverage update view ---


class BaseBeverageUpdateView(RequireMemberMixin, FormView):
    """Base view for editing an existing beverage (wine or whisky).

    Subclasses must set:
        beverage_model, beverage_fk_name, image_related_name,
        detail_url_name
    and implement process_form_data(beverage, user, cleaned_data).
    """

    beverage_model = None
    beverage_fk_name = None  # "wine" or "whisky"
    image_related_name = None  # e.g. "wineimage_set" or "images"
    detail_url_name = None  # e.g. "wine-detail" or "whisky-detail"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "user" not in kwargs:
            kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model,
            pk=self.kwargs["pk"],
            household=household,
        )
        initial.update(model_to_dict(beverage))
        first_barcode = beverage.barcodes.first()
        if first_barcode:
            initial["barcode"] = first_barcode.barcode
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model,
            pk=self.kwargs["pk"],
            household=household,
        )
        context[self.beverage_fk_name] = beverage
        context[f"{self.beverage_fk_name}_images"] = getattr(
            beverage, self.image_related_name
        ).all()
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model,
            pk=self.kwargs["pk"],
            household=household,
        )
        self.process_form_data(beverage, self.request.user, form.cleaned_data)
        self.success_url = reverse_lazy(
            self.detail_url_name, kwargs={"pk": beverage.pk}
        )
        return super().form_valid(form)

    def process_form_data(self, beverage, user, cleaned_data):
        raise NotImplementedError


# --- Beverage create view ---


class BaseBeverageCreateView(RequireMemberMixin, FormView):
    """Base view for creating a new beverage with vision extraction.

    Subclasses must set:
        vision_extractor_path, add_url_name, beverage_label
    and implement:
        process_form_data(user, household, cleaned_data) -> (beverage, created)
        resolve_extracted_data(result_data, initial) — FK resolution
    Optionally override:
        post_create(beverage, created) — post-creation processing
    """

    vision_extractor_path = None  # dotted path for lazy import
    add_url_name = None  # e.g. "wine-add" or "whisky-add"
    beverage_label = None  # "wine" or "whisky"

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

    def get_initial(self):
        initial = super().get_initial()

        scanned_label = self.request.session.get("scanned_label")
        extraction_result = self.request.session.get("extraction_result")

        should_extract = scanned_label and (
            not extraction_result or extraction_result.get("errors")
        )

        if should_extract:
            try:
                extractor = self._get_extractor()
                image_data = scanned_label.get("data")
                user = self.request.user
                if isinstance(image_data, list):
                    result = extractor.extract_from_images(image_data, user=user)
                else:
                    result = extractor.extract_from_images([image_data], user=user)

                self.request.session["extraction_result"] = {
                    "confidence": result.get("confidence", "low"),
                    "extracted_fields": result.get("extracted_fields", []),
                    "errors": result.get("errors", []),
                    "scanned_image": (
                        image_data[0] if isinstance(image_data, list) else image_data
                    ),
                    "image_count": (
                        len(image_data) if isinstance(image_data, list) else 1
                    ),
                    "extracted_data": result.get("data", {}),
                }
                extraction_result = self.request.session["extraction_result"]

            except Exception:
                logger.exception(
                    "Error extracting %s data from scanned label",
                    self.beverage_label,
                )
                self.request.session["extraction_result"] = {
                    "confidence": "low",
                    "extracted_fields": [],
                    "errors": ["Extraction failed"],
                    "scanned_image": scanned_label.get("data"),
                    "extracted_data": {},
                }
                extraction_result = self.request.session["extraction_result"]

        if extraction_result:
            result_data = extraction_result.get("extracted_data", {})
            if result_data:
                self.resolve_extracted_data(result_data, initial)
                initial.update(result_data)

        return initial

    def _get_extractor(self):
        """Lazy-import the vision extractor from the dotted path."""
        from importlib import import_module

        module_path, class_name = self.vision_extractor_path.rsplit(".", 1)
        module = import_module(module_path)
        cls = getattr(module, class_name)
        return cls()

    def resolve_extracted_data(self, result_data, initial):
        """Resolve FK fields in extracted data. Override per app."""
        pass

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        user_storages = Storage.objects.filter(
            household=household, app_type=get_app_type()
        )
        free_cells_by_storage = {s.pk: s.get_free_cells_by_row() for s in user_storages}
        context["free_cells_by_storage"] = free_cells_by_storage

        extraction_result = self.request.session.get("extraction_result")
        if extraction_result:
            context["extraction_result"] = extraction_result
            context["scanned_image"] = extraction_result.get("scanned_image")
            context["extracted_fields"] = extraction_result.get("extracted_fields", [])
            context["confidence"] = extraction_result.get("confidence", "low")

        scanned_label = self.request.session.get("scanned_label")
        if scanned_label:
            image_data = scanned_label.get("data")
            if isinstance(image_data, list):
                if len(image_data) > 1:
                    context["scanned_back_image"] = image_data[1]
                if len(image_data) > 2:
                    context["scanned_front_image"] = image_data[2]

        return context

    def form_valid(self, form):
        from wine_cellar.apps.core.utils import base64_to_uploaded_file

        # Attach scanned images if user hasn't uploaded their own
        scanned_label = self.request.session.get("scanned_label")
        if scanned_label:
            image_data = scanned_label.get("data")
            if isinstance(image_data, list):
                use_front = self.request.POST.get("use_scanned_front", "0")
                use_back = self.request.POST.get("use_scanned_back", "0")

                if (
                    use_back == "1"
                    and len(image_data) > 1
                    and not form.cleaned_data.get("image_back_label")
                ):
                    form.cleaned_data["image_back_label"] = base64_to_uploaded_file(
                        image_data[1], "scanned_back_label.jpg"
                    )

                if (
                    use_front == "1"
                    and len(image_data) > 2
                    and not form.cleaned_data.get("image_front_label")
                ):
                    form.cleaned_data["image_front_label"] = base64_to_uploaded_file(
                        image_data[2], "scanned_front_label.jpg"
                    )

        household = get_active_household(self.request.user)
        beverage, created = self.process_form_data(
            self.request.user, household, form.cleaned_data
        )

        self.post_create(beverage, created)

        # Clear session data
        for key in ("scanned_label", "extraction_result"):
            self.request.session.pop(key, None)

        if not created:
            from django.contrib import messages

            messages.info(
                self.request,
                f"{self.beverage_label.title()} already exists. "
                f"Added bottle to your cellar.",
            )

        return super().form_valid(form)

    def process_form_data(self, user, household, cleaned_data):
        raise NotImplementedError

    def post_create(self, beverage, created):
        """Hook for post-creation processing. Override per app."""
        pass


# --- Shared AJAX vision extraction ---


def extract_vision_ajax(
    request,
    *,
    barcode_scanner_factory,
    vision_extractor_path,
    beverage_label,
    resolve_extracted_fks=None,
):
    """Shared AJAX endpoint for beverage data extraction from uploaded images.

    Attempts barcode scanning first (non-AI, faster), then falls back
    to AI vision extraction if no barcode match is found.

    Args:
        barcode_scanner_factory: Callable returning a scanner with scan_and_match()
        vision_extractor_path: Dotted import path for vision extractor class
        beverage_label: "wine" or "whisky" — used for response keys
        resolve_extracted_fks: Optional callback(data) to resolve FK fields in-place
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
        barcode_scanner = barcode_scanner_factory()
        barcode_result = barcode_scanner.scan_and_match(images, request.user)

        if barcode_result.get("matched"):
            # Beverage-specific keys: "wines"/"wine_data" or "whiskies"/"whisky_data"
            plural_key = (
                f"{beverage_label}s" if beverage_label != "whisky" else "whiskies"
            )
            data_key = f"{beverage_label}_data"

            if barcode_result.get("multiple_matches"):
                return JsonResponse(
                    {
                        "success": True,
                        "multiple_matches": True,
                        "match_type": "barcode",
                        "matched_barcode": barcode_result["barcode"],
                        plural_key: barcode_result[plural_key],
                        "message": f"Multiple {plural_key} found with this barcode",
                    }
                )

            beverage_data = barcode_result[data_key]
            extracted_fields = list(beverage_data.keys())

            return JsonResponse(
                {
                    "success": True,
                    "data": beverage_data,
                    "confidence": "high",
                    "extracted_fields": extracted_fields,
                    "errors": [],
                    "match_type": "barcode",
                    "matched_barcode": barcode_result["barcode"],
                    "message": (
                        f"Matched {beverage_label} via barcode: "
                        f"{barcode_result['barcode']}"
                    ),
                }
            )

        # Step 2: No barcode match, use AI vision extraction
        from importlib import import_module

        module_path, class_name = vision_extractor_path.rsplit(".", 1)
        module = import_module(module_path)
        extractor_cls = getattr(module, class_name)
        extractor = extractor_cls()
        result = extractor.extract_from_images(images, user=request.user)

        data = result.get("data", {})

        # Resolve FK fields if callback provided (e.g. whisky distillery/region/bottler)
        if resolve_extracted_fks:
            resolve_extracted_fks(data)

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
        logger.exception("Error in %s AJAX vision extraction", beverage_label)
        return JsonResponse({"error": "Vision extraction failed"}, status=500)


# --- Label scan view ---


class BaseLabelScanView(RequireHouseholdMixin, TemplateView):
    """Base view for label scanning via camera capture or file upload."""

    add_url_name = None  # e.g. "wine-add" or "whisky-add"

    def _handle_camera_capture(self, request):
        """Handle multi-image camera capture POST data. Returns redirect or None."""
        import base64

        image_count = request.POST.get("image_count")
        if not image_count:
            return None

        images = []
        for i in range(int(image_count)):
            image_data = request.POST.get(f"image_data_{i}")
            if image_data:
                if "," in image_data:
                    image_data = image_data.split(",")[1]
                images.append(image_data)

        if not images:
            return None

        request.session["scanned_label"] = {
            "filename": "camera_captures.jpg",
            "size": sum(len(base64.b64decode(img)) for img in images),
            "data": images,
            "multi_image": True,
        }
        return redirect(self.add_url_name)

    def _handle_file_uploads(self, request):
        """Handle file uploads from request.FILES. Returns redirect or None."""
        import base64

        images = []
        for field_name in ["barcode_image", "front_image", "back_image"]:
            image = request.FILES.get(field_name)
            if image:
                image_data = image.read()
                base64_image = base64.b64encode(image_data).decode("utf-8")
                images.append(base64_image)

        if not images:
            return None

        request.session["scanned_label"] = {
            "filename": "uploaded_images",
            "size": sum(len(base64.b64decode(img)) for img in images),
            "data": images,
            "multi_image": len(images) > 1,
        }
        return redirect(self.add_url_name)

    def post(self, request, *args, **kwargs):
        if "extraction_result" in request.session:
            del request.session["extraction_result"]

        result = self._handle_camera_capture(request)
        if result:
            return result

        result = self._handle_file_uploads(request)
        if result:
            return result

        return self.get(request, *args, **kwargs)


# --- Home page view ---


class BaseHomePageView(RequireHouseholdMixin, TemplateView):
    """Base dashboard view with shared stats (value, stock, drinks, wishlist)."""

    beverage_model = None  # Set by subclass
    storage_item_model = None
    drink_record_model = None
    wishlist_model = None
    reminder_model = None
    beverage_fk_name = None  # "wine" or "whisky"
    beverage_price_path = None  # "wine__price" or "whisky__price"
    stock_reverse_path = None  # "wine__storageitem" or "whisky__whiskystorageitem"

    def get_app_specific_context(self, household, user):
        """Return app-specific context dict. Override per app."""
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        household = get_active_household(user)

        # Total value
        total_value = self.storage_item_model.objects.aggregate(
            total=Sum(
                Coalesce("price", self.beverage_price_path),
                filter=Q(deleted=False, household=household),
            )
        )["total"] or Decimal("0")
        total_value = total_value.quantize(Decimal("0"))
        user_settings = get_user_settings(user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )
        formatted_price = number_format(total_value, use_l10n=True)

        # Bottles in stock
        bottles_in_stock = self.storage_item_model.objects.filter(
            household=household, deleted=False
        ).count()

        # Low stock reminders
        low_stock_count = (
            self.reminder_model.objects.filter(household=household, is_active=True)
            .annotate(
                current_stock=Count(
                    self.stock_reverse_path,
                    filter=Q(**{f"{self.stock_reverse_path}__deleted": False}),
                )
            )
            .filter(current_stock__lte=F("min_stock"))
            .count()
        )

        # Recent drinks
        recent_drinks = (
            self.drink_record_model.objects.filter(household=household)
            .select_related(self.beverage_fk_name)
            .order_by("-date_consumed")[:3]
        )

        # Wishlist
        wishlist_items = self.wishlist_model.objects.filter(
            household=household, purchased=False
        ).order_by("-priority")[:3]

        # Drink stats
        drink_stats = self.drink_record_model.objects.filter(
            household=household
        ).aggregate(
            total_consumed=Count("id"),
            avg_rating=Avg("rating", filter=Q(rating__isnull=False)),
        )
        total_consumed = drink_stats["total_consumed"]
        avg_rating = (
            round(drink_stats["avg_rating"], 1) if drink_stats["avg_rating"] else None
        )

        context.update(
            {
                "total_value": f"{currency}{formatted_price}",
                "bottles_in_stock": bottles_in_stock,
                "total_bottles": bottles_in_stock,
                "low_stock_count": low_stock_count,
                "recent_drinks": recent_drinks,
                "wishlist_items": wishlist_items,
                "total_consumed": total_consumed,
                "avg_rating": avg_rating,
            }
        )

        # App-specific context
        context.update(self.get_app_specific_context(household, user))

        return context


# --- Merge confirm view ---


class BaseMergeConfirmView(RequireMemberMixin, TemplateView):
    """Base view for merging duplicate beverages.

    Subclasses must set:
        beverage_model, storage_item_model, beverage_fk_name, detail_url_name,
        image_model, m2m_fields, related_models, reminder_model
    """

    beverage_model = None
    storage_item_model = None
    beverage_fk_name = None  # "wine" or "whisky"
    detail_url_name = None  # e.g. "wine-detail" or "whisky-detail"
    image_model = None
    m2m_fields = ()  # M2M field names to merge, e.g. ("grapes", "attributes")
    related_models = ()  # (Model, fk_field) tuples for FK reassignment
    reminder_model = None

    def get_beverages(self):
        household = get_active_household(self.request.user)
        qs = self.beverage_model.objects.filter(household=household)
        primary = get_object_or_404(qs, pk=self.kwargs["primary_pk"])
        duplicate = get_object_or_404(qs, pk=self.kwargs["pk"])
        return primary, duplicate

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        primary, duplicate = self.get_beverages()
        dup_stock = self.storage_item_model.objects.filter(
            **{self.beverage_fk_name: duplicate}, deleted=False
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
        primary, duplicate = self.get_beverages()

        with transaction.atomic():
            # Move bottles
            self.storage_item_model.objects.filter(
                **{self.beverage_fk_name: duplicate}
            ).update(**{self.beverage_fk_name: primary})

            # Move barcodes (skip duplicates)
            for barcode in duplicate.barcodes.all():
                if not primary.barcodes.filter(barcode=barcode.barcode).exists():
                    setattr(barcode, self.beverage_fk_name, primary)
                    barcode.save()

            # Move images
            self.image_model.objects.filter(
                **{self.beverage_fk_name: duplicate}
            ).update(**{self.beverage_fk_name: primary})

            # Merge M2M fields
            for field_name in self.m2m_fields:
                getattr(primary, field_name).add(*getattr(duplicate, field_name).all())

            # Move FK references
            for model, fk_field in self.related_models:
                model.objects.filter(**{fk_field: duplicate}).update(
                    **{fk_field: primary}
                )

            # Handle ReorderReminder (unique on beverage+user)
            for reminder in self.reminder_model.objects.filter(
                **{self.beverage_fk_name: duplicate}
            ):
                if not self.reminder_model.objects.filter(
                    **{self.beverage_fk_name: primary}, user=reminder.user
                ).exists():
                    setattr(reminder, self.beverage_fk_name, primary)
                    reminder.save()
                else:
                    reminder.delete()

            # Delete the duplicate
            duplicate.delete()

        messages.success(
            request,
            f'Merged "{duplicate.name}" into "{primary.name}".',
        )
        return redirect(self.detail_url_name, pk=primary.pk)

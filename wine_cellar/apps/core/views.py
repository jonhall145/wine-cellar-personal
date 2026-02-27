import json
import logging
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DeleteView, DetailView, FormView, TemplateView

from wine_cellar.apps.household.mixins import RequireHouseholdMixin, RequireMemberMixin
from wine_cellar.apps.user.views import get_active_household, get_user_settings

logger = logging.getLogger(__name__)

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

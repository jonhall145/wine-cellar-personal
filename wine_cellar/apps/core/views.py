import io
import json
import logging
from collections import defaultdict
from decimal import Decimal

import qrcode
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.forms import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.formats import number_format
from django.views.generic import DeleteView, DetailView, FormView, TemplateView, View

from wine_cellar.apps.core.audit import log_create, log_delete, log_update
from wine_cellar.apps.household.mixins import RequireHouseholdMixin, RequireMemberMixin
from wine_cellar.apps.storage.models import Storage, get_app_type
from wine_cellar.apps.user.views import get_active_household, get_user_settings

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB in bytes


def _parse_taste_descriptors(descriptors_str):
    """Parse JSON taste descriptors from form input. Returns a list or []."""
    if not descriptors_str:
        return []
    try:
        descriptors = json.loads(descriptors_str)
        return descriptors if isinstance(descriptors, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _has_selected_taste_descriptors(descriptors):
    """Return whether the form currently has any selected taste descriptors."""
    if isinstance(descriptors, list):
        return bool(descriptors)
    return bool(_parse_taste_descriptors(descriptors))


# --- Wishlist views ---


class BaseWishlistListView(RequireHouseholdMixin, TemplateView):
    wishlist_model = None  # Set by subclass
    wishlist_columns_header = None  # Template path for column headers
    wishlist_columns_row = None  # Template path for column cells
    wishlist_convert_url_name = None  # Beverage create route for wishlist conversion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["wishlist_items"] = self.wishlist_model.objects.filter(
            household=household, purchased=False
        )
        context["wishlist_columns_header"] = self.wishlist_columns_header
        context["wishlist_columns_row"] = self.wishlist_columns_row
        context["wishlist_convert_url_name"] = self.wishlist_convert_url_name
        return context


class BaseWishlistDeleteView(RequireMemberMixin, DeleteView):
    success_url = reverse_lazy("wishlist-list")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return self.model.objects.filter(household=household)


class BaseWishlistPurchasedView(RequireMemberMixin, TemplateView):
    """Mark a wishlist item as purchased."""

    wishlist_model = None  # Set by subclass

    def post(self, request, *args, **kwargs):
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
    beverage_icon = None  # e.g. "wine-glass" or "whiskey-glass"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        context["drink_records"] = self.drink_record_model.objects.filter(
            household=household
        ).select_related(
            self.beverage_fk_name,
            "storage_item",
            "storage_item__storage",
        )
        context["beverage_fk_name"] = self.beverage_fk_name
        context["beverage_icon"] = self.beverage_icon or "wine-glass"
        return context


class BaseJourneyTimelineView(RequireHouseholdMixin, TemplateView):
    storage_item_model = None  # Set by subclass
    drink_record_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    beverage_icon = None  # e.g. "wine-glass" or "whiskey-glass"
    max_timeline_events = 200

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        user_settings = get_user_settings(self.request.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )

        storage_items = list(
            self.storage_item_model.objects.filter(household=household, deleted=False)
            .select_related(self.beverage_fk_name)
            .only(
                "created",
                "price",
                "household_id",
                f"{self.beverage_fk_name}__name",
                f"{self.beverage_fk_name}__price",
                f"{self.beverage_fk_name}__id",
            )
            .order_by("created", "pk")
        )
        drink_records = list(
            self.drink_record_model.objects.filter(household=household)
            .select_related(self.beverage_fk_name)
            .only(
                "date_consumed",
                "rating",
                "tasting_notes",
                "household_id",
                f"{self.beverage_fk_name}__name",
                f"{self.beverage_fk_name}__id",
            )
            .order_by("date_consumed", "pk")
        )

        timeline_events = []
        for item in storage_items:
            beverage = getattr(item, self.beverage_fk_name)
            timeline_events.append(
                {
                    "date": item.created.date(),
                    "event_type": "added",
                    "beverage": beverage,
                    "price": item.price if item.price is not None else beverage.price,
                }
            )

        for record in drink_records:
            timeline_events.append(
                {
                    "date": record.date_consumed,
                    "event_type": "consumed",
                    "beverage": getattr(record, self.beverage_fk_name),
                    "rating": record.rating,
                    "tasting_notes": record.tasting_notes,
                }
            )

        # Milestone: 100th bottle ever added (including deleted)
        hundredth_item = (
            self.storage_item_model.objects.filter(household=household)
            .select_related(self.beverage_fk_name)
            .order_by("created", "pk")[99:100]
            .first()
        )
        if hundredth_item:
            timeline_events.append(
                {
                    "date": hundredth_item.created.date(),
                    "event_type": "milestone",
                    "milestone_type": "hundredth_bottle",
                    "beverage": getattr(hundredth_item, self.beverage_fk_name),
                }
            )

        first_three_star = next(
            (record for record in drink_records if record.rating == 3), None
        )
        if first_three_star:
            timeline_events.append(
                {
                    "date": first_three_star.date_consumed,
                    "event_type": "milestone",
                    "milestone_type": "first_three_star",
                    "beverage": getattr(first_three_star, self.beverage_fk_name),
                }
            )

        timeline_events = sorted(
            timeline_events,
            key=lambda event: event["date"],
            reverse=True,
        )[: self.max_timeline_events]

        monthly_consumption = (
            self.drink_record_model.objects.filter(household=household)
            .annotate(month=TruncMonth("date_consumed"))
            .values("month")
            .annotate(total=Count("id"))
            .order_by("-month")[:12]
        )
        yearly_consumption = (
            self.drink_record_model.objects.filter(household=household)
            .values("date_consumed__year")
            .annotate(total=Count("id"))
            .order_by("-date_consumed__year")
        )
        price_trends = (
            self.storage_item_model.objects.filter(household=household, deleted=False)
            .annotate(month=TruncMonth("created"))
            .values("month")
            .annotate(
                purchases=Count("id"),
                avg_price=Avg(Coalesce("price", F(f"{self.beverage_fk_name}__price"))),
            )
            .order_by("-month")[:12]
        )

        context.update(
            {
                "timeline_events": timeline_events,
                "monthly_consumption": monthly_consumption,
                "yearly_consumption": yearly_consumption,
                "price_trends": price_trends,
                "currency": currency,
                "beverage_icon": self.beverage_icon or "wine-glass",
            }
        )
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
            "photo": record.photo,
            "taste_descriptors": json.dumps(record.taste_descriptors),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.get_object()
        form = context.get("form")
        context["record"] = record
        beverage = getattr(record, self.beverage_fk_name)
        context[self.beverage_fk_name] = beverage
        context["beverage"] = beverage
        context["show_taste_descriptors"] = bool(
            form
            and "taste_descriptors" in form.fields
            and _has_selected_taste_descriptors(form["taste_descriptors"].value())
        )
        return context

    def form_valid(self, form):
        record = self.get_object()
        record.date_consumed = form.cleaned_data["date_consumed"]
        record.tasting_notes = form.cleaned_data.get("tasting_notes")
        record.rating = form.cleaned_data.get("rating")
        record.shared_with = form.cleaned_data.get("shared_with")
        record.occasion = form.cleaned_data.get("occasion")
        record.taste_descriptors = _parse_taste_descriptors(
            form.cleaned_data.get("taste_descriptors")
        )
        if form.cleaned_data.get("photo"):
            record.photo = form.cleaned_data["photo"]
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
        storage_item = get_object_or_404(
            self.storage_item_model, pk=self.kwargs["pk"], household=household
        )
        context["storage_item"] = storage_item
        context["beverage"] = getattr(storage_item, self.beverage_fk_name)
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
    beverage_icon = None  # e.g. "wine-bottle" or "whiskey-glass"
    reminder_service = None

    def get_reminder_context(self, household):
        if self.reminder_service:
            return self.reminder_service.get_reorder_context(household)

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
        needs_reorder = [
            {
                self.beverage_fk_name: getattr(reminder, self.beverage_fk_name),
                "current_stock": reminder.current_stock,
                "min_stock": reminder.min_stock,
                "reminder": reminder,
            }
            for reminder in reminders
            if reminder.current_stock <= reminder.min_stock
        ]
        return reminders, needs_reorder

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        reminders, needs_reorder = self.get_reminder_context(household)
        context.update(
            {
                "reminders": reminders,
                "needs_reorder": needs_reorder,
                "beverage_fk_name": self.beverage_fk_name,
                "beverage_icon": self.beverage_icon or "wine-bottle",
            }
        )
        return context


class BaseReorderReminderCreateView(RequireMemberMixin, FormView):
    beverage_model = None  # Set by subclass
    reminder_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    detail_url_name = None  # e.g. "wine-detail" or "whisky-detail"
    reminder_service = None

    def get_form_class(self):
        from wine_cellar.apps.core.forms import ReorderReminderForm

        return ReorderReminderForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model, pk=self.kwargs["pk"], household=household
        )
        context[self.beverage_fk_name] = beverage
        context["beverage"] = beverage
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model, pk=self.kwargs["pk"], household=household
        )
        self.save_reorder_reminder(
            beverage=beverage,
            household=household,
            min_stock=form.cleaned_data["min_stock"],
        )
        self.success_url = reverse_lazy(
            self.detail_url_name, kwargs={"pk": beverage.pk}
        )
        return super().form_valid(form)

    def save_reorder_reminder(self, *, beverage, household, min_stock):
        if self.reminder_service:
            return self.reminder_service.save_reorder_reminder(
                **{self.beverage_fk_name: beverage},
                user=self.request.user,
                household=household,
                min_stock=min_stock,
            )

        return self.reminder_model.objects.update_or_create(
            **{self.beverage_fk_name: beverage},
            user=self.request.user,
            household=household,
            defaults={"min_stock": min_stock, "is_active": True},
        )


# --- Drink record create view ---


class BaseDrinkRecordCreateView(RequireMemberMixin, FormView):
    beverage_model = None  # Set by subclass
    drink_record_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    detail_url_name = None  # e.g. "wine-detail" or "whisky-detail"

    def get_initial(self):
        initial = super().get_initial()
        storage_item_pk = self.request.GET.get("storage_item")
        if storage_item_pk:
            try:
                initial["storage_item"] = int(storage_item_pk)
            except (TypeError, ValueError):
                pass
        return initial

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
        beverage = get_object_or_404(
            self.beverage_model, pk=self.kwargs["pk"], household=household
        )
        context[self.beverage_fk_name] = beverage
        context["beverage"] = beverage
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
            photo=form.cleaned_data.get("photo"),
            taste_descriptors=_parse_taste_descriptors(
                form.cleaned_data.get("taste_descriptors")
            ),
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
        storage_item.finished_date = (
            form.cleaned_data.get("date_consumed") or timezone.localdate()
        )
        storage_item.removal_reason = storage_item.RemovalReason.CONSUMED
        storage_item.given_date = None
        storage_item.recipient = ""
        storage_item.given_occasion = ""
        storage_item.save(
            update_fields=[
                "deleted",
                "finished_date",
                "removal_reason",
                "given_date",
                "recipient",
                "given_occasion",
            ]
        )


class BaseBottleQuickLogView(RequireMemberMixin, View):
    storage_item_model = None
    drink_record_model = None
    beverage_fk_name = None  # "wine" or "whisky"

    def get_object(self):
        household = get_active_household(self.request.user)
        return get_object_or_404(
            self.storage_item_model,
            pk=self.kwargs["pk"],
            household=household,
            deleted=False,
        )

    def get_locked_object(self):
        household = get_active_household(self.request.user)
        queryset = self.storage_item_model.objects.select_for_update().select_related(
            self.beverage_fk_name
        )
        return get_object_or_404(
            queryset,
            pk=self.kwargs["pk"],
            household=household,
            deleted=False,
        )

    def post(self, request, *args, **kwargs):
        household = get_active_household(request.user)
        date_consumed = timezone.localdate()

        with transaction.atomic():
            storage_item = self.get_locked_object()
            beverage = getattr(storage_item, self.beverage_fk_name)
            self.drink_record_model.objects.create(
                **{self.beverage_fk_name: beverage},
                user=request.user,
                household=household,
                date_consumed=date_consumed,
                storage_item=storage_item,
            )
            self.handle_bottle_update(storage_item, date_consumed)

        messages.success(request, "Drink logged.")
        return redirect("bottle-history", pk=storage_item.pk)

    def handle_bottle_update(self, storage_item, date_consumed):
        raise NotImplementedError


class BaseMarkBottleGivenView(RequireMemberMixin, FormView):
    template_name = "core/bottle_mark_given.html"
    storage_item_model = None
    beverage_fk_name = None
    detail_url_name = None
    list_url_name = None

    def get_form_class(self):
        from wine_cellar.apps.core.forms import MarkBottleGivenForm

        return MarkBottleGivenForm

    def get_object(self):
        household = get_active_household(self.request.user)
        return get_object_or_404(
            self.storage_item_model,
            pk=self.kwargs["pk"],
            household=household,
            deleted=False,
        )

    def get_success_url(self):
        if self.request.GET.get("next") == "list" and self.list_url_name:
            return reverse_lazy(self.list_url_name)
        storage_item = getattr(self, "object", None) or self.get_object()
        beverage = getattr(storage_item, self.beverage_fk_name)
        return reverse_lazy(self.detail_url_name, kwargs={"pk": beverage.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        storage_item = self.get_object()
        beverage = getattr(storage_item, self.beverage_fk_name)
        context["storage_item"] = storage_item
        context["beverage"] = beverage
        context[self.beverage_fk_name] = beverage
        context["cancel_url"] = self.get_success_url()
        return context

    def form_valid(self, form):
        storage_item = self.get_object()
        self.object = storage_item
        storage_item.deleted = True
        storage_item.removal_reason = storage_item.RemovalReason.GIVEN
        storage_item.recipient = form.cleaned_data["recipient"]
        storage_item.given_date = form.cleaned_data["given_date"]
        storage_item.given_occasion = form.cleaned_data.get("given_occasion", "")
        storage_item.finished_date = None
        storage_item.save(
            update_fields=[
                "deleted",
                "removal_reason",
                "recipient",
                "given_date",
                "given_occasion",
                "finished_date",
            ]
        )
        return redirect(self.get_success_url())


class BaseMarkBottleBrokenOrLostView(RequireMemberMixin, TemplateView):
    template_name = "core/bottle_mark_broken_lost.html"
    storage_item_model = None
    beverage_fk_name = None
    detail_url_name = None
    list_url_name = None
    storage_detail_url_name = None

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        household = get_active_household(self.request.user)
        return get_object_or_404(
            self.storage_item_model,
            pk=self.kwargs["pk"],
            household=household,
            deleted=False,
        )

    def get_success_url(self):
        next_view = self.request.GET.get("next")
        if next_view == "list" and self.list_url_name:
            return reverse_lazy(self.list_url_name)
        if next_view == "storage" and self.storage_detail_url_name:
            return reverse_lazy(
                self.storage_detail_url_name, kwargs={"pk": self.object.storage.pk}
            )
        beverage = getattr(self.object, self.beverage_fk_name)
        return reverse_lazy(self.detail_url_name, kwargs={"pk": beverage.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        beverage = getattr(self.object, self.beverage_fk_name)
        context["storage_item"] = self.object
        context["beverage"] = beverage
        context[self.beverage_fk_name] = beverage
        context["cancel_url"] = self.get_success_url()
        return context

    def post(self, request, *args, **kwargs):
        self.object.deleted = True
        self.object.finished_date = timezone.localdate()
        self.object.removal_reason = self.object.RemovalReason.REMOVED
        self.object.given_date = None
        self.object.recipient = ""
        self.object.given_occasion = ""
        self.object.save(
            update_fields=[
                "deleted",
                "finished_date",
                "removal_reason",
                "given_date",
                "recipient",
                "given_occasion",
            ]
        )
        return redirect(self.get_success_url())


class BaseReorderReminderDeleteView(RequireMemberMixin, DeleteView):
    success_url = reverse_lazy("notifications")

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return self.model.objects.filter(household=household)


# --- Cellar value view ---


class BaseCellarValueView(RequireHouseholdMixin, TemplateView):
    storage_item_model = None  # Set by subclass
    price_fallback_path = None  # e.g. "wine__price" or "whisky__price"
    beverage_fk_name = None  # "wine" or "whisky"
    select_related_fields = ()  # e.g. ("wine",) or ("whisky__distillery",)
    group_label = None  # e.g. "Country" or "Distillery"

    def get_groupings(self, item):
        """Return {context_key: group_name} dict for this item.

        Subclasses must implement. Example return:
            {"by_group": "France", "by_type": "Red"}
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
                "group_label": self.group_label,
                **groups,
            }
        )
        return context


# --- Beverage delete view ---


class BaseBeverageDeleteView(RequireMemberMixin, DeleteView):
    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return qs.filter(household=household, deleted=False)

    def form_valid(self, form):
        log_delete(self.request.user, self.object)
        self.object.deleted = True
        self.object.save(update_fields=["deleted"])
        return redirect(self.get_success_url())


# --- Images view ---


class BaseImagesView(RequireHouseholdMixin, DetailView):
    """View for managing beverage images (set primary, crop)."""

    images_prefetch_name = None  # e.g. "wineimage_set" or "images"
    image_api_prefix = None  # e.g. "/wine/image" or "/whisky/image"

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return self.model.objects.filter(household=household).prefetch_related(
            self.images_prefetch_name
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        beverage = self.object
        context["beverage"] = beverage
        context["images"] = getattr(beverage, self.images_prefetch_name).all()
        if self.image_api_prefix:
            context["image_api_prefix"] = self.image_api_prefix
        return context


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
    card_template = None  # e.g. "wine_card.html"
    filter_field_template = None  # e.g. "wine_filter_field.html"
    beverage_icon = None  # e.g. "wine-glass"
    default_filter_data = {}

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
        context["beverages"] = context.get("object_list", [])
        context["card_template"] = self.card_template
        context["filter_field_template"] = self.filter_field_template
        context["beverage_icon"] = self.beverage_icon
        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        if not self.default_filter_data:
            return kwargs
        data = kwargs.get("data")
        if data is None:
            data = self.request.GET.copy()
        else:
            data = data.copy()
        missing_keys = [key for key in self.default_filter_data if key not in data]
        for key in missing_keys:
            data[key] = self.default_filter_data[key]
        kwargs["data"] = data
        return kwargs

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
        return qs.filter(household=household, deleted=False).distinct()


# --- Detail view ---


class BaseDetailView(RequireHouseholdMixin, DetailView):
    """Base detail view with household filtering and duplicate detection."""

    select_related_fields = ()
    prefetch_related_fields = ()
    storage_item_reverse = None  # e.g. "storageitem" or "whiskystorageitem"
    extraction_log_model = None
    extraction_log_fk_name = None

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
            .filter(household=household, deleted=False)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        beverage = self.object
        context["beverage"] = beverage
        household = get_active_household(self.request.user)
        duplicates = (
            self.model.objects.filter(
                household=household, name=beverage.name, deleted=False
            )
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
        extraction_log = self.get_extraction_log(beverage)
        if extraction_log:
            context["extraction_log"] = extraction_log

        # Track recently viewed beverages in session
        _track_recent_view(self.request, beverage)

        return context

    def get_extraction_log(self, beverage):
        if not self.extraction_log_model or not self.extraction_log_fk_name:
            return None

        return (
            self.extraction_log_model.objects.filter(
                **{self.extraction_log_fk_name: beverage, "was_successful": True}
            )
            .order_by("-created")
            .first()
        )


MAX_RECENT_VIEWS = 8


def _track_recent_view(request, beverage):
    """Store recently viewed beverage IDs in the session."""
    key = "recent_views"
    recent = request.session.get(key, [])
    entry = {"pk": beverage.pk, "name": str(beverage.name)}
    # Remove existing entry for this beverage
    recent = [r for r in recent if r["pk"] != beverage.pk]
    # Prepend new entry
    recent.insert(0, entry)
    # Limit to MAX_RECENT_VIEWS
    request.session[key] = recent[:MAX_RECENT_VIEWS]


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
    group_label = None  # e.g. "Country" or "Distillery"

    def get_secondary_stats(self, records):
        """Return app-specific groupings as {context_key: dict}.

        Subclasses must implement. Example return:
            {"by_group": {"France": 5, "Italy": 3}}
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
                "group_label": self.group_label,
                "beverage_fk_name": self.beverage_fk_name,
                **self.get_secondary_stats(records),
            }
        )
        return context

    def get_type_display(self, beverage):
        """Return display string for the beverage type. Override per app."""
        raise NotImplementedError


# --- Stats dashboard view ---


class BaseStatsDashboardView(RequireHouseholdMixin, TemplateView):
    """Dedicated statistics dashboard showing cellar-level charts and trends."""

    storage_item_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    price_fallback_path = None  # e.g. "wine__price" or "whisky__price"
    select_related_fields = ()  # for storage items

    def get_type_display(self, beverage):
        """Return display string for the beverage type. Override per app."""
        raise NotImplementedError

    def get_country_name(self, beverage):
        """Return country display name for the beverage. Override per app."""
        raise NotImplementedError

    def get_item_price(self, item, beverage):
        """Return the best available purchase price for a stored bottle."""
        if item.price is not None:
            return item.price
        if beverage.price is not None:
            return beverage.price
        return Decimal("0")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        user_settings = get_user_settings(self.request.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )

        all_items_qs = self.storage_item_model.objects.filter(
            household=household
        ).select_related(*self.select_related_fields, "storage")

        # --- By type (count in stock) ---
        by_type = defaultdict(int)
        # --- By country (count in stock) ---
        by_country = defaultdict(int)
        # --- Value by storage location ---
        by_storage = {}
        spend_by_month = defaultdict(lambda: Decimal("0"))
        spend_by_year = defaultdict(lambda: Decimal("0"))

        # --- Rating distribution ---
        by_rating = {0: 0, 1: 0, 2: 0, 3: 0}

        # Single consolidated iteration over all items. Spending trends include
        # deleted bottles to reflect purchase history.
        for item in all_items_qs:
            beverage = getattr(item, self.beverage_fk_name)

            # In-stock aggregates (skip deleted items)
            if not item.deleted:
                by_type[self.get_type_display(beverage)] += 1
                by_country[self.get_country_name(beverage)] += 1

                storage_name = item.storage.name if item.storage else "Unknown"
                if storage_name not in by_storage:
                    by_storage[storage_name] = {"count": 0, "value": Decimal("0")}
                by_storage[storage_name]["count"] += 1
                item_price = self.get_item_price(item, beverage)
                by_storage[storage_name]["value"] += item_price

                # Rating distribution (in-stock items only)
                if hasattr(beverage, "rating") and beverage.rating is not None:
                    by_rating[beverage.rating] += 1

            # Spending trends (all items including deleted, for true purchase history)
            item_price = self.get_item_price(item, beverage)
            item_date = timezone.localtime(item.created).date()
            spend_by_month[item_date.replace(day=1)] += item_price
            spend_by_year[item_date.year] += item_price

        for data in by_storage.values():
            data["value"] = int(data["value"])

        # Sort by count descending
        by_type = dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True))
        by_country = dict(sorted(by_country.items(), key=lambda x: x[1], reverse=True))
        by_storage = dict(
            sorted(by_storage.items(), key=lambda x: x[1]["value"], reverse=True)
        )

        # Purchase trends (all bottles ever added, including consumed).
        # Includes deleted items so the chart reflects true purchase history.
        by_month = (
            self.storage_item_model.objects.filter(household=household)
            .annotate(month=TruncMonth("created"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        spend_by_month = [
            {"month": month, "amount": amount.quantize(Decimal("0.01"))}
            for month, amount in sorted(spend_by_month.items())
        ]
        spend_by_year = [
            {"year": year, "amount": amount.quantize(Decimal("0.01"))}
            for year, amount in sorted(spend_by_year.items())
        ]

        context.update(
            {
                "by_type": by_type,
                "by_country": by_country,
                "by_storage": by_storage,
                "by_month": list(by_month),
                "spend_by_month": spend_by_month,
                "spend_by_year": spend_by_year,
                "by_rating": by_rating,
                "currency": currency,
                "total_in_stock": sum(by_type.values()),
            }
        )
        return context


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
            external_url=form.cleaned_data.get("external_url", ""),
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

    def get_form_image_config(self):
        form_class = self.get_form_class()
        return (
            getattr(form_class, "image_model", None),
            getattr(form_class, "image_fields_map", {}),
            getattr(form_class, "beverage_fk_name", None),
        )

    def sync_form_images(self, beverage, user, cleaned_data):
        image_model, image_fields_map, beverage_fk_name = self.get_form_image_config()
        if not image_model or not beverage_fk_name:
            return

        for field_name, image_type in image_fields_map.items():
            image = cleaned_data.get(field_name)
            existing_image = image_model.objects.filter(
                **{
                    beverage_fk_name: beverage,
                    "user": user,
                    "image_type": image_type,
                }
            ).first()

            if image is False:
                if existing_image:
                    existing_image.image.delete()
                    existing_image.delete()
                continue

            if image and not hasattr(image, "instance"):
                if existing_image:
                    existing_image.image.delete()
                    existing_image.delete()
                image_model.objects.create(
                    **{
                        beverage_fk_name: beverage,
                        "image": image,
                        "user": user,
                        "image_type": image_type,
                    }
                )

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
        context["beverage"] = beverage
        context["beverage_images"] = getattr(beverage, self.image_related_name).all()
        # Keep legacy key for backward compat with app-specific templates
        context[f"{self.beverage_fk_name}_images"] = context["beverage_images"]
        return context

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        beverage = get_object_or_404(
            self.beverage_model,
            pk=self.kwargs["pk"],
            household=household,
        )
        with transaction.atomic():
            self.process_form_data(beverage, self.request.user, form.cleaned_data)
            self.sync_form_images(beverage, self.request.user, form.cleaned_data)
            log_update(self.request.user, beverage)
            self.post_save_beverage(beverage)
        self.success_url = reverse_lazy(
            self.detail_url_name, kwargs={"pk": beverage.pk}
        )
        return super().form_valid(form)

    def process_form_data(self, beverage, user, cleaned_data):
        raise NotImplementedError

    def post_save_beverage(self, beverage):
        """Hook for post-save processing. Override per app."""
        pass


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
    page_title = None
    scan_url_name = None
    rescan_url_name = None
    duplicate_check_url_name = None
    extract_vision_url_name = None
    quick_add_description = None
    image_autofill_hint = None
    image_extract_hint = None
    scanned_label_alt = None
    save_button_label = None
    field_section_definitions = ()
    cellar_extra_field_names = ()
    confidence_badge_labels = None
    vision_field_map = {}
    vision_confidence_field_map = {}
    vision_create_fields = ()
    vision_fk_name_fields = {}
    extraction_log_model = None
    extraction_log_fk_name = None
    wishlist_model = None  # Set by subclass
    wishlist_initial_field_map = {}

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
                    "field_confidence": result.get("field_confidence", {}),
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
                result_data = dict(result_data)
                self.resolve_extracted_data(result_data, initial)
                initial.update(result_data)

        self.apply_wishlist_values(initial, overwrite=True, serialize_related=True)
        return initial

    def get_wishlist_item(self):
        if hasattr(self, "_wishlist_item_cache"):
            return self._wishlist_item_cache

        if not self.wishlist_model:
            self._wishlist_item_cache = None
            return self._wishlist_item_cache

        wishlist_item_id = self.request.GET.get(
            "wishlist_item"
        ) or self.request.POST.get("wishlist_item")
        if not wishlist_item_id:
            self._wishlist_item_cache = None
            return self._wishlist_item_cache

        household = get_active_household(self.request.user)
        self._wishlist_item_cache = get_object_or_404(
            self.wishlist_model,
            pk=wishlist_item_id,
            household=household,
        )
        return self._wishlist_item_cache

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

    def _bind_form_fields(self, form, field_names):
        return [form[field_name] for field_name in field_names]

    def get_create_sections(self, form):
        return [
            {
                "title": section["title"],
                "fields": self._bind_form_fields(form, section["fields"]),
            }
            for section in self.field_section_definitions
        ]

    def get_vision_extraction_config(self):
        return {
            "endpointUrl": reverse(self.extract_vision_url_name),
            "beverageLabel": self.beverage_label,
            "fieldMap": self.vision_field_map,
            "confidenceFieldMap": self.vision_confidence_field_map,
            "createFields": list(self.vision_create_fields),
            "fkNameFields": self.vision_fk_name_fields,
        }

    def apply_wishlist_values(
        self, values, *, overwrite=False, serialize_related=False
    ):
        wishlist_item = self.get_wishlist_item()
        if not wishlist_item:
            return

        for form_field, wishlist_field in self.wishlist_initial_field_map.items():
            if not overwrite and values.get(form_field) not in (None, "", []):
                continue
            value = getattr(wishlist_item, wishlist_field)
            if value in (None, ""):
                continue
            if serialize_related and hasattr(value, "pk"):
                values[form_field] = value.pk
            else:
                values[form_field] = value

    def mark_wishlist_item_purchased(self, wishlist_item):
        if wishlist_item.purchased:
            return

        wishlist_item.purchased = True
        wishlist_item.save(update_fields=["purchased"])
        messages.success(
            self.request,
            f'Wishlist item "{wishlist_item.name}" marked as purchased.',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        household = get_active_household(self.request.user)
        wishlist_item = self.get_wishlist_item()
        user_storages = Storage.objects.filter(
            household=household, app_type=get_app_type()
        )
        free_cells_by_storage = {s.pk: s.get_free_cells_by_row() for s in user_storages}
        context["free_cells_by_storage"] = free_cells_by_storage
        context.update(
            {
                "create_page_title": self.page_title
                or f"Add {self.beverage_label.title()}",
                "beverage_label": self.beverage_label,
                "create_scan_url": reverse(self.scan_url_name),
                "create_scan_button_label": f"Scan {self.beverage_label.title()}",
                "create_rescan_url": reverse(self.rescan_url_name),
                "create_duplicate_check_url": reverse(self.duplicate_check_url_name),
                "create_quick_add_description": self.quick_add_description,
                "create_image_autofill_hint": self.image_autofill_hint,
                "create_image_extract_hint": self.image_extract_hint,
                "create_scanned_label_alt": self.scanned_label_alt,
                "create_save_button_label": self.save_button_label
                or f"Save {self.beverage_label.title()}",
                "create_form_sections": self.get_create_sections(form),
                "create_cellar_extra_fields": self._bind_form_fields(
                    form, self.cellar_extra_field_names
                ),
                "create_confidence_badges": self.confidence_badge_labels
                or {
                    "high": "High Confidence",
                    "medium": "Please Verify",
                    "low": "Low Confidence",
                },
                "vision_extraction_config": self.get_vision_extraction_config(),
                "wishlist_source_item": wishlist_item,
            }
        )

        extraction_result = self.request.session.get("extraction_result")
        if extraction_result:
            context["extraction_result"] = extraction_result
            context["scanned_image"] = extraction_result.get("scanned_image")
            context["extracted_fields"] = extraction_result.get("extracted_fields", [])
            context["confidence"] = extraction_result.get("confidence", "low")
            context["field_confidence"] = extraction_result.get("field_confidence", {})

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
        wishlist_item = self.get_wishlist_item()
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
        self.apply_wishlist_values(form.cleaned_data)
        with transaction.atomic():
            beverage, created = self.process_form_data(
                self.request.user, household, form.cleaned_data
            )
            self.create_form_images(beverage, self.request.user, form.cleaned_data)

            if created:
                log_create(self.request.user, beverage)

            self.post_create(beverage, created)
            if wishlist_item:
                self.mark_wishlist_item_purchased(wishlist_item)

            # Link extraction log to created beverage and record corrections
            extraction_result = self.request.session.get("extraction_result")
            if extraction_result and created:
                self._link_extraction_log(
                    beverage, form.cleaned_data, extraction_result
                )
            self.post_save_beverage(beverage)

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

        # Check if user wants to continue batch scanning
        if "save_scan_another" in self.request.POST:
            from django.contrib import messages

            messages.success(
                self.request,
                f"{self.beverage_label.title()} saved. Scan the next bottle.",
            )
            return redirect("label-scan")

        return super().form_valid(form)

    def process_form_data(self, user, household, cleaned_data):
        raise NotImplementedError

    def get_form_image_config(self):
        form_class = self.get_form_class()
        return (
            getattr(form_class, "image_model", None),
            getattr(form_class, "image_fields_map", {}),
            getattr(form_class, "beverage_fk_name", None),
        )

    def create_form_images(self, beverage, user, cleaned_data):
        image_model, image_fields_map, beverage_fk_name = self.get_form_image_config()
        if not image_model or not beverage_fk_name:
            return

        for field_name, image_type in image_fields_map.items():
            image = cleaned_data.get(field_name)
            if not image:
                continue

            image_model.objects.get_or_create(
                **{
                    beverage_fk_name: beverage,
                    "image": image,
                    "user": user,
                    "image_type": image_type,
                }
            )

    def post_create(self, beverage, created):
        """Hook for post-creation processing. Override per app."""
        pass

    def post_save_beverage(self, beverage):
        """Hook for post-save processing. Override per app."""
        pass

    def _link_extraction_log(self, beverage, cleaned_data, extraction_result):
        """Link the most recent extraction log to the created beverage
        and record any user corrections."""
        if not self.extraction_log_model or not self.extraction_log_fk_name:
            return

        try:
            log = (
                self.extraction_log_model.objects.filter(
                    **{
                        "user": self.request.user,
                        f"{self.extraction_log_fk_name}__isnull": True,
                    }
                )
                .order_by("-created")
                .first()
            )
            if log:
                extracted_data = extraction_result.get("extracted_data", {})
                corrections = self._detect_corrections(cleaned_data, extracted_data)
                setattr(log, self.extraction_log_fk_name, beverage)
                log.was_successful = True
                if corrections:
                    log.user_corrections = corrections
                log.save(
                    update_fields=[
                        self.extraction_log_fk_name,
                        "was_successful",
                        "user_corrections",
                    ]
                )
        except Exception:
            logger.exception(
                "Failed to link extraction log to %s %s",
                self.beverage_label,
                beverage.pk,
            )

    @staticmethod
    def _detect_corrections(cleaned_data, extracted_data):
        """Compare submitted form data with extracted data to find corrections."""
        corrections = {}
        for field, extracted_val in extracted_data.items():
            if field in (
                "label_bounds_front",
                "label_bounds_back",
                "appellation",
                "designation",
            ):
                continue
            submitted_val = cleaned_data.get(field)
            if submitted_val is None:
                continue
            # Normalize for comparison
            if hasattr(submitted_val, "pk"):
                submitted_val = submitted_val.pk
            elif hasattr(submitted_val, "__iter__") and not isinstance(
                submitted_val, str
            ):
                submitted_val = sorted(str(v) for v in submitted_val)
                extracted_val = (
                    sorted(str(v) for v in extracted_val)
                    if isinstance(extracted_val, list)
                    else [str(extracted_val)]
                )
            else:
                submitted_val = str(submitted_val)
                extracted_val = str(extracted_val)
            if submitted_val != extracted_val:
                corrections[field] = {
                    "extracted": (
                        extracted_val
                        if isinstance(extracted_val, (str, int, float, list))
                        else str(extracted_val)
                    ),
                    "submitted": (
                        submitted_val
                        if isinstance(submitted_val, (str, int, float, list))
                        else str(submitted_val)
                    ),
                }
        return corrections


class StorageItemFormLayoutMixin:
    extra_stock_field_names = ()

    def get_free_cells_by_storage(self, *, exclude_item=None):
        household = get_active_household(self.request.user)
        user_storages = Storage.objects.filter(
            household=household, app_type=get_app_type()
        )
        return {
            storage.pk: storage.get_free_cells_by_row(exclude_item=exclude_item)
            for storage in user_storages
        }

    def get_stock_extra_fields(self, form):
        return [form[field_name] for field_name in self.extra_stock_field_names]


class BaseStorageItemAddView(StorageItemFormLayoutMixin, RequireMemberMixin, FormView):
    beverage_model = None
    storage_item_model = None
    beverage_fk_name = None
    beverage_context_name = None
    beverage_label = None
    detail_url_name = None
    show_storage_suggestions = False

    def get_beverage(self):
        if not hasattr(self, "_beverage"):
            household = get_active_household(self.request.user)
            self._beverage = get_object_or_404(
                self.beverage_model, pk=self.kwargs["pk"], household=household
            )
        return self._beverage

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs.update(self.get_add_form_kwargs(self.get_beverage()))
        return kwargs

    def get_add_form_kwargs(self, beverage):
        return {}

    def get_initial(self):
        initial = super().get_initial()
        initial.update(self.get_add_initial(self.get_beverage()))
        return initial

    def get_add_initial(self, beverage):
        return {}

    def get_storage_suggestions(self):
        if not self.show_storage_suggestions:
            return []

        beverage = self.get_beverage()
        household = get_active_household(self.request.user)
        storage_related_name = self.storage_item_model._meta.get_field(
            "storage"
        ).remote_field.related_name
        storage_item_pk = f"{storage_related_name}__pk"
        beverage_filter = Q(
            **{
                f"{storage_related_name}__household": household,
                f"{storage_related_name}__deleted": False,
                f"{storage_related_name}__{self.beverage_fk_name}": beverage,
            }
        )
        used_slots_filter = Q(
            **{
                f"{storage_related_name}__household": household,
                f"{storage_related_name}__deleted": False,
            }
        )
        suggested_storages = (
            Storage.objects.filter(household=household, app_type=get_app_type())
            .annotate(
                bottle_count=Count(
                    storage_item_pk,
                    filter=beverage_filter,
                    distinct=True,
                ),
                occupied_slots=Count(
                    storage_item_pk,
                    filter=used_slots_filter,
                    distinct=True,
                ),
            )
            .filter(bottle_count__gt=0)
            .order_by("name", "pk")
        )

        suggestions = []
        for storage in suggested_storages:
            total_slots = storage.total_slots
            if total_slots == 0:
                free_slots = None
            else:
                free_slots = total_slots - storage.occupied_slots

            suggestions.append(
                {
                    "storage_id": storage.pk,
                    "storage_name": storage.name,
                    "bottle_count": storage.bottle_count,
                    "free_slots": free_slots,
                }
            )

        return suggestions

    def get_common_create_kwargs(self, cleaned_data):
        return {
            "storage": cleaned_data["storage"],
            "row": cleaned_data.get("row"),
            "column": cleaned_data.get("column"),
            "price": cleaned_data.get("price"),
            "is_gift": cleaned_data.get("is_gift", False),
            "gift_from": cleaned_data.get("gift_from"),
            "occasion": cleaned_data.get("occasion"),
            "rating": cleaned_data.get("rating"),
        }

    def get_extra_create_kwargs(self, cleaned_data):
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        beverage = self.get_beverage()
        context[self.beverage_context_name] = beverage
        context["free_cells_by_storage"] = self.get_free_cells_by_storage()
        context["storage_suggestions"] = self.get_storage_suggestions()
        context["stock_suggestions_title"] = (
            f"This {self.beverage_label} is already in:"
        )
        context["stock_extra_fields"] = self.get_stock_extra_fields(context["form"])
        return context

    def form_valid(self, form):
        beverage = self.get_beverage()
        household = get_active_household(self.request.user)
        create_kwargs = self.get_common_create_kwargs(form.cleaned_data)
        create_kwargs.update(
            {
                self.beverage_fk_name: beverage,
                "user": self.request.user,
                "household": household,
            }
        )
        create_kwargs.update(self.get_extra_create_kwargs(form.cleaned_data))
        self.storage_item_model.objects.create(**create_kwargs)
        self.success_url = reverse_lazy(
            self.detail_url_name, kwargs={"pk": beverage.pk}
        )
        return super().form_valid(form)


class BaseStorageItemUpdateView(
    StorageItemFormLayoutMixin, RequireMemberMixin, FormView
):
    storage_item_model = None
    beverage_fk_name = None
    beverage_context_name = None
    detail_url_name = None
    list_url_name = "bottle-list"
    move_history_model = None
    extra_initial_field_names = ()
    common_edit_field_names = (
        "storage",
        "row",
        "column",
        "price",
        "is_gift",
        "gift_from",
        "occasion",
        "rating",
    )

    def get_object(self):
        if not hasattr(self, "_object"):
            household = get_active_household(self.request.user)
            self._object = get_object_or_404(
                self.storage_item_model,
                pk=self.kwargs["pk"],
                household=household,
                deleted=False,
            )
        return self._object

    def get_beverage(self):
        return getattr(self.get_object(), self.beverage_fk_name)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs.update(self.get_update_form_kwargs(self.get_object()))
        return kwargs

    def get_update_form_kwargs(self, item):
        return {}

    def get_initial(self):
        initial = super().get_initial()
        item = self.get_object()
        for field_name in self.common_edit_field_names + self.extra_initial_field_names:
            initial[field_name] = getattr(item, field_name)
        return initial

    def get_cancel_url(self, item):
        if self.request.GET.get("next") == "list":
            return reverse_lazy(self.list_url_name)
        beverage = getattr(item, self.beverage_fk_name)
        return reverse_lazy(self.detail_url_name, kwargs={"pk": beverage.pk})

    def get_success_url_for_item(self, item):
        return self.get_cancel_url(item)

    def item_has_moved(self, item, cleaned_data):
        new_storage = cleaned_data["storage"]
        new_row = cleaned_data.get("row")
        new_column = cleaned_data.get("column")
        return (
            item.storage_id != new_storage.pk
            or item.row != new_row
            or item.column != new_column
        )

    def create_move_history(self, item, cleaned_data):
        self.move_history_model.objects.create(
            storage_item=item,
            from_storage=item.storage,
            from_row=item.row,
            from_column=item.column,
            to_storage=cleaned_data["storage"],
            to_row=cleaned_data.get("row"),
            to_column=cleaned_data.get("column"),
            user=self.request.user,
        )

    def apply_common_updates(self, item, cleaned_data):
        for field_name in self.common_edit_field_names:
            setattr(item, field_name, cleaned_data.get(field_name))

    def apply_extra_updates(self, item, cleaned_data):
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        context[self.beverage_context_name] = self.get_beverage()
        context["item"] = item
        context["storage_item"] = item
        context["free_cells_by_storage"] = self.get_free_cells_by_storage(
            exclude_item=item
        )
        context["cancel_url"] = self.get_cancel_url(item)
        return context

    def form_valid(self, form):
        item = self.get_object()
        if self.item_has_moved(item, form.cleaned_data):
            self.create_move_history(item, form.cleaned_data)

        self.apply_common_updates(item, form.cleaned_data)
        self.apply_extra_updates(item, form.cleaned_data)
        item.save()

        self.success_url = self.get_success_url_for_item(item)
        return super().form_valid(form)


# --- Shared duplicate check AJAX ---


def check_beverage_duplicate_ajax(request, *, beverage_model, detail_url_name):
    """Shared AJAX endpoint to warn about beverages with similar names.

    Accepts GET requests with a ``name`` query parameter and returns up to 5
    existing beverages from the user's household whose name closely matches the
    supplied value.  Matching uses Python difflib ratio filtering (≥ 0.6) on a
    capped set of household beverages so the response is fast even for larger
    collections.
    """
    from difflib import SequenceMatcher

    from django.urls import reverse

    name = request.GET.get("name", "").strip()
    if len(name) < 3:
        return JsonResponse({"similar": []})

    household = get_active_household(request.user)
    name_lower = name.lower()

    # Fetch candidates (limited for performance) and score by similarity.
    all_candidates = list(
        beverage_model.objects.filter(household=household, deleted=False).values(
            "pk", "name"
        )[:500]
    )

    scored = []
    for candidate in all_candidates:
        cname_lower = candidate["name"].lower()
        ratio = SequenceMatcher(None, name_lower, cname_lower).ratio()
        if ratio >= 0.6:
            scored.append((ratio, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)

    similar = [
        {
            "pk": c["pk"],
            "name": c["name"],
            "url": reverse(detail_url_name, kwargs={"pk": c["pk"]}),
        }
        for _, c in scored[:5]
    ]

    return JsonResponse({"similar": similar})


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
            "field_confidence": result.get("field_confidence", {}),
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
    homepage_title = None  # e.g. "My Wine Cellar"
    stats_template = None  # e.g. "includes/homepage_stats.html"
    alerts_template = None  # e.g. "includes/homepage_alerts.html"
    beverage_icon = None  # e.g. "wine-glass"
    reminder_service = None

    def get_app_specific_context(self, household, user):
        """Return app-specific context dict. Override per app."""
        return {}

    def get_low_stock_count(self, household):
        if self.reminder_service:
            return self.reminder_service.count_low_stock_reminders(household)

        return (
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        household = get_active_household(user)

        # Total value
        bev_not_deleted = Q(**{f"{self.beverage_fk_name}__deleted": False})
        total_value = self.storage_item_model.objects.aggregate(
            total=Sum(
                Coalesce("price", self.beverage_price_path),
                filter=Q(deleted=False, household=household) & bev_not_deleted,
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
            household=household,
            deleted=False,
            **{f"{self.beverage_fk_name}__deleted": False},
        ).count()

        # Low stock reminders
        low_stock_count = self.get_low_stock_count(household)

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
                "homepage_title": self.homepage_title,
                "stats_template": self.stats_template,
                "alerts_template": self.alerts_template,
                "beverage_icon": self.beverage_icon,
                "beverage_fk_name": self.beverage_fk_name,
            }
        )

        # App-specific context
        context.update(self.get_app_specific_context(household, user))

        # Recently viewed beverages from session
        recent_session = self.request.session.get("recent_views", [])
        if recent_session:
            recent_pks = [r["pk"] for r in recent_session]
            recent_qs = self.beverage_model.objects.filter(
                pk__in=recent_pks, household=household, deleted=False
            )
            recent_map = {b.pk: b for b in recent_qs}
            # Preserve session order
            context["recent_views"] = [
                recent_map[pk] for pk in recent_pks if pk in recent_map
            ]
        else:
            context["recent_views"] = []

        return context


# --- QR code generation ---


class BaseQRCodeView(RequireHouseholdMixin, View):
    """Generate a QR code PNG linking to a beverage's detail page."""

    beverage_model = None  # Set by subclass
    detail_url_name = None  # "wine-detail" or "whisky-detail"

    def get(self, request, pk):
        household = get_active_household(request.user)
        beverage = get_object_or_404(
            self.beverage_model.objects.filter(household=household), pk=pk
        )
        url = request.build_absolute_uri(
            reverse_lazy(self.detail_url_name, kwargs={"pk": beverage.pk})
        )
        img = qrcode.make(url, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return HttpResponse(buf.getvalue(), content_type="image/png")


# --- Random bottle picker ---


class BaseRandomBottleView(RequireHouseholdMixin, TemplateView):
    """Pick a random in-stock bottle and redirect to its detail page."""

    template_name = "core/random_bottle.html"
    storage_item_model = None  # Set by subclass
    beverage_fk_name = None  # "wine" or "whisky"
    detail_url_name = None  # "wine-detail" or "whisky-detail"

    def get(self, request, *args, **kwargs):
        household = get_active_household(request.user)
        item = (
            self.storage_item_model.objects.filter(household=household, deleted=False)
            .select_related(self.beverage_fk_name)
            .order_by("?")
            .first()
        )
        if item:
            beverage = getattr(item, self.beverage_fk_name)
            return redirect(self.detail_url_name, pk=beverage.pk)
        messages.info(request, "No bottles in stock to pick from!")
        return redirect("homepage")


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

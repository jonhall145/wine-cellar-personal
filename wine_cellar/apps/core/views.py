from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DeleteView, FormView, TemplateView

from wine_cellar.apps.household.mixins import RequireHouseholdMixin, RequireMemberMixin
from wine_cellar.apps.user.views import get_active_household, get_user_settings

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

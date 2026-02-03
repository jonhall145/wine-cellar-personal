import json

from django.contrib.auth.decorators import login_required
from django.db import models
from django.forms import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, DetailView, FormView, ListView
from django.views.generic.list import MultipleObjectMixin
from django_filters.views import FilterView

from wine_cellar.apps.storage.filters import StorageItemFilter
from wine_cellar.apps.storage.forms import (
    StockAddForm,
    StorageForm,
    StorageItemEditForm,
)
from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.models import Wine


class StorageListView(ListView):
    model = Storage
    template_name = "storage_list.html"
    context_object_name = "storages"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().order_by("order", "created")
        household = get_active_household(self.request.user)
        return qs.filter(household=household)


class StorageDetailView(DetailView, MultipleObjectMixin):
    template_name = "storage_detail.html"
    model = Storage
    paginate_by = 10

    def get_context_data(self, **kwargs):
        object = self.get_object()
        object_list = object.get_wines
        context = super(StorageDetailView, self).get_context_data(
            object_list=object_list, **kwargs
        )
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return qs.filter(household=household)


class StorageCreateView(FormView):
    template_name = "storage_create.html"
    form_class = StorageForm
    success_url = reverse_lazy("storage-list")

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        self.process_form_data(self.request.user, household, form.cleaned_data)
        return super().form_valid(form)

    @staticmethod
    def process_form_data(user, household, cleaned_data):
        location = cleaned_data["location"]
        description = cleaned_data["description"]
        name = cleaned_data["name"]
        rows = cleaned_data["rows"] or 0
        columns = cleaned_data["columns"] or 0
        is_cold = cleaned_data.get("is_cold", False)
        is_default = cleaned_data.get("is_default", False)

        # Get max order for this household
        max_order = Storage.objects.filter(household=household).count()

        Storage.objects.create(
            location=location,
            description=description,
            name=name,
            rows=rows,
            columns=columns,
            is_cold=is_cold,
            is_default=is_default,
            order=max_order,
            user=user,
            household=household,
        )


class StorageUpdateView(FormView):
    template_name = "storage_edit.html"
    form_class = StorageForm
    success_url = reverse_lazy("storage-list")

    def get_initial(self):
        initial = super().get_initial()
        household = get_active_household(self.request.user)
        storage = get_object_or_404(Storage, pk=self.kwargs["pk"], household=household)
        initial.update(model_to_dict(storage))
        return initial

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        storage = get_object_or_404(Storage, pk=self.kwargs["pk"], household=household)
        self.process_form_data(storage, self.request.user, form.cleaned_data)
        self.success_url = reverse_lazy("storage-detail", kwargs={"pk": storage.pk})
        return super().form_valid(form)

    @staticmethod
    def process_form_data(storage, user, cleaned_data):
        location = cleaned_data["location"]
        description = cleaned_data["description"]
        name = cleaned_data["name"]
        rows = cleaned_data["rows"]
        columns = cleaned_data["columns"]
        is_cold = cleaned_data.get("is_cold", False)
        is_default = cleaned_data.get("is_default", False)

        storage.location = location
        storage.description = description
        storage.name = name
        storage.rows = rows
        storage.columns = columns
        storage.is_cold = is_cold
        storage.is_default = is_default
        storage.user = user
        storage.save()


class StorageDeleteView(DeleteView):
    model = Storage
    template_name = "storage_confirm_delete.html"
    success_url = reverse_lazy("storage-list")

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        storages = Storage.objects.filter(household=household).count()
        if storages <= 1:
            form.add_error(
                None,
                _(
                    "You must have at least one storage."
                    + " Cannot delete the last storage."
                ),
            )
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return qs.filter(household=household)


class StorageItemAddView(FormView):
    template_name = "stock_add.html"
    form_class = StockAddForm

    def get_wine(self):
        if not hasattr(self, "_wine"):
            household = get_active_household(self.request.user)
            self._wine = get_object_or_404(
                Wine, pk=self.kwargs["pk"], household=household
            )
        return self._wine

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "user" not in kwargs:
            kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        wine = self.get_wine()
        # Pre-populate rating from wine's default rating
        if wine.rating is not None:
            initial["rating"] = wine.rating
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wine = self.get_wine()
        context["wine"] = wine
        household = get_active_household(self.request.user)
        user_storages = Storage.objects.filter(household=household)
        free_cells_by_storage = {
            storage.pk: storage.get_free_cells_by_row() for storage in user_storages
        }
        context["free_cells_by_storage"] = free_cells_by_storage

        # Storage suggestions: find where this wine already has bottles
        existing_bottles = (
            StorageItem.objects.filter(wine=wine, household=household, deleted=False)
            .select_related("storage")
            .values("storage__pk", "storage__name", "storage__rows", "storage__columns")
            .annotate(bottle_count=models.Count("pk"))
        )

        storage_suggestions = []
        for item in existing_bottles:
            storage_pk = item["storage__pk"]
            total_slots = item["storage__rows"] * item["storage__columns"]
            # For unlimited shelves (rows=0), show as "unlimited"
            if total_slots == 0:
                free_slots = None  # Unlimited
            else:
                used_slots = StorageItem.objects.filter(
                    storage_id=storage_pk, household=household, deleted=False
                ).count()
                free_slots = total_slots - used_slots

            storage_suggestions.append(
                {
                    "storage_id": storage_pk,
                    "storage_name": item["storage__name"],
                    "bottle_count": item["bottle_count"],
                    "free_slots": free_slots,
                }
            )

        context["storage_suggestions"] = storage_suggestions
        return context

    def form_valid(self, form):
        wine = self.get_wine()
        household = get_active_household(self.request.user)
        self.process_form_data(wine, self.request.user, household, form.cleaned_data)
        self.success_url = reverse_lazy("wine-detail", kwargs={"pk": wine.pk})
        return super().form_valid(form)

    @staticmethod
    def process_form_data(wine, user, household, cleaned_data):
        storage = cleaned_data["storage"]
        row = cleaned_data["row"]
        column = cleaned_data["column"]
        price = cleaned_data.get("price")
        is_gift = cleaned_data.get("is_gift", False)
        gift_from = cleaned_data.get("gift_from")
        occasion = cleaned_data.get("occasion")
        rating = cleaned_data.get("rating")

        StorageItem.objects.create(
            storage=storage,
            wine=wine,
            row=row,
            column=column,
            user=user,
            household=household,
            price=price,
            is_gift=is_gift,
            gift_from=gift_from,
            occasion=occasion,
            rating=rating,
        )


class StorageItemDeleteView(DeleteView):
    model = StorageItem
    template_name = "storage_item_confirm_delete.html"

    def get_success_url(self):
        next = self.request.GET.get("next")
        if next == "storage":
            return reverse_lazy("storage-detail", kwargs={"pk": self.object.storage.pk})
        return reverse_lazy("wine-detail", kwargs={"pk": self.object.wine.pk})

    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return qs.filter(household=household, deleted=False)

    def form_valid(self, form):
        self.object = self.get_object()
        self.object.deleted = True
        self.object.save(update_fields=["deleted"])
        return redirect(self.get_success_url())


class StorageItemHistoryView(ListView):
    model = StorageItem
    template_name = "storage_item_history.html"
    context_object_name = "storage_items"
    paginate_by = 10

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("wine", "storage")
            .order_by("-created")
        )
        household = get_active_household(self.request.user)
        return qs.filter(household=household, deleted=True)


class StorageItemListView(FilterView):
    """List all bottles (StorageItem) with filtering."""

    model = StorageItem
    template_name = "bottle_list.html"
    context_object_name = "bottles"
    filterset_class = StorageItemFilter
    paginate_by = 20

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return (
            StorageItem.objects.filter(household=household, deleted=False)
            .select_related("wine", "storage")
            .order_by("-created")
        )


class StorageItemUpdateView(FormView):
    """Edit an existing bottle (StorageItem)."""

    template_name = "bottle_edit.html"
    form_class = StorageItemEditForm

    def get_object(self):
        if not hasattr(self, "_object"):
            household = get_active_household(self.request.user)
            self._object = get_object_or_404(
                StorageItem,
                pk=self.kwargs["pk"],
                household=household,
                deleted=False,
            )
        return self._object

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["instance"] = self.get_object()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        item = self.get_object()
        initial.update(
            {
                "storage": item.storage,
                "row": item.row,
                "column": item.column,
                "price": item.price,
                "is_gift": item.is_gift,
                "gift_from": item.gift_from,
                "occasion": item.occasion,
                "rating": item.rating,
            }
        )
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        context["wine"] = item.wine
        context["item"] = item

        # Free cells calculation - exclude current item so it can be moved
        household = get_active_household(self.request.user)
        user_storages = Storage.objects.filter(household=household)
        free_cells_by_storage = {
            storage.pk: storage.get_free_cells_by_row(exclude_item=item)
            for storage in user_storages
        }
        context["free_cells_by_storage"] = free_cells_by_storage

        # Cancel URL - return to wine detail or bottle list
        next_url = self.request.GET.get("next")
        if next_url == "list":
            context["cancel_url"] = reverse_lazy("bottle-list")
        else:
            context["cancel_url"] = reverse_lazy(
                "wine-detail", kwargs={"pk": item.wine.pk}
            )

        return context

    def form_valid(self, form):
        item = self.get_object()
        item.storage = form.cleaned_data["storage"]
        item.row = form.cleaned_data["row"]
        item.column = form.cleaned_data["column"]
        item.price = form.cleaned_data["price"]
        item.is_gift = form.cleaned_data["is_gift"]
        item.gift_from = form.cleaned_data["gift_from"]
        item.occasion = form.cleaned_data["occasion"]
        item.rating = form.cleaned_data["rating"]
        item.save()

        next_url = self.request.GET.get("next")
        if next_url == "list":
            self.success_url = reverse_lazy("bottle-list")
        else:
            self.success_url = reverse_lazy("wine-detail", kwargs={"pk": item.wine.pk})

        return super().form_valid(form)


@login_required
def storage_grid_data(request):
    """API endpoint to get storage grid data for React component."""
    household = get_active_household(request.user)
    storages = Storage.objects.filter(household=household).order_by("name")

    # Get current storage from query param or use first one
    current_storage_id = request.GET.get("storage_id")
    if current_storage_id:
        current_storage_id = int(current_storage_id)
    elif storages.exists():
        current_storage_id = storages.first().pk
    else:
        current_storage_id = None

    storage_data = []
    for storage in storages:
        items = []
        for item in storage.items.filter(deleted=False).select_related("wine"):
            wine = item.wine
            # Use bottle's rating, fall back to wine's rating
            rating = item.rating if item.rating is not None else wine.rating
            items.append(
                {
                    "row": item.row,
                    "column": item.column,
                    "wine": {
                        "id": wine.pk,
                        "name": wine.name,
                        "vintage": wine.vintage,
                        "wine_type": (
                            wine.get_wine_type_display() if wine.wine_type else ""
                        ),
                        "country": wine.country or "",
                        "item_id": item.pk,
                        "rating": rating,
                    },
                }
            )

        storage_data.append(
            {
                "id": storage.pk,
                "name": storage.name,
                "rows": storage.rows,
                "columns": storage.columns,
                "items": items,
            }
        )

    return JsonResponse(
        {
            "storages": storage_data,
            "current_storage_id": current_storage_id,
        }
    )


@login_required
@require_POST
def move_bottle(request):
    """API endpoint to move a bottle to a new position."""
    try:
        data = json.loads(request.body)
        item_id = data.get("item_id")
        target_storage_id = data.get("target_storage_id")
        target_row = data.get("target_row")
        target_column = data.get("target_column")

        # Validate inputs
        if not all([item_id, target_storage_id, target_row, target_column]):
            return JsonResponse({"error": "Missing required fields"}, status=400)

        household = get_active_household(request.user)

        # Get the item to move
        try:
            item = StorageItem.objects.get(
                pk=item_id, household=household, deleted=False
            )
        except StorageItem.DoesNotExist:
            return JsonResponse({"error": "Bottle not found"}, status=404)

        # Get target storage
        try:
            target_storage = Storage.objects.get(
                pk=target_storage_id, household=household
            )
        except Storage.DoesNotExist:
            return JsonResponse({"error": "Storage not found"}, status=404)

        # Check if target position is valid
        if target_row < 1 or target_row > target_storage.rows:
            return JsonResponse({"error": "Invalid row"}, status=400)
        if target_column < 1 or target_column > target_storage.columns:
            return JsonResponse({"error": "Invalid column"}, status=400)

        # Check if target position is occupied
        if target_storage.is_slot_occupied(target_row, target_column):
            # Check if it's the same item (no-op)
            if (
                item.storage_id == target_storage_id
                and item.row == target_row
                and item.column == target_column
            ):
                return JsonResponse({"success": True, "message": "No change needed"})
            return JsonResponse({"error": "Target position is occupied"}, status=400)

        # Move the bottle
        item.storage = target_storage
        item.row = target_row
        item.column = target_column
        item.save(update_fields=["storage", "row", "column"])

        return JsonResponse(
            {
                "success": True,
                "message": (
                    f"Moved to {target_storage.name} ({target_row}, {target_column})"
                ),
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def storage_move_up(request, pk):
    """Move a storage up in the display order."""
    household = get_active_household(request.user)
    storage = get_object_or_404(Storage, pk=pk, household=household)
    prev_storage = (
        Storage.objects.filter(household=household, order__lt=storage.order)
        .order_by("-order")
        .first()
    )
    if prev_storage:
        storage.order, prev_storage.order = prev_storage.order, storage.order
        storage.save(update_fields=["order"])
        prev_storage.save(update_fields=["order"])
    return redirect("storage-list")


@login_required
def storage_move_down(request, pk):
    """Move a storage down in the display order."""
    household = get_active_household(request.user)
    storage = get_object_or_404(Storage, pk=pk, household=household)
    next_storage = (
        Storage.objects.filter(household=household, order__gt=storage.order)
        .order_by("order")
        .first()
    )
    if next_storage:
        storage.order, next_storage.order = next_storage.order, storage.order
        storage.save(update_fields=["order"])
        next_storage.save(update_fields=["order"])
    return redirect("storage-list")

import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.forms import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, DetailView, FormView, ListView
from django.views.generic.list import MultipleObjectMixin
from django_filters.views import FilterView

from wine_cellar.apps.core.views import (
    BaseBottleQuickLogView,
    BaseMarkBottleBrokenOrLostView,
    BaseMarkBottleGivenView,
    BaseStorageItemAddView,
    BaseStorageItemUpdateView,
)
from wine_cellar.apps.household.mixins import RequireHouseholdMixin
from wine_cellar.apps.storage.filters import StorageItemFilter
from wine_cellar.apps.storage.forms import (
    StockAddForm,
    StorageForm,
    StorageItemEditForm,
)
from wine_cellar.apps.storage.models import (
    BottleMoveHistory,
    Storage,
    StorageItem,
    get_app_type,
)
from wine_cellar.apps.storage.utils import (
    format_bottle_location,
    format_given_detail,
    format_move_detail,
    with_removal_sort_date,
)
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.whisky.utils import classify_cask_type
from wine_cellar.apps.wine.models import DrinkRecord, Wine

logger = logging.getLogger(__name__)


def _is_whisky_mode():
    return getattr(settings, "CELLAR_APP_TYPE", "wine") == "whisky"


def _get_storage_item_model():
    if _is_whisky_mode():
        from wine_cellar.apps.whisky.models import WhiskyStorageItem

        return WhiskyStorageItem
    return StorageItem


logger = logging.getLogger(__name__)


class StorageListView(ListView):
    model = Storage
    template_name = "storage_list.html"
    context_object_name = "storages"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().order_by("order", "created")
        household = get_active_household(self.request.user)
        return qs.filter(household=household, app_type=get_app_type())


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
        return qs.filter(household=household, app_type=get_app_type())


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
        app_type = get_app_type()
        max_order = Storage.objects.filter(
            household=household, app_type=app_type
        ).count()

        cell_mask = cleaned_data.get("cell_mask")

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
            app_type=app_type,
            cell_mask=cell_mask,
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
        if storage.cell_mask is not None:
            initial["cell_mask"] = json.dumps(storage.cell_mask)
        else:
            initial["cell_mask"] = ""
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
        cell_mask = cleaned_data.get("cell_mask")

        # Clip mask to new bounds if rows/columns changed
        if cell_mask is not None and rows and columns:
            cell_mask = [
                [r, c] for r, c in cell_mask if 1 <= r <= rows and 1 <= c <= columns
            ]
            # If all cells are active, set mask to null
            if len(cell_mask) == rows * columns:
                cell_mask = None

        storage.location = location
        storage.description = description
        storage.name = name
        storage.rows = rows
        storage.columns = columns
        storage.is_cold = is_cold
        storage.is_default = is_default
        storage.cell_mask = cell_mask
        storage.user = user
        storage.save()


class StorageDeleteView(DeleteView):
    model = Storage
    template_name = "storage_confirm_delete.html"
    success_url = reverse_lazy("storage-list")

    def form_valid(self, form):
        household = get_active_household(self.request.user)
        storages = Storage.objects.filter(
            household=household, app_type=get_app_type()
        ).count()
        if storages <= 1:
            form.add_error(
                None,
                "You must have at least one storage."
                " Cannot delete the last storage.",
            )
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_queryset(self):
        qs = super().get_queryset()
        household = get_active_household(self.request.user)
        return qs.filter(household=household, app_type=get_app_type())


class StorageItemAddView(BaseStorageItemAddView):
    template_name = "stock_add.html"
    form_class = StockAddForm
    beverage_model = Wine
    storage_item_model = StorageItem
    beverage_fk_name = "wine"
    beverage_context_name = "wine"
    beverage_label = "wine"
    detail_url_name = "wine-detail"
    show_storage_suggestions = True

    def get_add_initial(self, wine):
        if wine.rating is None:
            return {}
        return {"rating": wine.rating}

    def get_extra_create_kwargs(self, cleaned_data):
        return {"occasion_date": cleaned_data.get("occasion_date")}


class StorageItemDeleteView(BaseMarkBottleBrokenOrLostView):
    storage_item_model = StorageItem
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"
    list_url_name = "bottle-list"
    storage_detail_url_name = "storage-detail"


class StorageItemMarkGivenView(BaseMarkBottleGivenView):
    storage_item_model = StorageItem
    beverage_fk_name = "wine"
    detail_url_name = "wine-detail"
    list_url_name = "bottle-list"


class StorageItemHistoryView(ListView):
    model = StorageItem
    template_name = "storage_item_history.html"
    context_object_name = "storage_items"
    paginate_by = 10

    def get_queryset(self):
        qs = with_removal_sort_date(
            super().get_queryset().select_related("wine", "storage")
        ).order_by("-removal_sort_date", "-created", "-pk")
        household = get_active_household(self.request.user)
        return qs.filter(household=household, deleted=True)


class StorageItemListView(RequireHouseholdMixin, FilterView):
    """List all bottles (StorageItem) with filtering."""

    model = StorageItem
    template_name = "bottle_list.html"
    context_object_name = "bottles"
    filterset_class = StorageItemFilter
    paginate_by = 20

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return (
            StorageItem.objects.filter(household=household)
            .select_related("wine", "storage")
            .order_by("-created")
        )


class StorageItemUpdateView(BaseStorageItemUpdateView):
    """Edit an existing bottle (StorageItem)."""

    template_name = "bottle_edit.html"
    form_class = StorageItemEditForm
    storage_item_model = StorageItem
    beverage_fk_name = "wine"
    beverage_context_name = "wine"
    detail_url_name = "wine-detail"
    move_history_model = BottleMoveHistory
    extra_initial_field_names = ("occasion_date",)

    def get_update_form_kwargs(self, item):
        return {"instance": item}

    def apply_extra_updates(self, item, cleaned_data):
        item.occasion_date = cleaned_data.get("occasion_date")


@login_required
def storage_grid_data(request):
    """API endpoint to get storage grid data for React component."""
    household = get_active_household(request.user)
    storages = Storage.objects.filter(
        household=household, app_type=get_app_type()
    ).order_by("name")

    # Get current storage from query param or use first one
    current_storage_id = request.GET.get("storage_id")
    if current_storage_id:
        current_storage_id = int(current_storage_id)
    elif storages.exists():
        current_storage_id = storages.first().pk
    else:
        current_storage_id = None

    whisky_mode = _is_whisky_mode()

    storage_data = []
    for storage in storages:
        items = []
        used_slots = storage.used_slots
        total_slots = storage.total_slots
        utilization_percent = (
            round((used_slots / total_slots) * 100) if total_slots else 0
        )
        item_qs = storage._get_items().filter(deleted=False)
        if whisky_mode:
            item_qs = item_qs.select_related("whisky")
        else:
            item_qs = item_qs.select_related("wine")

        for item in item_qs:
            if whisky_mode:
                whisky = item.whisky
                rating = item.rating if item.rating is not None else whisky.rating
                cask_cat = classify_cask_type(whisky.cask_type or "")
                items.append(
                    {
                        "row": item.row,
                        "column": item.column,
                        "wine": {
                            "id": whisky.pk,
                            "name": whisky.name,
                            "vintage": whisky.vintage_year,
                            "wine_type": (
                                whisky.get_whisky_type_display()
                                if whisky.whisky_type
                                else ""
                            ),
                            "wine_type_class": f"cask-{cask_cat}",
                            "country": whisky.country or "",
                            "item_id": item.pk,
                            "rating": rating,
                        },
                    }
                )
            else:
                wine = item.wine
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
                "used_slots": used_slots,
                "total_slots": total_slots,
                "utilization_percent": utilization_percent,
                "cell_mask": storage.cell_mask,
                "items": items,
            }
        )

    return JsonResponse(
        {
            "storages": storage_data,
            "current_storage_id": current_storage_id,
            "item_url_prefix": "/whisky/" if whisky_mode else "/wine/",
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
        if any(
            value is None
            for value in (item_id, target_storage_id, target_row, target_column)
        ):
            return JsonResponse({"error": "Missing required fields"}, status=400)

        household = get_active_household(request.user)

        # Get the item to move
        ItemModel = _get_storage_item_model()
        try:
            item = ItemModel.objects.get(pk=item_id, household=household, deleted=False)
        except ItemModel.DoesNotExist:
            return JsonResponse({"error": "Bottle not found"}, status=404)

        # Get target storage
        try:
            target_storage = Storage.objects.get(
                pk=target_storage_id,
                household=household,
                app_type=get_app_type(),
            )
        except Storage.DoesNotExist:
            return JsonResponse({"error": "Storage not found"}, status=404)

        # Check if target position is valid
        if target_row < 1 or target_row > target_storage.rows:
            return JsonResponse({"error": "Invalid row"}, status=400)
        if target_column < 1 or target_column > target_storage.columns:
            return JsonResponse({"error": "Invalid column"}, status=400)
        if not target_storage.is_cell_active(target_row, target_column):
            return JsonResponse({"error": "Target cell is not active"}, status=400)

        with transaction.atomic():
            item = (
                ItemModel.objects.select_for_update()
                .select_related("storage")
                .get(pk=item.pk, household=household, deleted=False)
            )
            storage_ids = {target_storage.pk}
            if item.storage_id is not None:
                storage_ids.add(item.storage_id)
            locked_storages = {
                storage.pk: storage
                for storage in Storage.objects.select_for_update()
                .filter(pk__in=storage_ids)
                .order_by("pk")
            }
            target_storage = locked_storages[target_storage.pk]

            if (
                item.storage_id == target_storage_id
                and item.row == target_row
                and item.column == target_column
            ):
                return JsonResponse({"success": True, "message": "No change needed"})

            if (
                ItemModel.objects.filter(
                    storage=target_storage,
                    row=target_row,
                    column=target_column,
                    deleted=False,
                )
                .exclude(pk=item.pk)
                .exists()
            ):
                return JsonResponse(
                    {"error": "Target position is occupied"}, status=400
                )

            old_storage = item.storage
            old_row = item.row
            old_column = item.column

            item.storage = target_storage
            item.row = target_row
            item.column = target_column
            item.save(update_fields=["storage", "row", "column"])

            if _is_whisky_mode():
                from wine_cellar.apps.whisky.models import WhiskyBottleMoveHistory

                WhiskyBottleMoveHistory.objects.create(
                    storage_item=item,
                    from_storage=old_storage,
                    from_row=old_row,
                    from_column=old_column,
                    to_storage=target_storage,
                    to_row=target_row,
                    to_column=target_column,
                    user=request.user,
                )
            else:
                BottleMoveHistory.objects.create(
                    storage_item=item,
                    from_storage=old_storage,
                    from_row=old_row,
                    from_column=old_column,
                    to_storage=target_storage,
                    to_row=target_row,
                    to_column=target_column,
                    user=request.user,
                )

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
    except Exception:
        logger.exception("Unexpected error while moving bottle.")
        return JsonResponse(
            {"error": "An internal error occurred while moving the bottle."},
            status=500,
        )


@login_required
def storage_move_up(request, pk):
    """Move a storage up in the display order."""
    household = get_active_household(request.user)
    storage = get_object_or_404(Storage, pk=pk, household=household)
    prev_storage = (
        Storage.objects.filter(
            household=household, app_type=get_app_type(), order__lt=storage.order
        )
        .order_by("-order")
        .first()
    )
    if prev_storage:
        storage.order, prev_storage.order = prev_storage.order, storage.order
        storage.save(update_fields=["order"])
        prev_storage.save(update_fields=["order"])
    return redirect("storage-list")


class BottleHistoryView(RequireHouseholdMixin, DetailView):
    """Show the lifecycle history timeline for a single wine bottle (StorageItem)."""

    model = StorageItem
    template_name = "bottle_history.html"
    context_object_name = "item"

    def get_queryset(self):
        household = get_active_household(self.request.user)
        return StorageItem.objects.filter(household=household).select_related(
            "wine", "storage"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.object
        events = []

        events.append(
            {
                "type": "added",
                "date": item.created.date(),
                "label": "Added to cellar",
                "detail": format_bottle_location(item.storage, item.row, item.column),
            }
        )

        moves = item.move_history.select_related("from_storage", "to_storage").all()
        for move in moves:
            events.append(
                {
                    "type": "move",
                    "date": move.moved_at.date(),
                    "label": "Moved",
                    "detail": format_move_detail(
                        move.from_storage,
                        move.from_row,
                        move.from_column,
                        move.to_storage,
                        move.to_row,
                        move.to_column,
                    ),
                }
            )

        for drink in item.drink_records.all():
            events.append(
                {
                    "type": "drink",
                    "date": drink.date_consumed,
                    "label": "Drink recorded",
                    "detail": drink.tasting_notes or "",
                }
            )

        if item.removal_reason == StorageItem.RemovalReason.GIVEN and item.given_date:
            events.append(
                {
                    "type": "given",
                    "date": item.given_date,
                    "label": "Given away",
                    "detail": format_given_detail(item.recipient, item.given_occasion),
                }
            )
        elif item.finished_date:
            event_type = "finished"
            label = "Broken or lost"
            if item.removal_reason in ("", StorageItem.RemovalReason.CONSUMED):
                label = "Finished"
            elif item.removal_reason != StorageItem.RemovalReason.REMOVED:
                label = "Removed from inventory"
            else:
                event_type = "removed"
            events.append(
                {
                    "type": event_type,
                    "date": item.finished_date,
                    "label": label,
                    "detail": "",
                }
            )

        context["events"] = sorted(events, key=lambda e: e["date"])
        context["beverage"] = item.wine
        context["beverage_detail_url"] = reverse(
            "wine-detail", kwargs={"pk": item.wine.pk}
        )
        if item.deleted:
            if item.removal_reason == StorageItem.RemovalReason.GIVEN:
                context["beverage_detail_url"] += "?show_consumed=1#gifted-bottles"
            else:
                context["beverage_detail_url"] += "?show_consumed=1#consumed-bottles"
        return context


class BottleQuickLogView(BaseBottleQuickLogView):
    storage_item_model = StorageItem
    drink_record_model = DrinkRecord
    beverage_fk_name = "wine"

    def handle_bottle_update(self, storage_item, date_consumed):
        storage_item.deleted = True
        storage_item.finished_date = date_consumed
        storage_item.removal_reason = StorageItem.RemovalReason.CONSUMED
        storage_item.given_date = None
        storage_item.recipient = ""
        storage_item.given_occasion = ""
        storage_item.save_with_modified(
            update_fields=[
                "deleted",
                "finished_date",
                "removal_reason",
                "given_date",
                "recipient",
                "given_occasion",
            ]
        )


@login_required
def storage_move_down(request, pk):
    """Move a storage down in the display order."""
    household = get_active_household(request.user)
    storage = get_object_or_404(Storage, pk=pk, household=household)
    next_storage = (
        Storage.objects.filter(
            household=household, app_type=get_app_type(), order__gt=storage.order
        )
        .order_by("order")
        .first()
    )
    if next_storage:
        storage.order, next_storage.order = next_storage.order, storage.order
        storage.save(update_fields=["order"])
        next_storage.save(update_fields=["order"])
    return redirect("storage-list")

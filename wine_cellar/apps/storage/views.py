from django.forms import model_to_dict
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import DeleteView, DetailView, FormView, ListView
from django.views.generic.list import MultipleObjectMixin

from wine_cellar.apps.storage.forms import StockAddForm, StorageForm
from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.wine.models import Wine


class StorageListView(ListView):
    model = Storage
    template_name = "storage_list.html"
    context_object_name = "storages"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset().order_by("created")
        return qs.filter(user=self.request.user)


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
        return qs.filter(user=self.request.user)


class StorageCreateView(FormView):
    template_name = "storage_create.html"
    form_class = StorageForm
    success_url = reverse_lazy("storage-list")

    def form_valid(self, form):
        self.process_form_data(self.request.user, form.cleaned_data)
        return super().form_valid(form)

    @staticmethod
    def process_form_data(user, cleaned_data):
        location = cleaned_data["location"]
        description = cleaned_data["description"]
        name = cleaned_data["name"]
        rows = cleaned_data["rows"] or 0
        columns = cleaned_data["columns"] or 0

        Storage.objects.create(
            location=location,
            description=description,
            name=name,
            rows=rows,
            columns=columns,
            user=user,
        )


class StorageUpdateView(FormView):
    template_name = "storage_edit.html"
    form_class = StorageForm
    success_url = reverse_lazy("storage-list")

    def get_initial(self):
        initial = super().get_initial()
        storage = get_object_or_404(
            Storage, pk=self.kwargs["pk"], user=self.request.user
        )
        initial.update(model_to_dict(storage))
        return initial

    def form_valid(self, form):
        storage = get_object_or_404(
            Storage, pk=self.kwargs["pk"], user=self.request.user
        )
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

        storage.location = location
        storage.description = description
        storage.name = name
        storage.rows = rows
        storage.columns = columns
        storage.user = user
        storage.save()


class StorageDeleteView(DeleteView):
    model = Storage
    template_name = "storage_confirm_delete.html"
    success_url = reverse_lazy("storage-list")

    def form_valid(self, form):
        storages = Storage.objects.filter(user=self.request.user).count()
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
        return qs.filter(user=self.request.user)


class StorageItemAddView(FormView):
    template_name = "stock_add.html"
    form_class = StockAddForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "user" not in kwargs:
            kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
        return context

    def form_valid(self, form):
        wine = get_object_or_404(Wine, pk=self.kwargs["pk"], user=self.request.user)
        self.process_form_data(wine, self.request.user, form.cleaned_data)
        self.success_url = reverse_lazy("wine-detail", kwargs={"pk": wine.pk})
        return super().form_valid(form)

    @staticmethod
    def process_form_data(wine, user, cleaned_data):
        storage = cleaned_data["storage"]
        row = cleaned_data["row"]
        column = cleaned_data["column"]
        price = cleaned_data.get("price")
        is_gift = cleaned_data.get("is_gift", False)
        gift_from = cleaned_data.get("gift_from")
        occasion = cleaned_data.get("occasion")

        StorageItem.objects.create(
            storage=storage,
            wine=wine,
            row=row,
            column=column,
            user=user,
            price=price,
            is_gift=is_gift,
            gift_from=gift_from,
            occasion=occasion,
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
        return qs.filter(user=self.request.user, deleted=False)

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
        qs = super().get_queryset().order_by("-created")
        return qs.filter(user=self.request.user, deleted=True)


from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json


@login_required
def storage_grid_data(request):
    """API endpoint to get storage grid data for React component."""
    storages = Storage.objects.filter(user=request.user).order_by("name")

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

        # Get the item to move
        try:
            item = StorageItem.objects.get(pk=item_id, user=request.user, deleted=False)
        except StorageItem.DoesNotExist:
            return JsonResponse({"error": "Bottle not found"}, status=404)

        # Get target storage
        try:
            target_storage = Storage.objects.get(
                pk=target_storage_id, user=request.user
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
                "message": f"Moved to {target_storage.name} ({target_row}, {target_column})",
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

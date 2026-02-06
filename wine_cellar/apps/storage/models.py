from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.wine.models import UserContentModel, Wine


class Storage(UserContentModel):
    name = models.CharField(max_length=100, verbose_name=_("Storage Name"))
    description = models.TextField(
        verbose_name=_("Storage Description"), null=True, blank=True
    )
    location = models.CharField(max_length=100, verbose_name=_("Location"))
    rows = models.PositiveIntegerField(default=0, verbose_name=_("Number of Rows"))
    columns = models.PositiveIntegerField(
        default=0, verbose_name=_("Number of Columns")
    )
    is_cold = models.BooleanField(default=False, verbose_name=_("Cold Storage"))
    order = models.PositiveIntegerField(default=0, verbose_name=_("Display Order"))
    is_default = models.BooleanField(default=False, verbose_name=_("Default Storage"))

    class Meta:
        verbose_name = _("Storage")
        verbose_name_plural = _("Storages")

    def save(self, *args, **kwargs):
        if self.is_default:
            # Ensure only one default storage per user
            Storage.objects.filter(user=self.user, is_default=True).update(
                is_default=False
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def total_slots(self):
        return self.rows * self.columns

    @property
    def used_slots(self):
        return self.items.filter(deleted=False).count()

    @property
    def is_full(self):
        return self.used_slots >= self.total_slots

    def is_slot_occupied(self, row, column):
        return self.items.filter(row=row, column=column, deleted=False).exists()

    @property
    def get_wines(self):
        return self.items.filter(deleted=False).order_by("row", "column")

    def get_free_cells_by_row(self, exclude_item=None):
        """
        Calculate free cells for each row in this storage.

        Args:
            exclude_item: Optional StorageItem to exclude from occupied calculation
                         (useful when moving a bottle)

        Returns:
            Dict mapping row numbers to lists of free column numbers.
            Empty dict if storage has no rows (rows=0).
        """
        if self.rows == 0:
            return {}

        occupied_query = self.items.filter(deleted=False)
        if exclude_item:
            occupied_query = occupied_query.exclude(pk=exclude_item.pk)

        used_cells = set(occupied_query.values_list("row", "column"))

        free_cells = {}
        for row in range(1, self.rows + 1):
            free_cells[row] = [
                col
                for col in range(1, self.columns + 1)
                if (row, col) not in used_cells
            ]
        return free_cells


class StorageItem(UserContentModel):
    storage = models.ForeignKey(Storage, on_delete=models.CASCADE, related_name="items")
    wine = models.ForeignKey(Wine, on_delete=models.CASCADE)
    row = models.PositiveIntegerField(null=True, blank=True)
    column = models.PositiveIntegerField(null=True, blank=True)
    deleted = models.BooleanField(default=False, db_index=True)
    price = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    is_gift = models.BooleanField(default=False, verbose_name=_("Is Gift"))
    gift_from = models.CharField(
        max_length=100, null=True, blank=True, verbose_name=_("Gift From")
    )
    occasion = models.CharField(
        max_length=100, null=True, blank=True, verbose_name=_("Occasion")
    )
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name=_("Rating"),
        help_text=_("Star rating (0-3) for this specific bottle."),
    )

    class Meta:
        verbose_name = _("Storage Item")
        verbose_name_plural = _("Storage Items")
        indexes = [
            models.Index(fields=["user", "deleted"], name="storageitem_user_del_idx"),
            models.Index(
                fields=["storage", "row", "column"], name="storageitem_position_idx"
            ),
            models.Index(fields=["wine", "deleted"], name="storageitem_wine_del_idx"),
        ]

    def __str__(self):
        location = (
            f"Row {self.row}, Col {self.column}"
            if self.row and self.column
            else "Unassigned"
        )
        return f"{self.wine.name} - {self.storage.name} ({location})"

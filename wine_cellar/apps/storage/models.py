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

    class Meta:
        verbose_name = _("Storage")
        verbose_name_plural = _("Storages")

    def __str__(self):
        return self.name

    @property
    def total_slots(self):
        return self.rows * self.columns

    @property
    def used_slots(self):
        return self.items.count()

    @property
    def is_full(self):
        return self.used_slots >= self.total_slots

    def is_slot_occupied(self, row, column):
        return self.items.filter(row=row, column=column, deleted=False).exists()

    @property
    def get_wines(self):
        return self.items.filter(deleted=False).order_by("row", "column")


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

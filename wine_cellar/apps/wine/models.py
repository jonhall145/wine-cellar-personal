from decimal import Decimal

import pycountry
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.formats import number_format

from wine_cellar.apps.core.models import (
    HouseholdQuerySet,
    UserContentModel,
)
from wine_cellar.apps.core.models import versioned_media_url as _versioned_media_url
from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.utils import user_directory_path


class WineType(models.TextChoices):
    WHITE = "WH", "White"
    RED = "RE", "Red"
    ROSE = "RO", "Rose"
    SPARKLING = "SP", "Sparkling"
    DESSERT = "DE", "Dessert"
    FORTIFIED = "FO", "Fortified"
    ORANGE = "OR", "Orange"


class Category(models.TextChoices):
    DRY = "DR", "Dry"
    SEMI_DRY = "SD", "Semi-Dry"
    MEDIUM_SWEET = "MS", "Medium Sweet"
    SWEET = "SW", "Sweet"
    FEINHERB = "FH", "Feinherb"


class ImageType(models.TextChoices):
    LABEL_FRONT = "LF", "Label Front"
    LABEL_BACK = "LB", "Label Back"


class SizeChoices(models.TextChoices):
    PICCOLO = "PI", "Piccolo (187ml)"
    DEMI = "DE", "Demi (375ml)"
    HALF = "HA", "Half (500ml)"
    STANDARD = "ST", "Standard (750ml)"
    LITER = "LI", "Liter (1L)"
    MAGNUM = "MA", "Magnum (1.5L)"
    JEROBOAM = "JE", "Jeroboam (3L)"
    REHOBOAM = "RE", "Rehoboam (4.5L)"


# Mapping from numeric liters to size codes for migration
SIZE_LITERS_TO_CODE = {
    0.1875: "PI",
    0.375: "DE",
    0.5: "HA",
    0.75: "ST",
    1.0: "LI",
    1.5: "MA",
    3.0: "JE",
    4.5: "RE",
}


class Size(UserContentModel):
    name = models.CharField(
        max_length=2,
        choices=SizeChoices,
        default=SizeChoices.STANDARD,
        verbose_name="Size",
    )

    class Meta:
        verbose_name = "Size"
        verbose_name_plural = "Sizes"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique size",
            )
        ]

    def __str__(self):
        return str(SizeChoices(self.name).label) if self.name else ""


class Grape(UserContentModel):
    name = models.CharField(max_length=100, verbose_name="Grape")

    class Meta:
        verbose_name = "Grape"
        verbose_name_plural = "Grapes"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique grape",
            )
        ]

    def __str__(self):
        return self.name or ""


class Vineyard(UserContentModel):
    name = models.CharField(max_length=100, verbose_name="Name")
    website = models.CharField(max_length=100, null=True, verbose_name="Website")
    region = models.CharField(max_length=250, null=True, verbose_name="Region")
    country = models.CharField(
        max_length=3,
        null=True,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        verbose_name="Country",
    )

    class Meta:
        verbose_name = "Vineyard"
        verbose_name_plural = "Vineyards"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "country", "region", "user"],
                name="unique vineyard",
            )
        ]

    def __str__(self):
        return self.name


class FoodPairing(UserContentModel):
    name = models.CharField(max_length=100, verbose_name="Food")

    class Meta:
        verbose_name = "Food Pairing"
        verbose_name_plural = "Food Pairings"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique food pairing",
            )
        ]

    def __str__(self):
        return self.name


class Attribute(UserContentModel):
    name = models.CharField(max_length=100, verbose_name="Attribute")

    class Meta:
        verbose_name = "Attribute"
        verbose_name_plural = "Attributes"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique attributes",
            )
        ]

    def __str__(self):
        return self.name


class Appellation(models.Model):
    """Wine appellation/region with geocoded coordinates."""

    name = models.CharField(max_length=100, verbose_name="Name")
    country = models.CharField(
        max_length=3,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        verbose_name="Country",
    )
    latitude = models.FloatField(verbose_name="Latitude")
    longitude = models.FloatField(verbose_name="Longitude")
    parent_region = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subregions",
        verbose_name="Parent Region",
    )

    class Meta:
        verbose_name = "Appellation"
        verbose_name_plural = "Appellations"
        indexes = [
            models.Index(fields=["country"], name="appellation_country_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "country"],
                name="unique_appellation_name_country",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.country})"


class Source(UserContentModel):
    name = models.CharField(max_length=250, verbose_name="Source")
    url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="URL",
        help_text="Website URL for this source",
    )
    price_selector = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Price CSS Selector",
        help_text="CSS selector to extract price, e.g., '.product-price'",
    )

    class Meta:
        verbose_name = "Source"
        verbose_name_plural = "Sources"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique source",
            )
        ]

    def __str__(self):
        return self.name


class Collection(UserContentModel):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        null=True,
        related_name="wine_collections",
        verbose_name="User",
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="wine_collection_items",
        verbose_name="Household",
    )
    name = models.CharField(max_length=100, verbose_name="Name")
    description = models.CharField(
        max_length=250,
        blank=True,
        default="",
        verbose_name="Description",
    )
    color = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Color",
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Icon",
    )
    wines = models.ManyToManyField(
        "wine.Wine",
        blank=True,
        related_name="collections",
        verbose_name="Wines",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Collection"
        verbose_name_plural = "Collections"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "household"],
                name="unique_wine_collection_name_per_household",
            )
        ]

    def __str__(self):
        return self.name


class WineQuerySet(HouseholdQuerySet):
    """Custom queryset for Wine with prefetch optimization."""

    def active(self):
        """Return only non-deleted wines."""
        return self.filter(deleted=False)

    def with_related(self):
        return self.select_related("size", "appellation").prefetch_related(
            "grapes",
            "attributes",
            "food_pairings",
            "vineyard",
            "source",
            "wineimage_set",
        )

    def with_stock_count(self):
        return self.annotate(
            stock_count=models.Count(
                "storageitem",
                filter=models.Q(storageitem__deleted=False),
                distinct=True,
            )
        )


class Wine(UserContentModel):
    objects = WineQuerySet.as_manager()

    name = models.CharField(max_length=100, verbose_name="Name")
    wine_type = models.CharField(max_length=2, choices=WineType, verbose_name="Type")
    category = models.CharField(
        max_length=2, choices=Category, null=True, verbose_name="Category"
    )
    grapes = models.ManyToManyField(Grape, verbose_name="Grapes")
    attributes = models.ManyToManyField(Attribute, verbose_name="Attributes")
    food_pairings = models.ManyToManyField(FoodPairing, verbose_name="Food Pairings")
    abv = models.FloatField(
        null=True,
        blank=True,
        verbose_name="ABV",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    size = models.ForeignKey(
        Size, on_delete=models.SET_NULL, null=True, verbose_name="Size"
    )
    vintage = models.PositiveIntegerField(
        validators=[MinValueValidator(1900)],
        null=True,
        db_index=True,
        verbose_name="Vintage",
    )
    drink_by = models.DateField(
        blank=True, null=True, db_index=True, verbose_name="Drink By"
    )
    # New drinking window fields - 0 means "now", otherwise a year
    drink_from = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Drink From",
        help_text="Year to start drinking, or 0 for 'now'",
    )
    drink_to = models.PositiveIntegerField(
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Drink Until",
        help_text="Year to drink by, or 0 for 'now'",
    )
    comment = models.CharField(max_length=250, blank=True, verbose_name="Comment")
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name="Default Rating",
        help_text="Default star rating (0-3) for bottles of this wine.",
    )
    country = models.CharField(
        max_length=3,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        db_index=True,
        verbose_name="Country",
    )
    subregion = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Subregion",
    )
    appellation = models.ForeignKey(
        Appellation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Appellation",
        help_text="Wine region with geocoded coordinates for map display",
    )
    vineyard = models.ManyToManyField(Vineyard, verbose_name="Vineyard")
    source = models.ManyToManyField(Source, verbose_name="Source")
    price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        verbose_name="Price",
        validators=[MinValueValidator(0)],
    )
    price_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Price URL",
        help_text="Product page URL for automatic price tracking",
    )
    ai_summary = models.TextField(
        blank=True,
        default="",
        verbose_name="AI Summary",
        help_text="AI-generated wine summary stored with source citations.",
    )
    ai_summary_sources = models.JSONField(
        blank=True,
        default=list,
        verbose_name="AI Summary Sources",
        help_text="Source list captured for the AI-generated wine summary.",
    )
    ai_summary_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="AI Summary Generated At",
    )
    ai_summary_model = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="AI Summary Model",
    )
    deleted = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        if self.vintage:
            return f"{self.name} ({self.vintage})"
        return self.name

    def get_absolute_url(self):
        return reverse("wine-detail", kwargs={"pk": self.pk})

    @property
    def get_vineyards(self):
        return "\n".join([str(vineyard) for vineyard in self.vineyard.all()])

    @property
    def get_grapes(self):
        return ", ".join([str(grape) for grape in self.grapes.all()])

    @property
    def get_sources(self):
        return ", ".join([str(s) for s in self.source.all()])

    @property
    def get_attributes(self):
        return "\n".join([str(attribute) for attribute in self.attributes.all()])

    @property
    def currency_symbol(self):
        user_settings = get_user_settings(self.user)
        return settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )

    def format_currency(self, amount):
        if amount is None:
            return None
        if hasattr(amount, "quantize"):
            amount = amount.quantize(Decimal("0.00"))
        formatted_price = number_format(amount, use_l10n=True)
        return f"{self.currency_symbol}{formatted_price}"

    @property
    def get_price_with_currency(self):
        return self.format_currency(self.price)

    @property
    def get_average_price_with_currency(self):
        avg_price = self.storageitem_set.aggregate(avg_price=models.Avg("price"))[
            "avg_price"
        ]

        if avg_price is None:
            return None
        return self.format_currency(avg_price)

    @property
    def get_food_pairings(self):
        return "\n".join([str(pairing) for pairing in self.food_pairings.all()])

    @property
    def get_type(self):
        return WineType(self.wine_type).label

    @property
    def get_category(self):
        if self.category:
            return Category(self.category).label

    @property
    def total_stock(self):
        return self.storageitem_set.filter(deleted=False).count()

    @property
    def get_stock(self):
        return self.storageitem_set.filter(deleted=False).order_by(
            "storage", "row", "column"
        )

    def _cached_images(self) -> list:
        """Return wineimage_set from prefetch cache if available, else query."""
        return list(self.wineimage_set.all())

    @property
    def image(self) -> str:
        images = self._cached_images()
        if not images:
            return static(settings.DEFAULT_WINE_IMAGE)
        return _versioned_media_url(images[0].image) or images[0].image.url

    @property
    def image_thumbnail(self) -> str:
        images = self._cached_images()
        # First check for explicitly selected primary image
        primary = next((i for i in images if i.is_primary), None)
        if primary:
            if primary.thumbnail:
                return _versioned_media_url(primary.thumbnail) or primary.thumbnail.url
            return _versioned_media_url(primary.image) or primary.image.url
        # Fall back to front label
        front = next((i for i in images if i.image_type == ImageType.LABEL_FRONT), None)
        if not front:
            return static(settings.DEFAULT_WINE_IMAGE)
        if front.thumbnail:
            return _versioned_media_url(front.thumbnail) or front.thumbnail.url
        return _versioned_media_url(front.image) or front.image.url

    @property
    def image_thumbnails(self) -> list[str]:
        """Return all images: thumbnails and full images for front and back labels."""
        images = {img.image_type: img for img in self._cached_images()}
        order = [
            ImageType.LABEL_FRONT,
            ImageType.LABEL_BACK,
        ]
        result = []
        for image_type in order:
            image = images.get(image_type)
            if image:
                if image.thumbnail:
                    result.append(
                        _versioned_media_url(image.thumbnail) or image.thumbnail.url
                    )
                result.append(_versioned_media_url(image.image) or image.image.url)
        return result

    @property
    def country_name(self):
        return pycountry.countries.get(alpha_2=self.country).name

    @property
    def country_icon(self):
        return pycountry.countries.get(alpha_2=self.country).flag

    class Meta:
        verbose_name = "Wine"
        verbose_name_plural = "Wines"
        indexes = [
            models.Index(fields=["user", "wine_type"], name="wine_user_type_idx"),
            models.Index(fields=["name"], name="wine_name_idx"),
            models.Index(fields=["user", "vintage"], name="wine_user_vintage_idx"),
            models.Index(fields=["user", "drink_by"], name="wine_user_drinkby_idx"),
            models.Index(fields=["user", "drink_to"], name="wine_user_drinkto_idx"),
            models.Index(fields=["user", "created"], name="wine_user_created_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "name",
                    "wine_type",
                    "abv",
                    "size",
                    "vintage",
                    "country",
                    "user",
                ],
                condition=models.Q(deleted=False),
                name="unique wine",
            )
        ]


class WineImage(models.Model):
    image = models.ImageField(upload_to=user_directory_path, verbose_name="Image")
    thumbnail = models.ImageField(
        upload_to=user_directory_path,
        blank=True,
        null=True,
        verbose_name="Thumbnail",
    )
    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name="Wine")
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="User",
    )
    image_type = models.CharField(
        max_length=3,
        choices=ImageType,
        default=ImageType.LABEL_FRONT,
        verbose_name="Image Type",
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name="Primary Image",
        help_text="Use this image as the featured thumbnail for the wine.",
    )

    class Meta:
        verbose_name = "Wine Image"
        verbose_name_plural = "Wine Images"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Ensure only one primary image per wine
            WineImage.objects.filter(wine=self.wine, is_primary=True).exclude(
                pk=self.pk
            ).update(is_primary=False)
        super().save(*args, **kwargs)


class WineBarcode(models.Model):
    """A barcode associated with a wine. Supports multiple barcodes per wine."""

    wine = models.ForeignKey(
        Wine, on_delete=models.CASCADE, related_name="barcodes", verbose_name="Wine"
    )
    barcode = models.CharField(max_length=100, verbose_name="Barcode")
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, null=True, verbose_name="User"
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Household",
    )
    created = models.DateTimeField(auto_now_add=True, verbose_name="Created")

    class Meta:
        verbose_name = "Wine Barcode"
        verbose_name_plural = "Wine Barcodes"
        indexes = [
            models.Index(fields=["barcode"], name="winebarcode_barcode_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["barcode", "user"],
                name="unique_barcode_per_user",
            )
        ]

    def __str__(self):
        return f"{self.barcode} ({self.wine.name})"


class DrinkRecord(UserContentModel):
    """Record of drinking/consuming a bottle."""

    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name="Wine")
    date_consumed = models.DateField(verbose_name="Date Consumed")
    tasting_notes = models.TextField(
        null=True, blank=True, verbose_name="Tasting Notes"
    )
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name="Rating",
        help_text="Star rating (0-3) for this drinking experience.",
    )
    shared_with = models.CharField(
        max_length=250, null=True, blank=True, verbose_name="Shared With"
    )
    occasion = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Occasion"
    )
    storage_item = models.ForeignKey(
        "storage.StorageItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drink_records",
        verbose_name="Bottle",
        help_text="The specific bottle consumed (optional).",
    )
    photo = models.ImageField(
        upload_to=user_directory_path,
        null=True,
        blank=True,
        verbose_name="Photo",
        help_text="Photo of the bottle, meal, or tasting setting.",
    )
    taste_descriptors = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Taste Descriptors",
        help_text="Selected flavor descriptors from the tasting wheel.",
    )

    class Meta:
        verbose_name = "Drink Record"
        verbose_name_plural = "Drink Records"
        ordering = ["-date_consumed"]
        indexes = [
            models.Index(
                fields=["user", "date_consumed"], name="drinkrecord_user_date_idx"
            ),
        ]


class Wishlist(UserContentModel):
    """Wines the user wants to buy."""

    name = models.CharField(max_length=100, verbose_name="Name")
    wine_type = models.CharField(
        max_length=2, choices=WineType, null=True, blank=True, verbose_name="Type"
    )
    country = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        verbose_name="Country",
    )
    subregion = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Subregion"
    )
    vintage = models.PositiveIntegerField(null=True, blank=True, verbose_name="Vintage")
    price_limit = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Price Limit",
    )
    external_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Purchase Link",
    )
    notes = models.TextField(null=True, blank=True, verbose_name="Notes")
    priority = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Priority",
    )
    purchased = models.BooleanField(default=False, verbose_name="Purchased")
    external_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Purchase Link",
    )

    class Meta:
        verbose_name = "Wishlist Item"
        verbose_name_plural = "Wishlist Items"
        ordering = ["-priority", "name"]


class BottleNote(UserContentModel):
    """Dated notes for a specific bottle over time."""

    storage_item = models.ForeignKey(
        "storage.StorageItem",
        on_delete=models.CASCADE,
        related_name="notes",
        verbose_name="Bottle",
    )
    note_date = models.DateField(verbose_name="Date")
    note = models.TextField(verbose_name="Note")

    class Meta:
        verbose_name = "Bottle Note"
        verbose_name_plural = "Bottle Notes"
        ordering = ["-note_date"]


class DrinkingWindowAlert(UserContentModel):
    """Alerts for wines approaching drinking window."""

    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name="Wine")
    alert_date = models.DateField(verbose_name="Alert Date")
    message = models.CharField(
        max_length=250, null=True, blank=True, verbose_name="Message"
    )
    is_read = models.BooleanField(default=False, verbose_name="Read")

    class Meta:
        verbose_name = "Drinking Window Alert"
        verbose_name_plural = "Drinking Window Alerts"
        ordering = ["alert_date"]


class ReorderReminder(UserContentModel):
    """Reminder to reorder a wine when stock drops below threshold."""

    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name="Wine")
    min_stock = models.PositiveIntegerField(default=1, verbose_name="Minimum Stock")
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Reorder Reminder"
        verbose_name_plural = "Reorder Reminders"
        constraints = [
            models.UniqueConstraint(
                fields=["wine", "user"],
                name="unique_reorder_reminder",
            )
        ]


class VisionExtractionLog(UserContentModel):
    """Log of vision extraction attempts for analysis and improvement."""

    image_count = models.PositiveIntegerField(
        verbose_name="Image Count",
        help_text="Number of images sent for extraction",
    )
    raw_response = models.TextField(
        verbose_name="Raw Response",
        help_text="Raw response from the vision API",
    )
    extracted_data = models.JSONField(
        verbose_name="Extracted Data",
        help_text="Parsed extraction result as JSON",
    )
    confidence = models.CharField(
        max_length=10,
        verbose_name="Confidence",
        help_text="Confidence level: high, medium, or low",
    )
    extracted_fields = models.JSONField(
        verbose_name="Extracted Fields",
        help_text="List of fields that were successfully extracted",
    )
    wine = models.ForeignKey(
        Wine,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Wine",
        help_text="Wine created from this extraction (if any)",
    )
    user_corrections = models.JSONField(
        null=True,
        blank=True,
        verbose_name="User Corrections",
        help_text="Fields that the user corrected after extraction",
    )
    was_successful = models.BooleanField(
        default=False,
        verbose_name="Successful",
        help_text="Whether the extraction led to a wine being created",
    )
    errors = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Errors",
        help_text="Any errors during extraction",
    )
    model_used = models.CharField(
        max_length=50,
        default="claude-haiku-4-5",
        verbose_name="Model Used",
        help_text="AI model used for extraction",
    )
    processing_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Processing Time (ms)",
        help_text="Time taken for the extraction in milliseconds",
    )

    class Meta:
        verbose_name = "Vision Extraction Log"
        verbose_name_plural = "Vision Extraction Logs"
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["user", "created"], name="visionlog_user_created_idx"),
            models.Index(fields=["confidence"], name="visionlog_confidence_idx"),
            models.Index(fields=["was_successful"], name="visionlog_success_idx"),
        ]

    def __str__(self):
        return f"Extraction {self.pk} ({self.confidence}) - {self.created}"


class PriceHistory(UserContentModel):
    """Historical price records for wines from various sources."""

    wine = models.ForeignKey(
        Wine,
        on_delete=models.CASCADE,
        related_name="price_history",
        verbose_name="Wine",
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="price_records",
        verbose_name="Source",
    )
    price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="Price",
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Recorded At",
    )

    class Meta:
        verbose_name = "Price History"
        verbose_name_plural = "Price History Records"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(
                fields=["wine", "source", "recorded_at"],
                name="pricehistory_wine_source_idx",
            ),
        ]

    def __str__(self):
        source_name = self.source.name if self.source else "Unknown"
        return f"{self.wine.name} - {self.price} ({source_name})"

    @property
    def price_with_currency(self):
        return self.wine.format_currency(self.price)

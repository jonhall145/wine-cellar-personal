import os
from decimal import Decimal

import pycountry
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.formats import number_format
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.utils import user_directory_path


def _versioned_media_url(field):
    """Append ?v={mtime} to a media file URL for cache busting."""
    if not field:
        return None
    url = field.url
    try:
        mtime = int(os.path.getmtime(field.path))
        return f"{url}?v={mtime}"
    except (FileNotFoundError, ValueError):
        return url


class UserContentModel(models.Model):
    """Abstract base model for user-owned content."""

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        null=True,
        verbose_name=_("User"),
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(class)s_items",
        verbose_name=_("Household"),
    )
    created = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Created"),
    )
    modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified"),
    )

    class Meta:
        abstract = True


class WineType(models.TextChoices):
    WHITE = "WH", _("White")
    RED = "RE", _("Red")
    ROSE = "RO", _("Rose")
    SPARKLING = "SP", _("Sparkling")
    DESSERT = "DE", _("Dessert")
    FORTIFIED = "FO", _("Fortified")
    ORANGE = "OR", _("Orange")


class Category(models.TextChoices):
    DRY = "DR", _("Dry")
    SEMI_DRY = "SD", _("Semi-Dry")
    MEDIUM_SWEET = "MS", _("Medium Sweet")
    SWEET = "SW", _("Sweet")
    FEINHERB = "FH", _("Feinherb")


class ImageType(models.TextChoices):
    LABEL_FRONT = "LF", _("Label Front")
    LABEL_BACK = "LB", _("Label Back")


class SizeChoices(models.TextChoices):
    PICCOLO = "PI", _("Piccolo (187ml)")
    DEMI = "DE", _("Demi (375ml)")
    HALF = "HA", _("Half (500ml)")
    STANDARD = "ST", _("Standard (750ml)")
    LITER = "LI", _("Liter (1L)")
    MAGNUM = "MA", _("Magnum (1.5L)")
    JEROBOAM = "JE", _("Jeroboam (3L)")
    REHOBOAM = "RE", _("Rehoboam (4.5L)")


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
        verbose_name=_("Size"),
    )

    class Meta:
        verbose_name = _("Size")
        verbose_name_plural = _("Sizes")
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique size",
            )
        ]

    def __str__(self):
        return str(SizeChoices(self.name).label) if self.name else ""


class Grape(UserContentModel):
    name = models.CharField(max_length=100, verbose_name=_("Grape"))

    class Meta:
        verbose_name = _("Grape")
        verbose_name_plural = _("Grapes")
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique grape",
            )
        ]

    def __str__(self):
        return self.name or ""


class Vineyard(UserContentModel):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    website = models.CharField(max_length=100, null=True, verbose_name=_("Website"))
    region = models.CharField(max_length=250, null=True, verbose_name=_("Region"))
    country = models.CharField(
        max_length=3,
        null=True,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        verbose_name=_("Country"),
    )

    class Meta:
        verbose_name = _("Vineyard")
        verbose_name_plural = _("Vineyards")
        constraints = [
            models.UniqueConstraint(
                fields=["name", "country", "region", "user"],
                name="unique vineyard",
            )
        ]

    def __str__(self):
        return self.name


class FoodPairing(UserContentModel):
    name = models.CharField(max_length=100, verbose_name=_("Food"))

    class Meta:
        verbose_name = _("Food Pairing")
        verbose_name_plural = _("Food Pairings")
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique food pairing",
            )
        ]

    def __str__(self):
        return self.name


class Attribute(UserContentModel):
    name = models.CharField(max_length=100, verbose_name=_("Attribute"))

    class Meta:
        verbose_name = _("Attribute")
        verbose_name_plural = _("Attributes")
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

    name = models.CharField(max_length=100, verbose_name=_("Name"))
    country = models.CharField(
        max_length=3,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        verbose_name=_("Country"),
    )
    latitude = models.FloatField(verbose_name=_("Latitude"))
    longitude = models.FloatField(verbose_name=_("Longitude"))
    parent_region = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subregions",
        verbose_name=_("Parent Region"),
    )

    class Meta:
        verbose_name = _("Appellation")
        verbose_name_plural = _("Appellations")
        unique_together = ["name", "country"]
        indexes = [
            models.Index(fields=["country"], name="appellation_country_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.country})"


class Source(UserContentModel):
    name = models.CharField(max_length=250, verbose_name=_("Source"))
    url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("URL"),
        help_text=_("Website URL for this source"),
    )
    price_selector = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Price CSS Selector"),
        help_text=_("CSS selector to extract price, e.g., '.product-price'"),
    )

    class Meta:
        verbose_name = _("Source")
        verbose_name_plural = _("Sources")
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique source",
            )
        ]

    def __str__(self):
        return self.name


class Wine(UserContentModel):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    wine_type = models.CharField(max_length=2, choices=WineType, verbose_name=_("Type"))
    category = models.CharField(
        max_length=2, choices=Category, null=True, verbose_name=_("Category")
    )
    grapes = models.ManyToManyField(Grape, verbose_name=_("Grapes"))
    attributes = models.ManyToManyField(Attribute, verbose_name=_("Attributes"))
    food_pairings = models.ManyToManyField(FoodPairing, verbose_name=_("Food Pairings"))
    abv = models.FloatField(null=True, blank=True, verbose_name=_("ABV"))
    size = models.ForeignKey(
        Size, on_delete=models.SET_NULL, null=True, verbose_name=_("Size")
    )
    vintage = models.PositiveIntegerField(
        validators=[MinValueValidator(1900)],
        null=True,
        db_index=True,
        verbose_name=_("Vintage"),
    )
    drink_by = models.DateField(
        blank=True, null=True, db_index=True, verbose_name=_("Drink By")
    )
    # New drinking window fields - 0 means "now", otherwise a year
    drink_from = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Drink From"),
        help_text=_("Year to start drinking, or 0 for 'now'"),
    )
    drink_to = models.PositiveIntegerField(
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("Drink Until"),
        help_text=_("Year to drink by, or 0 for 'now'"),
    )
    comment = models.CharField(max_length=250, blank=True, verbose_name=_("Comment"))
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name=_("Default Rating"),
        help_text=_("Default star rating (0-3) for bottles of this wine."),
    )
    country = models.CharField(
        max_length=3,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        db_index=True,
        verbose_name=_("Country"),
    )
    subregion = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_("Subregion"),
    )
    appellation = models.ForeignKey(
        Appellation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Appellation"),
        help_text=_("Wine region with geocoded coordinates for map display"),
    )
    vineyard = models.ManyToManyField(Vineyard, verbose_name=_("Vineyard"))
    source = models.ManyToManyField(Source, verbose_name=_("Source"))
    price = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, verbose_name=_("Price")
    )
    rrp = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("RRP"),
    )
    price_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Price URL"),
        help_text=_("Product page URL for automatic price tracking"),
    )

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
    def get_price_with_currency(self):
        user_settings = get_user_settings(self.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )
        formatted_price = number_format(self.price, use_l10n=True)
        return f"{currency}{formatted_price}"

    @property
    def get_rrp_with_currency(self):
        user_settings = get_user_settings(self.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )
        formatted_price = number_format(self.rrp, use_l10n=True)
        return f"{currency}{formatted_price}"

    @property
    def get_average_price_with_currency(self):
        user_settings = get_user_settings(self.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )
        avg_price = self.storageitem_set.aggregate(avg_price=models.Avg("price"))[
            "avg_price"
        ]

        if avg_price is None:
            return None
        avg_price = avg_price.quantize(Decimal("0.00"))
        formatted_price = number_format(avg_price, use_l10n=True)
        return f"{currency}{formatted_price}"

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

    @property
    def image(self):
        i = self.wineimage_set.first()
        if not i:
            return static(settings.DEFAULT_WINE_IMAGE)
        return _versioned_media_url(i.image) or i.image.url

    @property
    def image_thumbnail(self):
        # First check for explicitly selected primary image
        primary = self.wineimage_set.filter(is_primary=True).first()
        if primary:
            if primary.thumbnail:
                return _versioned_media_url(primary.thumbnail) or primary.thumbnail.url
            return _versioned_media_url(primary.image) or primary.image.url
        # Fall back to front label
        front = self.wineimage_set.filter(image_type=ImageType.LABEL_FRONT).first()
        if not front:
            return static(settings.DEFAULT_WINE_IMAGE)
        if front.thumbnail:
            return _versioned_media_url(front.thumbnail) or front.thumbnail.url
        # return normal image as fallback
        return _versioned_media_url(front.image) or front.image.url

    @property
    def image_thumbnails(self):
        """Return all images: thumbnails and full images for front and back labels."""
        images = {img.image_type: img for img in self.wineimage_set.all()}
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
        verbose_name = _("Wine")
        verbose_name_plural = _("Wines")
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
                name="unique wine",
            )
        ]


class WineImage(models.Model):
    image = models.ImageField(upload_to=user_directory_path, verbose_name=_("Image"))
    thumbnail = models.ImageField(
        upload_to=user_directory_path,
        blank=True,
        null=True,
        verbose_name=_("Thumbnail"),
    )
    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name=_("Wine"))
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("User"),
    )
    image_type = models.CharField(
        max_length=3,
        choices=ImageType,
        default=ImageType.LABEL_FRONT,
        verbose_name=_("Image Type"),
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("Primary Image"),
        help_text=_("Use this image as the featured thumbnail for the wine."),
    )

    class Meta:
        verbose_name = _("Wine Image")
        verbose_name_plural = _("Wine Images")

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
        Wine, on_delete=models.CASCADE, related_name="barcodes", verbose_name=_("Wine")
    )
    barcode = models.CharField(max_length=100, verbose_name=_("Barcode"))
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, null=True, verbose_name=_("User")
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Household"),
    )
    created = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))

    class Meta:
        verbose_name = _("Wine Barcode")
        verbose_name_plural = _("Wine Barcodes")
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

    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name=_("Wine"))
    date_consumed = models.DateField(verbose_name=_("Date Consumed"))
    tasting_notes = models.TextField(
        null=True, blank=True, verbose_name=_("Tasting Notes")
    )
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name=_("Rating"),
        help_text=_("Star rating (0-3) for this drinking experience."),
    )
    shared_with = models.CharField(
        max_length=250, null=True, blank=True, verbose_name=_("Shared With")
    )
    occasion = models.CharField(
        max_length=100, null=True, blank=True, verbose_name=_("Occasion")
    )
    storage_item = models.ForeignKey(
        "storage.StorageItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drink_records",
        verbose_name=_("Bottle"),
        help_text=_("The specific bottle consumed (optional)."),
    )

    class Meta:
        verbose_name = _("Drink Record")
        verbose_name_plural = _("Drink Records")
        ordering = ["-date_consumed"]
        indexes = [
            models.Index(
                fields=["user", "date_consumed"], name="drinkrecord_user_date_idx"
            ),
        ]


class Wishlist(UserContentModel):
    """Wines the user wants to buy."""

    name = models.CharField(max_length=100, verbose_name=_("Name"))
    wine_type = models.CharField(
        max_length=2, choices=WineType, null=True, blank=True, verbose_name=_("Type")
    )
    country = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        verbose_name=_("Country"),
    )
    subregion = models.CharField(
        max_length=100, null=True, blank=True, verbose_name=_("Subregion")
    )
    vintage = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Vintage")
    )
    price_limit = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Price Limit"),
    )
    notes = models.TextField(null=True, blank=True, verbose_name=_("Notes"))
    priority = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Priority"),
    )
    purchased = models.BooleanField(default=False, verbose_name=_("Purchased"))

    class Meta:
        verbose_name = _("Wishlist Item")
        verbose_name_plural = _("Wishlist Items")
        ordering = ["-priority", "name"]


class BottleNote(UserContentModel):
    """Dated notes for a specific bottle over time."""

    storage_item = models.ForeignKey(
        "storage.StorageItem",
        on_delete=models.CASCADE,
        related_name="notes",
        verbose_name=_("Bottle"),
    )
    note_date = models.DateField(verbose_name=_("Date"))
    note = models.TextField(verbose_name=_("Note"))

    class Meta:
        verbose_name = _("Bottle Note")
        verbose_name_plural = _("Bottle Notes")
        ordering = ["-note_date"]


class DrinkingWindowAlert(UserContentModel):
    """Alerts for wines approaching drinking window."""

    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name=_("Wine"))
    alert_date = models.DateField(verbose_name=_("Alert Date"))
    message = models.CharField(
        max_length=250, null=True, blank=True, verbose_name=_("Message")
    )
    is_read = models.BooleanField(default=False, verbose_name=_("Read"))

    class Meta:
        verbose_name = _("Drinking Window Alert")
        verbose_name_plural = _("Drinking Window Alerts")
        ordering = ["alert_date"]


class ReorderReminder(UserContentModel):
    """Reminder to reorder a wine when stock drops below threshold."""

    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name=_("Wine"))
    min_stock = models.PositiveIntegerField(default=1, verbose_name=_("Minimum Stock"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Reorder Reminder")
        verbose_name_plural = _("Reorder Reminders")
        constraints = [
            models.UniqueConstraint(
                fields=["wine", "user"],
                name="unique_reorder_reminder",
            )
        ]


class VisionExtractionLog(UserContentModel):
    """Log of vision extraction attempts for analysis and improvement."""

    image_count = models.PositiveIntegerField(
        verbose_name=_("Image Count"),
        help_text=_("Number of images sent for extraction"),
    )
    raw_response = models.TextField(
        verbose_name=_("Raw Response"),
        help_text=_("Raw response from the vision API"),
    )
    extracted_data = models.JSONField(
        verbose_name=_("Extracted Data"),
        help_text=_("Parsed extraction result as JSON"),
    )
    confidence = models.CharField(
        max_length=10,
        verbose_name=_("Confidence"),
        help_text=_("Confidence level: high, medium, or low"),
    )
    extracted_fields = models.JSONField(
        verbose_name=_("Extracted Fields"),
        help_text=_("List of fields that were successfully extracted"),
    )
    wine = models.ForeignKey(
        Wine,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Wine"),
        help_text=_("Wine created from this extraction (if any)"),
    )
    user_corrections = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("User Corrections"),
        help_text=_("Fields that the user corrected after extraction"),
    )
    was_successful = models.BooleanField(
        default=False,
        verbose_name=_("Successful"),
        help_text=_("Whether the extraction led to a wine being created"),
    )
    errors = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Errors"),
        help_text=_("Any errors during extraction"),
    )
    model_used = models.CharField(
        max_length=50,
        default="claude-haiku-4-5",
        verbose_name=_("Model Used"),
        help_text=_("AI model used for extraction"),
    )
    processing_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Processing Time (ms)"),
        help_text=_("Time taken for the extraction in milliseconds"),
    )

    class Meta:
        verbose_name = _("Vision Extraction Log")
        verbose_name_plural = _("Vision Extraction Logs")
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
        verbose_name=_("Wine"),
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="price_records",
        verbose_name=_("Source"),
    )
    price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name=_("Price"),
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Recorded At"),
    )

    class Meta:
        verbose_name = _("Price History")
        verbose_name_plural = _("Price History Records")
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


class SaleAlert(UserContentModel):
    """Alerts for price drops on wines from specific sources."""

    wine = models.ForeignKey(
        Wine,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sale_alerts",
        verbose_name=_("Wine"),
        help_text=_("Leave blank to monitor all wines from this source"),
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sale_alerts",
        verbose_name=_("Source"),
        help_text=_("Leave blank to monitor all sources for this wine"),
    )
    threshold_percent = models.PositiveIntegerField(
        default=10,
        verbose_name=_("Price Drop Threshold (%)"),
        help_text=_("Alert when price drops by this percentage or more"),
    )
    threshold_price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Target Price"),
        help_text=_("Alert when price drops to or below this amount"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
    )
    last_notified = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Notified"),
    )

    class Meta:
        verbose_name = _("Sale Alert")
        verbose_name_plural = _("Sale Alerts")
        indexes = [
            models.Index(
                fields=["user", "is_active"], name="salealert_user_active_idx"
            ),
        ]

    def __str__(self):
        wine_name = self.wine.name if self.wine else "Any wine"
        source_name = self.source.name if self.source else "Any source"
        return f"Alert: {wine_name} from {source_name}"

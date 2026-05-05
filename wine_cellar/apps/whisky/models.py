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
    user_directory_path,
    versioned_media_url,
)

# ---------------------------------------------------------------------------
# Custom country codes for UK nations (X prefix = ISO private use)
# ---------------------------------------------------------------------------

WHISKY_COUNTRIES = {
    "XS": "Scotland",
    "XE": "England",
    "XW": "Wales",
}

# Flag emoji fallbacks for custom codes
WHISKY_COUNTRY_FLAGS = {
    "XS": "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
    "XE": "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f",
    "XW": "\U0001f3f4\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f",
}


def get_country_name(code):
    """Resolve country code to display name, including custom whisky codes."""
    if code in WHISKY_COUNTRIES:
        return WHISKY_COUNTRIES[code]
    try:
        return pycountry.countries.get(alpha_2=code).name
    except (AttributeError, LookupError):
        return code


def get_country_icon(code):
    """Resolve country code to flag emoji, including custom whisky codes."""
    if not code:
        return ""
    if code in WHISKY_COUNTRY_FLAGS:
        return WHISKY_COUNTRY_FLAGS[code]
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


# ---------------------------------------------------------------------------
# Choice enums
# ---------------------------------------------------------------------------


class WhiskyType(models.TextChoices):
    SINGLE_MALT = "SM", "Single Malt"
    BLENDED_MALT = "BM", "Blended Malt"
    BLENDED = "BL", "Blended"
    SINGLE_GRAIN = "SG", "Single Grain"


class PeatedLevel(models.TextChoices):
    UNPEATED = "UP", "Unpeated"
    PEATED = "PE", "Peated"


class FillLevel(models.TextChoices):
    UNOPENED = "UN", "Unopened"
    OPENED = "OP", "Opened"
    DREG = "DR", "Dreg"


COMMON_CASK_TYPES = [
    "Bourbon",
    "Sherry (Oloroso)",
    "Sherry (Pedro Ximénez)",
    "Sherry (Fino)",
    "Port",
    "Rum",
    "Wine (Red)",
    "Wine (White)",
    "Madeira",
    "Marsala",
    "Cognac",
    "Beer / Ale",
    "Sauternes",
    "Moscatel",
    "Virgin Oak",
    "First Fill Bourbon",
    "Refill Bourbon",
    "First Fill Sherry",
    "Refill Sherry",
]


class WoodType(models.TextChoices):
    AMERICAN_OAK = "AO", "American Oak"
    EUROPEAN_OAK = "EO", "European Oak"
    JAPANESE_MIZUNARA = "JM", "Japanese Mizunara"
    FRENCH_OAK = "FO", "French Oak"
    OTHER = "OT", "Other"


class PreviousContents(models.TextChoices):
    BOURBON = "BO", "Bourbon"
    SHERRY_OLOROSO = "SO", "Sherry (Oloroso)"
    SHERRY_PX = "SP", "Sherry (Pedro Ximénez)"
    SHERRY_FINO = "SF", "Sherry (Fino)"
    PORT = "PO", "Port"
    RUM = "RU", "Rum"
    WINE_RED = "WR", "Wine (Red)"
    WINE_WHITE = "WW", "Wine (White)"
    MADEIRA = "MA", "Madeira"
    MARSALA = "MS", "Marsala"
    VIRGIN_OAK = "VO", "Virgin Oak"
    BEER = "BE", "Beer / Ale"
    OTHER = "OT", "Other"


class DistilleryStatus(models.TextChoices):
    ACTIVE = "AC", "Active"
    SILENT = "SI", "Silent"
    CLOSED = "CL", "Closed"
    DEMOLISHED = "DE", "Demolished"


class BottleSize(models.TextChoices):
    MINIATURE = "0.05", "Miniature (50ml)"
    SAMPLE = "0.10", "Sample (100ml)"
    SMALL = "0.20", "Small (200ml)"
    HALF = "0.35", "Half Bottle (350ml)"
    HALF_LITRE = "0.50", "Half Litre (500ml)"
    STANDARD = "0.70", "Standard (700ml)"
    LITRE = "1.00", "Litre (1000ml)"
    MAGNUM = "1.50", "Magnum (1500ml)"
    OTHER = "0.00", "Other"


# ---------------------------------------------------------------------------
# Reference models (shared fixture data, not user-scoped)
# ---------------------------------------------------------------------------


class WhiskyRegion(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    country = models.CharField(max_length=2, default="GB")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "country"],
                name="unique_whiskyregion_name_country",
            ),
        ]

    def __str__(self):
        return self.name


class Distillery(models.Model):
    name = models.CharField(max_length=200)
    region = models.ForeignKey(
        WhiskyRegion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="distilleries",
    )
    country = models.CharField(max_length=2, default="GB")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=2,
        choices=DistilleryStatus.choices,
        default=DistilleryStatus.ACTIVE,
    )
    founded_year = models.PositiveIntegerField(null=True, blank=True)
    closed_year = models.PositiveIntegerField(null=True, blank=True)
    owner = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_user_created = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "distilleries"
        indexes = [
            models.Index(
                fields=["region", "status"], name="distillery_region_status_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "country"],
                name="unique_distillery_name_country",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def country_name(self):
        return get_country_name(self.country)


class Bottler(models.Model):
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50, blank=True, default="")
    country = models.CharField(max_length=2, default="GB")
    website = models.URLField(blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_user_created = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name


# ---------------------------------------------------------------------------
# User-scoped supporting models
# ---------------------------------------------------------------------------


class WhiskyAttribute(UserContentModel):
    name = models.CharField(max_length=100, verbose_name="Attribute")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique_whiskyattribute_name_user",
            ),
        ]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Core whisky model
# ---------------------------------------------------------------------------


class WhiskyQuerySet(HouseholdQuerySet):
    """Custom queryset for Whisky with prefetch optimization."""

    def active(self):
        """Return only non-deleted whiskies."""
        return self.filter(deleted=False)

    def with_related(self):
        return self.select_related(
            "distillery",
            "region",
            "bottler",
            "source",
        ).prefetch_related("attributes", "images")

    def with_stock_count(self):
        return self.annotate(
            stock_count=models.Count(
                "whiskystorageitem",
                filter=models.Q(whiskystorageitem__deleted=False),
                distinct=True,
            )
        )


class Whisky(UserContentModel):
    objects = WhiskyQuerySet.as_manager()

    name = models.CharField(max_length=200, verbose_name="Name")
    whisky_type = models.CharField(
        max_length=2,
        choices=WhiskyType.choices,
        default=WhiskyType.SINGLE_MALT,
        verbose_name="Type",
    )
    distillery = models.ForeignKey(
        Distillery,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Distillery",
    )
    region = models.ForeignKey(
        WhiskyRegion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Region",
    )
    country = models.CharField(max_length=2, default="XS", verbose_name="Country")

    # Age & dates
    age_statement = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Age Statement",
        help_text="Leave blank for NAS (No Age Statement).",
    )
    vintage_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Distilled Year",
    )
    bottled_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Bottled Year",
    )

    # Character
    abv = models.FloatField(
        null=True,
        blank=True,
        verbose_name="ABV %",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    size = models.CharField(
        max_length=4,
        choices=BottleSize.choices,
        default=BottleSize.STANDARD,
        verbose_name="Bottle Size",
    )
    peated_level = models.CharField(
        max_length=2,
        choices=PeatedLevel.choices,
        null=True,
        blank=True,
        verbose_name="Peated",
    )
    cask_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Cask Type",
        help_text="e.g. Bourbon, Sherry (Oloroso), Virgin Oak",
    )
    cask_strength = models.BooleanField(
        default=False,
        verbose_name="Cask Strength",
    )
    color = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Color",
    )

    # Bottling details
    bottler = models.ForeignKey(
        Bottler,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Bottler",
        help_text="Leave blank for Official Bottling (OB).",
    )
    source = models.ForeignKey(
        "whisky.WhiskySource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Source",
        help_text="Where this whisky was purchased.",
    )
    bottler_series = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Bottler Series",
    )
    cask_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Cask Number",
    )
    batch_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Batch Number",
    )
    bottle_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Bottle Number",
        help_text="e.g. 123/500",
    )
    limited_edition = models.BooleanField(
        default=False,
        verbose_name="Limited Edition",
    )
    release_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Release Year",
    )

    # Tracking
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name="Rating",
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Price",
        validators=[MinValueValidator(0)],
    )
    comment = models.TextField(
        blank=True,
        default="",
        verbose_name="Comment",
    )
    owner = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Owner",
    )
    deleted = models.BooleanField(default=False, db_index=True)

    # Relations
    attributes = models.ManyToManyField(
        WhiskyAttribute,
        blank=True,
        verbose_name="Attributes",
    )

    class Meta:
        verbose_name_plural = "whiskies"
        ordering = ["-created"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "name",
                    "whisky_type",
                    "abv",
                    "size",
                    "vintage_year",
                    "bottled_year",
                    "user",
                ],
                condition=models.Q(deleted=False),
                name="unique_whisky_natural_key",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "whisky_type"], name="whisky_user_type_idx"),
            models.Index(fields=["user", "created"], name="whisky_user_created_idx"),
            models.Index(
                fields=["distillery", "age_statement"], name="whisky_dist_age_idx"
            ),
            models.Index(fields=["name"], name="whisky_name_idx"),
            models.Index(fields=["country"], name="whisky_country_idx"),
        ]

    def __str__(self):
        parts = [self.name]
        if self.age_statement:
            parts.append(f"{self.age_statement}yo")
        if self.abv:
            parts.append(f"{self.abv}%")
        return " ".join(parts)

    def get_absolute_url(self):
        return reverse("whisky-detail", kwargs={"pk": self.pk})

    @property
    def is_official_bottling(self):
        return self.bottler is None

    @property
    def is_nas(self):
        return self.age_statement is None

    @property
    def total_stock(self):
        return self.whiskystorageitem_set.filter(deleted=False).count()

    @property
    def get_stock(self):
        return self.whiskystorageitem_set.filter(deleted=False).select_related(
            "storage"
        )

    @property
    def country_name(self):
        return get_country_name(self.country)

    @property
    def country_icon(self):
        return get_country_icon(self.country)

    @property
    def image_thumbnail(self):
        images = self.images.all()
        primary = images.filter(is_primary=True).first()
        if primary:
            if primary.thumbnail:
                return versioned_media_url(primary.thumbnail) or primary.thumbnail.url
            return versioned_media_url(primary.image) or primary.image.url

        front = images.filter(image_type=WhiskyImage.ImageType.LABEL_FRONT).first()
        if front:
            if front.thumbnail:
                return versioned_media_url(front.thumbnail) or front.thumbnail.url
            return versioned_media_url(front.image) or front.image.url

        first = images.first()
        if first:
            if first.thumbnail:
                return versioned_media_url(first.thumbnail) or first.thumbnail.url
            return versioned_media_url(first.image) or first.image.url

        return static(settings.DEFAULT_WINE_IMAGE)

    @property
    def all_images(self):
        result = []
        for image in self.images.all():
            if image.thumbnail:
                url = versioned_media_url(image.thumbnail) or image.thumbnail.url
                result.append(url)
            else:
                result.append(versioned_media_url(image.image) or image.image.url)
        return result

    @property
    def display_type(self):
        return self.get_whisky_type_display()

    @property
    def currency_symbol(self):
        from wine_cellar.apps.user.views import get_user_settings

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
        avg_price = self.whiskystorageitem_set.aggregate(avg_price=models.Avg("price"))[
            "avg_price"
        ]

        if avg_price is None:
            return None
        return self.format_currency(avg_price)


# ---------------------------------------------------------------------------
# Cask history
# ---------------------------------------------------------------------------


class CaskHistory(models.Model):
    whisky = models.ForeignKey(
        Whisky,
        on_delete=models.CASCADE,
        related_name="cask_history",
    )
    order = models.PositiveIntegerField(
        verbose_name="Maturation Order",
        help_text="1 = primary cask, 2+ = subsequent casks/finishes",
    )
    cask_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Cask Type",
    )
    wood_type = models.CharField(
        max_length=2,
        choices=WoodType.choices,
        blank=True,
        default="",
        verbose_name="Wood Type",
    )
    previous_contents = models.CharField(
        max_length=2,
        choices=PreviousContents.choices,
        verbose_name="Previous Contents",
    )
    duration_years = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duration (years)",
    )
    is_finish = models.BooleanField(
        default=False,
        verbose_name="Finish",
        help_text="Check if this is a finishing cask rather than primary maturation.",
    )
    cask_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Cask Number",
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name="Notes",
    )

    class Meta:
        ordering = ["whisky", "order"]
        verbose_name_plural = "cask histories"
        constraints = [
            models.UniqueConstraint(
                fields=["whisky", "order"],
                name="unique_caskhistory_whisky_order",
            ),
        ]

    def __str__(self):
        parts = [self.get_previous_contents_display(), self.cask_type or ""]
        if self.is_finish:
            parts.append("(finish)")
        if self.duration_years:
            parts.append(f"{self.duration_years}yr")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Images & barcodes
# ---------------------------------------------------------------------------


class WhiskyImage(models.Model):
    class ImageType(models.TextChoices):
        LABEL_FRONT = "LF", "Front Label"
        LABEL_BACK = "LB", "Back Label"

    whisky = models.ForeignKey(
        Whisky,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to=user_directory_path, verbose_name="Image")
    thumbnail = models.ImageField(
        upload_to=user_directory_path,
        null=True,
        blank=True,
        verbose_name="Thumbnail",
    )
    image_type = models.CharField(
        max_length=2,
        choices=ImageType.choices,
        default=ImageType.LABEL_FRONT,
        verbose_name="Image Type",
    )
    is_primary = models.BooleanField(default=False, verbose_name="Primary Image")
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, null=True, verbose_name="User"
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-created"]

    def __str__(self):
        return f"{self.whisky.name} - {self.get_image_type_display()}"


class WhiskyBarcode(models.Model):
    whisky = models.ForeignKey(
        Whisky,
        on_delete=models.CASCADE,
        related_name="barcodes",
    )
    barcode = models.CharField(max_length=100, db_index=True)
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, null=True, verbose_name="User"
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["barcode", "user"],
                name="unique_whiskybarcode_barcode_user",
            ),
        ]

    def __str__(self):
        return f"{self.barcode} -> {self.whisky.name}"


# ---------------------------------------------------------------------------
# Storage & inventory
# ---------------------------------------------------------------------------


class WhiskyStorageItemQuerySet(HouseholdQuerySet):
    """Custom queryset for WhiskyStorageItem."""

    def in_stock(self):
        return self.filter(deleted=False)


class WhiskyStorageItem(UserContentModel):
    class RemovalReason(models.TextChoices):
        CONSUMED = "consumed", "Consumed"
        GIVEN = "given", "Given Away"
        REMOVED = "removed", "Removed"

    objects = WhiskyStorageItemQuerySet.as_manager()

    storage = models.ForeignKey(
        "storage.Storage",
        on_delete=models.CASCADE,
        related_name="whisky_items",
    )
    whisky = models.ForeignKey(Whisky, on_delete=models.CASCADE)
    row = models.PositiveIntegerField(null=True, blank=True)
    column = models.PositiveIntegerField(null=True, blank=True)
    deleted = models.BooleanField(default=False, db_index=True)
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    is_gift = models.BooleanField(default=False, verbose_name="Is Gift")
    gift_from = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Gift From"
    )
    occasion = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="Occasion"
    )
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name="Rating",
    )
    fill_level = models.CharField(
        max_length=2,
        choices=FillLevel.choices,
        default=FillLevel.UNOPENED,
        verbose_name="Fill Level",
    )
    opened_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date Opened",
    )
    dreg_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date Entered Dreg",
    )
    owner = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Owner",
    )
    finished_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date Finished",
    )
    recipient = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Recipient",
    )
    given_occasion = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Given Occasion",
    )
    given_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date Given",
    )
    removal_reason = models.CharField(
        max_length=20,
        choices=RemovalReason.choices,
        blank=True,
        default="",
        verbose_name="Removal Reason",
    )

    class Meta:
        verbose_name = "Whisky Bottle"
        verbose_name_plural = "Whisky Bottles"
        indexes = [
            models.Index(fields=["user", "deleted"], name="wsi_user_del_idx"),
            models.Index(fields=["storage", "row", "column"], name="wsi_position_idx"),
            models.Index(fields=["whisky", "deleted"], name="wsi_whisky_del_idx"),
        ]

    def __str__(self):
        location = (
            f"Row {self.row}, Col {self.column}"
            if self.row and self.column
            else "Unassigned"
        )
        return f"{self.whisky.name} - {self.storage.name} ({location})"

    @property
    def dreg_warning(self):
        """True if dreg for >335 days (warn 30 days before 1 year)."""
        import datetime

        if self.fill_level != FillLevel.DREG or not self.dreg_date:
            return False
        return (datetime.date.today() - self.dreg_date).days > 335

    @property
    def dreg_expired(self):
        """True if dreg for >365 days."""
        import datetime

        if self.fill_level != FillLevel.DREG or not self.dreg_date:
            return False
        return (datetime.date.today() - self.dreg_date).days > 365

    @property
    def removal_date(self):
        return self.given_date or self.finished_date


# ---------------------------------------------------------------------------
# Drink records & tracking
# ---------------------------------------------------------------------------


class WhiskyDrinkRecord(UserContentModel):
    whisky = models.ForeignKey(Whisky, on_delete=models.CASCADE)
    storage_item = models.ForeignKey(
        WhiskyStorageItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    date_consumed = models.DateField(verbose_name="Date")
    tasting_notes = models.TextField(
        blank=True, default="", verbose_name="Tasting Notes"
    )
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name="Rating",
    )
    shared_with = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Shared With"
    )
    occasion = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Occasion"
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
        ordering = ["-date_consumed"]
        indexes = [
            models.Index(fields=["user", "date_consumed"], name="wdr_user_date_idx"),
        ]

    def __str__(self):
        return f"{self.whisky.name} on {self.date_consumed}"


class WhiskyWishlist(UserContentModel):
    name = models.CharField(max_length=200, verbose_name="Name")
    whisky_type = models.CharField(
        max_length=2,
        choices=WhiskyType.choices,
        null=True,
        blank=True,
        verbose_name="Type",
    )
    distillery = models.ForeignKey(
        Distillery,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Distillery",
    )
    region = models.ForeignKey(
        WhiskyRegion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Region",
    )
    country = models.CharField(
        max_length=2, blank=True, default="", verbose_name="Country"
    )
    age_statement = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Age"
    )
    price_limit = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Max Price",
    )
    external_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Purchase Link",
    )
    notes = models.TextField(blank=True, default="", verbose_name="Notes")
    priority = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
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
        ordering = ["-priority", "name"]

    def __str__(self):
        return self.name


class WhiskyBottleNote(UserContentModel):
    storage_item = models.ForeignKey(
        WhiskyStorageItem,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    note_date = models.DateField(verbose_name="Date")
    note = models.TextField(verbose_name="Note")

    class Meta:
        ordering = ["-note_date"]

    def __str__(self):
        return f"Note on {self.note_date} for {self.storage_item.whisky.name}"


class WhiskyDrinkingWindowAlert(UserContentModel):
    whisky = models.ForeignKey(Whisky, on_delete=models.CASCADE)
    alert_date = models.DateField(verbose_name="Alert Date")
    message = models.CharField(max_length=200, verbose_name="Message")
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-alert_date"]

    def __str__(self):
        return f"Alert: {self.whisky.name} - {self.message}"


class WhiskyReorderReminder(UserContentModel):
    whisky = models.ForeignKey(Whisky, on_delete=models.CASCADE)
    min_stock = models.PositiveIntegerField(default=1, verbose_name="Minimum Stock")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["whisky", "user"],
                name="unique_whiskyreorderreminder_whisky_user",
            ),
        ]

    def __str__(self):
        return f"Reorder: {self.whisky.name} (min {self.min_stock})"


# ---------------------------------------------------------------------------
# Vision extraction log
# ---------------------------------------------------------------------------


class WhiskyVisionExtractionLog(UserContentModel):
    whisky = models.ForeignKey(
        Whisky,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    image_count = models.PositiveIntegerField(default=0)
    raw_response = models.TextField(blank=True, default="")
    extracted_data = models.JSONField(default=dict, blank=True)
    confidence = models.CharField(max_length=20, blank=True, default="")
    extracted_fields = models.JSONField(default=list, blank=True)
    user_corrections = models.JSONField(default=dict, blank=True)
    was_successful = models.BooleanField(default=False)
    errors = models.TextField(blank=True, default="")
    model_used = models.CharField(max_length=100, blank=True, default="")
    processing_time_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Extraction {self.pk} - {'OK' if self.was_successful else 'FAIL'}"


# ---------------------------------------------------------------------------
# Price tracking
# ---------------------------------------------------------------------------


class WhiskySource(UserContentModel):
    name = models.CharField(max_length=200, verbose_name="Source")
    url = models.URLField(blank=True, default="", verbose_name="URL")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique_whiskysource_name_user",
            ),
        ]

    def __str__(self):
        return self.name


class Collection(UserContentModel):
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        null=True,
        related_name="whisky_collections",
        verbose_name="User",
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="whisky_collection_items",
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
    whiskies = models.ManyToManyField(
        "whisky.Whisky",
        blank=True,
        related_name="collections",
        verbose_name="Whiskies",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Collection"
        verbose_name_plural = "Collections"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "household"],
                name="unique_whisky_collection_name_per_household",
            ),
        ]

    def __str__(self):
        return self.name


class WhiskyPriceHistory(UserContentModel):
    whisky = models.ForeignKey(Whisky, on_delete=models.CASCADE)
    source = models.ForeignKey(
        WhiskySource, on_delete=models.SET_NULL, null=True, blank=True
    )
    price = models.DecimalField(max_digits=8, decimal_places=2)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name_plural = "price histories"

    def __str__(self):
        return f"{self.whisky.name} - {self.price} at {self.recorded_at}"

    @property
    def price_with_currency(self):
        return self.whisky.format_currency(self.price)


class WhiskyBottleMoveHistory(models.Model):
    """Records when a whisky bottle is moved to a different storage location."""

    storage_item = models.ForeignKey(
        WhiskyStorageItem,
        on_delete=models.CASCADE,
        related_name="move_history",
    )
    from_storage = models.ForeignKey(
        "storage.Storage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="From Storage",
    )
    from_row = models.PositiveIntegerField(null=True, blank=True)
    from_column = models.PositiveIntegerField(null=True, blank=True)
    to_storage = models.ForeignKey(
        "storage.Storage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="To Storage",
    )
    to_row = models.PositiveIntegerField(null=True, blank=True)
    to_column = models.PositiveIntegerField(null=True, blank=True)
    moved_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
    )

    class Meta:
        ordering = ["moved_at"]
        verbose_name = "Whisky Bottle Move History"
        verbose_name_plural = "Whisky Bottle Move Histories"

    def __str__(self):
        return (
            f"{self.storage_item} moved to {self.to_storage} on"
            f" {self.moved_at.date()}"
        )

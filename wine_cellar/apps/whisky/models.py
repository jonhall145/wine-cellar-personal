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
    SINGLE_MALT = "SM", _("Single Malt")
    BLENDED_MALT = "BM", _("Blended Malt")
    BLENDED = "BL", _("Blended")
    SINGLE_GRAIN = "SG", _("Single Grain")


class PeatedLevel(models.TextChoices):
    UNPEATED = "UP", _("Unpeated")
    PEATED = "PE", _("Peated")


class FillLevel(models.TextChoices):
    UNOPENED = "UN", _("Unopened")
    OPENED = "OP", _("Opened")
    DREG = "DR", _("Dreg")


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
    AMERICAN_OAK = "AO", _("American Oak")
    EUROPEAN_OAK = "EO", _("European Oak")
    JAPANESE_MIZUNARA = "JM", _("Japanese Mizunara")
    FRENCH_OAK = "FO", _("French Oak")
    OTHER = "OT", _("Other")


class PreviousContents(models.TextChoices):
    BOURBON = "BO", _("Bourbon")
    SHERRY_OLOROSO = "SO", _("Sherry (Oloroso)")
    SHERRY_PX = "SP", _("Sherry (Pedro Ximénez)")
    SHERRY_FINO = "SF", _("Sherry (Fino)")
    PORT = "PO", _("Port")
    RUM = "RU", _("Rum")
    WINE_RED = "WR", _("Wine (Red)")
    WINE_WHITE = "WW", _("Wine (White)")
    MADEIRA = "MA", _("Madeira")
    MARSALA = "MS", _("Marsala")
    VIRGIN_OAK = "VO", _("Virgin Oak")
    BEER = "BE", _("Beer / Ale")
    OTHER = "OT", _("Other")


class DistilleryStatus(models.TextChoices):
    ACTIVE = "AC", _("Active")
    SILENT = "SI", _("Silent")
    CLOSED = "CL", _("Closed")
    DEMOLISHED = "DE", _("Demolished")


class BottleSize(models.TextChoices):
    MINIATURE = "0.05", _("Miniature (50ml)")
    SAMPLE = "0.10", _("Sample (100ml)")
    SMALL = "0.20", _("Small (200ml)")
    HALF = "0.35", _("Half Bottle (350ml)")
    HALF_LITRE = "0.50", _("Half Litre (500ml)")
    STANDARD = "0.70", _("Standard (700ml)")
    LITRE = "1.00", _("Litre (1000ml)")
    MAGNUM = "1.50", _("Magnum (1500ml)")
    OTHER = "0.00", _("Other")


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
    name = models.CharField(max_length=100, verbose_name=_("Attribute"))

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

    name = models.CharField(max_length=200, verbose_name=_("Name"))
    whisky_type = models.CharField(
        max_length=2,
        choices=WhiskyType.choices,
        default=WhiskyType.SINGLE_MALT,
        verbose_name=_("Type"),
    )
    distillery = models.ForeignKey(
        Distillery,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Distillery"),
    )
    region = models.ForeignKey(
        WhiskyRegion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Region"),
    )
    country = models.CharField(max_length=2, default="XS", verbose_name=_("Country"))

    # Age & dates
    age_statement = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Age Statement"),
        help_text=_("Leave blank for NAS (No Age Statement)."),
    )
    vintage_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Distilled Year"),
    )
    bottled_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Bottled Year"),
    )

    # Character
    abv = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("ABV %"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    size = models.CharField(
        max_length=4,
        choices=BottleSize.choices,
        default=BottleSize.STANDARD,
        verbose_name=_("Bottle Size"),
    )
    peated_level = models.CharField(
        max_length=2,
        choices=PeatedLevel.choices,
        null=True,
        blank=True,
        verbose_name=_("Peated"),
    )
    cask_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Cask Type"),
        help_text=_("e.g. Bourbon, Sherry (Oloroso), Virgin Oak"),
    )
    cask_strength = models.BooleanField(
        default=False,
        verbose_name=_("Cask Strength"),
    )
    color = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Color"),
    )

    # Bottling details
    bottler = models.ForeignKey(
        Bottler,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Bottler"),
        help_text=_("Leave blank for Official Bottling (OB)."),
    )
    source = models.ForeignKey(
        "whisky.WhiskySource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Source"),
        help_text=_("Where this whisky was purchased."),
    )
    bottler_series = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Bottler Series"),
    )
    cask_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Cask Number"),
    )
    batch_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Batch Number"),
    )
    bottle_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Bottle Number"),
        help_text=_("e.g. 123/500"),
    )
    limited_edition = models.BooleanField(
        default=False,
        verbose_name=_("Limited Edition"),
    )
    release_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Release Year"),
    )

    # Tracking
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name=_("Rating"),
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Price"),
        validators=[MinValueValidator(0)],
    )
    comment = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Comment"),
    )
    owner = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Owner"),
    )

    # Relations
    attributes = models.ManyToManyField(
        WhiskyAttribute,
        blank=True,
        verbose_name=_("Attributes"),
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
    def get_price_with_currency(self):
        from wine_cellar.apps.user.views import get_user_settings

        if self.price is None:
            return None
        user_settings = get_user_settings(self.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )
        formatted_price = number_format(self.price, use_l10n=True)
        return f"{currency}{formatted_price}"

    @property
    def get_average_price_with_currency(self):
        from wine_cellar.apps.user.views import get_user_settings

        user_settings = get_user_settings(self.user)
        currency = settings.CURRENCY_SYMBOLS.get(
            getattr(user_settings, "currency", "EUR"), "€"
        )
        avg_price = self.whiskystorageitem_set.aggregate(avg_price=models.Avg("price"))[
            "avg_price"
        ]

        if avg_price is None:
            return None
        avg_price = avg_price.quantize(Decimal("0.00"))
        formatted_price = number_format(avg_price, use_l10n=True)
        return f"{currency}{formatted_price}"


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
        verbose_name=_("Maturation Order"),
        help_text=_("1 = primary cask, 2+ = subsequent casks/finishes"),
    )
    cask_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Cask Type"),
    )
    wood_type = models.CharField(
        max_length=2,
        choices=WoodType.choices,
        blank=True,
        default="",
        verbose_name=_("Wood Type"),
    )
    previous_contents = models.CharField(
        max_length=2,
        choices=PreviousContents.choices,
        verbose_name=_("Previous Contents"),
    )
    duration_years = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Duration (years)"),
    )
    is_finish = models.BooleanField(
        default=False,
        verbose_name=_("Finish"),
        help_text=_(
            "Check if this is a finishing cask rather than primary maturation."
        ),
    )
    cask_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Cask Number"),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Notes"),
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
        LABEL_FRONT = "LF", _("Front Label")
        LABEL_BACK = "LB", _("Back Label")

    whisky = models.ForeignKey(
        Whisky,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to=user_directory_path, verbose_name=_("Image"))
    thumbnail = models.ImageField(
        upload_to=user_directory_path,
        null=True,
        blank=True,
        verbose_name=_("Thumbnail"),
    )
    image_type = models.CharField(
        max_length=2,
        choices=ImageType.choices,
        default=ImageType.LABEL_FRONT,
        verbose_name=_("Image Type"),
    )
    is_primary = models.BooleanField(default=False, verbose_name=_("Primary Image"))
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, null=True, verbose_name=_("User")
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
        get_user_model(), on_delete=models.CASCADE, null=True, verbose_name=_("User")
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
    )
    fill_level = models.CharField(
        max_length=2,
        choices=FillLevel.choices,
        default=FillLevel.UNOPENED,
        verbose_name=_("Fill Level"),
    )
    opened_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date Opened"),
    )
    dreg_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Date Entered Dreg"),
    )
    owner = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Owner"),
    )

    class Meta:
        verbose_name = _("Whisky Bottle")
        verbose_name_plural = _("Whisky Bottles")
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
    date_consumed = models.DateField(verbose_name=_("Date"))
    tasting_notes = models.TextField(
        blank=True, default="", verbose_name=_("Tasting Notes")
    )
    rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        verbose_name=_("Rating"),
    )
    shared_with = models.CharField(
        max_length=200, blank=True, default="", verbose_name=_("Shared With")
    )
    occasion = models.CharField(
        max_length=200, blank=True, default="", verbose_name=_("Occasion")
    )

    class Meta:
        ordering = ["-date_consumed"]
        indexes = [
            models.Index(fields=["user", "date_consumed"], name="wdr_user_date_idx"),
        ]

    def __str__(self):
        return f"{self.whisky.name} on {self.date_consumed}"


class WhiskyWishlist(UserContentModel):
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    whisky_type = models.CharField(
        max_length=2,
        choices=WhiskyType.choices,
        null=True,
        blank=True,
        verbose_name=_("Type"),
    )
    distillery = models.ForeignKey(
        Distillery,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Distillery"),
    )
    region = models.ForeignKey(
        WhiskyRegion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Region"),
    )
    country = models.CharField(
        max_length=2, blank=True, default="", verbose_name=_("Country")
    )
    age_statement = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Age")
    )
    price_limit = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Max Price"),
    )
    notes = models.TextField(blank=True, default="", verbose_name=_("Notes"))
    priority = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        verbose_name=_("Priority"),
    )
    purchased = models.BooleanField(default=False, verbose_name=_("Purchased"))

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
    note_date = models.DateField(verbose_name=_("Date"))
    note = models.TextField(verbose_name=_("Note"))

    class Meta:
        ordering = ["-note_date"]

    def __str__(self):
        return f"Note on {self.note_date} for {self.storage_item.whisky.name}"


class WhiskyDrinkingWindowAlert(UserContentModel):
    whisky = models.ForeignKey(Whisky, on_delete=models.CASCADE)
    alert_date = models.DateField(verbose_name=_("Alert Date"))
    message = models.CharField(max_length=200, verbose_name=_("Message"))
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-alert_date"]

    def __str__(self):
        return f"Alert: {self.whisky.name} - {self.message}"


class WhiskyReorderReminder(UserContentModel):
    whisky = models.ForeignKey(Whisky, on_delete=models.CASCADE)
    min_stock = models.PositiveIntegerField(default=1, verbose_name=_("Minimum Stock"))
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
    name = models.CharField(max_length=200, verbose_name=_("Source"))
    url = models.URLField(blank=True, default="", verbose_name=_("URL"))

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
        verbose_name=_("User"),
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="whisky_collection_items",
        verbose_name=_("Household"),
    )
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    description = models.CharField(
        max_length=250,
        blank=True,
        default="",
        verbose_name=_("Description"),
    )
    color = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name=_("Color"),
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("Icon"),
    )
    whiskies = models.ManyToManyField(
        "whisky.Whisky",
        blank=True,
        related_name="collections",
        verbose_name=_("Whiskies"),
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("Collection")
        verbose_name_plural = _("Collections")
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

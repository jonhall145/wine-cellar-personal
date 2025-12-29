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


class UserContentModel(models.Model):
    """Abstract base model for user-owned content."""

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        null=True,
        verbose_name=_("User"),
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
    FRONT = "FR", _("Front")
    BACK = "BA", _("Back")
    LABEL_FRONT = "LF", _("Label Front")
    LABEL_BACK = "LB", _("Label Back")


class Size(UserContentModel):
    name = models.FloatField(verbose_name=_("Size"))

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
        return str(number_format(self.name, use_l10n=True))


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


class Source(UserContentModel):
    name = models.CharField(max_length=250, verbose_name=_("Source"))

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
    barcode = models.CharField(max_length=100, null=True, verbose_name=_("Barcode"))
    wine_type = models.CharField(max_length=2, choices=WineType, verbose_name=_("Type"))
    category = models.CharField(max_length=2, choices=Category, null=True, verbose_name=_("Category"))
    grapes = models.ManyToManyField(Grape, verbose_name=_("Grapes"))
    attributes = models.ManyToManyField(Attribute, verbose_name=_("Attributes"))
    food_pairings = models.ManyToManyField(FoodPairing, verbose_name=_("Food Pairings"))
    abv = models.FloatField(null=True, blank=True, verbose_name=_("ABV"))
    size = models.ForeignKey(Size, on_delete=models.SET_NULL, null=True, verbose_name=_("Size"))
    vintage = models.PositiveIntegerField(
        validators=[MinValueValidator(1900)],
        null=True,
        db_index=True,
        verbose_name=_("Vintage"),
    )
    drink_by = models.DateField(blank=True, null=True, db_index=True, verbose_name=_("Drink By"))
    comment = models.CharField(max_length=250, blank=True, verbose_name=_("Comment"))
    rating = models.PositiveIntegerField(
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name=_("Rating"),
    )
    country = models.CharField(
        max_length=3,
        choices={country.alpha_2: country.name for country in pycountry.countries},
        db_index=True,
        verbose_name=_("Country"),
    )
    vineyard = models.ManyToManyField(Vineyard, verbose_name=_("Vineyard"))
    source = models.ManyToManyField(Source, verbose_name=_("Source"))
    price = models.DecimalField(max_digits=6, decimal_places=2, null=True, verbose_name=_("Price"))

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
        return f"{formatted_price}{currency}"

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
        return f"{formatted_price}{currency}"

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
        return self.storageitem_set.filter(deleted=False)

    @property
    def image(self):
        i = self.wineimage_set.first()
        if not i:
            return static(settings.DEFAULT_WINE_IMAGE)
        return i.image.url

    @property
    def image_thumbnail(self):
        i = self.wineimage_set.filter(image_type=ImageType.FRONT)
        if not i:
            return static(settings.DEFAULT_WINE_IMAGE)
        front = i.first()
        if front.thumbnail:
            return front.thumbnail.url
        # return normal image as fallback
        return front.image.url

    @property
    def image_thumbnails(self):
        images = {img.image_type: img for img in self.wineimage_set.all()}
        order = [
            ImageType.FRONT,
            ImageType.BACK,
            ImageType.LABEL_FRONT,
            ImageType.LABEL_BACK,
        ]
        result = []
        for image_type in order:
            image = images.get(image_type)
            if image:
                src = image.thumbnail.url if image.thumbnail else image.image.url
                result.append(src)
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
    thumbnail = models.ImageField(upload_to=user_directory_path, blank=True, null=True, verbose_name=_("Thumbnail"))
    wine = models.ForeignKey(Wine, on_delete=models.CASCADE, verbose_name=_("Wine"))
    user = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, verbose_name=_("User"))
    image_type = models.CharField(
        max_length=3, choices=ImageType, default=ImageType.FRONT, verbose_name=_("Image Type")
    )

    class Meta:
        verbose_name = _("Wine Image")
        verbose_name_plural = _("Wine Images")

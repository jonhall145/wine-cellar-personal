from datetime import datetime

import pycountry
from django import forms
from django.core import validators
from django.forms import ImageField
from django.utils.text import slugify

from wine_cellar.apps.core.forms import (
    BaseDrinkRecordForm,
    BeverageBaseFormMixin,
    TomSelectMixin,
    native_select_widget,
)
from wine_cellar.apps.storage.models import Storage, get_app_type
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.whisky.models import (
    COMMON_CASK_TYPES,
    Bottler,
    BottleSize,
    Distillery,
    FillLevel,
    PeatedLevel,
    Whisky,
    WhiskyImage,
    WhiskyRegion,
    WhiskySource,
    WhiskyStorageItem,
    WhiskyType,
)
from wine_cellar.apps.wine.widgets import NoFilenameClearableFileInput


def get_whisky_owner_choices(household):
    whisky_owners = Whisky.objects.filter(household=household, deleted=False).exclude(
        owner=""
    )
    storage_item_owners = WhiskyStorageItem.objects.filter(household=household).exclude(
        owner=""
    )
    owners = sorted(
        set(whisky_owners.values_list("owner", flat=True).distinct())
        | set(storage_item_owners.values_list("owner", flat=True).distinct())
    )
    return [("", "---------")] + [(owner, owner) for owner in owners]


class CreatableModelChoiceField(forms.ModelChoiceField):
    """ModelChoiceField that allows TomSelect-created values."""

    def to_python(self, value):
        if isinstance(value, str) and value.startswith("tom_new_opt"):
            return value
        return super().to_python(value)

    def validate(self, value):
        if isinstance(value, str) and value.startswith("tom_new_opt"):
            return
        super().validate(value)


class CreatableMultipleChoiceField(forms.MultipleChoiceField):
    """MultipleChoiceField that allows TomSelect-created values not in choices."""

    def valid_value(self, value):
        return True


class WhiskyFormPostCleanMixin:
    def _post_clean(self):
        """Update tom-select config to prevent data loss on validation errors."""
        if hasattr(self, "cleaned_data"):
            distillery = self.cleaned_data.get("distillery")
            if distillery:
                self.set_tom_config(
                    name="distillery",
                    create=True,
                    items=[distillery.pk],
                    clear=False,
                )
            region = self.cleaned_data.get("region")
            if region:
                self.set_tom_config(
                    name="region",
                    create=True,
                    items=[region.pk],
                    clear=False,
                )
            bottler = self.cleaned_data.get("bottler")
            if bottler:
                self.set_tom_config(
                    name="bottler",
                    create=True,
                    items=[bottler.pk],
                    clear=False,
                )
            country = self.cleaned_data.get("country")
            if country:
                self.set_tom_config(
                    name="country",
                    items=[country],
                    clear=False,
                )
            cask_type = self.cleaned_data.get("cask_type")
            if cask_type:
                self.set_tom_config(
                    name="cask_type",
                    create=True,
                    items=[cask_type],
                    clear=False,
                )
            source = self.cleaned_data.get("source")
            if source:
                self.set_tom_config(
                    name="source",
                    create=True,
                    items=[source.pk],
                    clear=False,
                )
            owner = self.cleaned_data.get("owner")
            if owner:
                self.set_tom_config(
                    name="owner",
                    create=True,
                    items=[owner],
                    clear=False,
                )


class WhiskyBaseForm(
    BeverageBaseFormMixin,
    WhiskyFormPostCleanMixin,
    TomSelectMixin,
    forms.Form,
):
    image_fields_map = {
        "image_front_label": WhiskyImage.ImageType.LABEL_FRONT,
        "image_back_label": WhiskyImage.ImageType.LABEL_BACK,
    }
    image_model = WhiskyImage
    beverage_fk_name = "whisky"

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self._init_beverage_form(user)

        # Whisky-specific: source queryset for household
        self.fields["source"].queryset = WhiskySource.objects.filter(
            household=self.household
        ).order_by("name")

        self.fields["owner"].widget.choices = get_whisky_owner_choices(self.household)

    name = forms.CharField(
        max_length=200,
        help_text="Enter the name of the whisky.",
    )
    whisky_type = forms.ChoiceField(
        choices=WhiskyType.choices,
        initial=WhiskyType.SINGLE_MALT,
        help_text="Select the type of whisky.",
    )
    distillery = CreatableModelChoiceField(
        queryset=Distillery.objects.all().order_by("name"),
        required=False,
        help_text="Select the distillery.",
    )
    region = CreatableModelChoiceField(
        queryset=WhiskyRegion.objects.all().order_by("order", "name"),
        required=False,
        help_text="Select the whisky region.",
    )
    country = forms.ChoiceField(
        choices=(
            lambda: [("", "---------")]
            + [
                ("XS", "Scotland"),
                ("IE", "Ireland"),
                ("JP", "Japan"),
                ("XE", "England"),
                ("US", "United States"),
                ("XW", "Wales"),
            ]
            + [("", "───────────")]
            + [
                (c.alpha_2, c.name)
                for c in pycountry.countries
                if c.alpha_2 not in ("IE", "JP", "US")
            ]
        )(),
        initial="XS",
        help_text="Select the country of origin.",
    )
    age_statement = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(100),
        ],
        help_text="Age in years (leave blank for NAS).",
    )
    vintage_year = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(1800),
            validators.MaxValueValidator(datetime.now().year),
        ],
        help_text="Year the whisky was distilled.",
    )
    bottled_year = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(1800),
            validators.MaxValueValidator(datetime.now().year + 1),
        ],
        help_text="Year the whisky was bottled.",
    )
    abv = forms.FloatField(
        required=False,
        validators=[
            validators.MinValueValidator(0.0),
            validators.MaxValueValidator(100.0),
        ],
        help_text="Alcohol by volume percentage.",
        localize=True,
    )
    size = forms.ChoiceField(
        choices=BottleSize.choices,
        initial=BottleSize.STANDARD,
        help_text="Select the bottle size.",
    )
    peated_level = forms.ChoiceField(
        choices=[("", "---------")] + list(PeatedLevel.choices),
        required=False,
        label="Peated",
        help_text="Is this whisky peated?",
    )
    cask_type = CreatableMultipleChoiceField(
        choices=[(c, c) for c in COMMON_CASK_TYPES],
        required=False,
        widget=forms.SelectMultiple(),
        help_text="e.g. Bourbon, Sherry (Oloroso). Type to add custom.",
    )
    cask_strength = forms.BooleanField(
        required=False,
        label="Cask Strength",
    )
    color = forms.CharField(
        max_length=100,
        required=False,
        help_text="Color description.",
    )
    bottler = CreatableModelChoiceField(
        queryset=Bottler.objects.all().order_by("name"),
        required=False,
        help_text="Leave blank for Official Bottling (OB).",
    )
    source = CreatableModelChoiceField(
        queryset=WhiskySource.objects.none(),
        required=False,
        label="Source",
        help_text="Where was this whisky purchased?",
    )
    owner = forms.CharField(
        max_length=100,
        required=False,
        label="Owner",
        help_text="Who owns this bottle?",
        widget=forms.Select(),
    )
    bottler_series = forms.CharField(
        max_length=200,
        required=False,
        help_text="Bottler series or range name.",
    )
    cask_number = forms.CharField(
        max_length=100,
        required=False,
        help_text="Cask number if single cask.",
    )
    batch_number = forms.CharField(
        max_length=100,
        required=False,
        help_text="Batch or edition number.",
    )
    bottle_number = forms.CharField(
        max_length=100,
        required=False,
        help_text="Bottle number (e.g. 123/500).",
    )
    limited_edition = forms.BooleanField(
        required=False,
        help_text="Check if this is a limited edition.",
    )
    release_year = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(1800),
            validators.MaxValueValidator(datetime.now().year + 1),
        ],
        help_text="Year of release.",
    )
    rating = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        choices=[("", "-")] + [(i, f"{i} ★" if i else "0") for i in range(4)],
        help_text="Rate this whisky from 0 to 3 stars.",
    )
    price = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
    )
    barcode = forms.CharField(
        max_length=100,
        required=False,
        help_text="Enter the barcode number.",
    )
    comment = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea,
        help_text="Your thoughts and tasting notes.",
    )
    image_front_label = ImageField(
        widget=NoFilenameClearableFileInput,
        required=False,
        help_text="Upload a photo of the front label.",
    )
    image_back_label = ImageField(
        widget=NoFilenameClearableFileInput,
        required=False,
        help_text="Upload a photo of the back label.",
    )
    # Storage fields
    storage = forms.ModelChoiceField(
        queryset=Storage.objects.none(),
        required=False,
        help_text="Select where to store this bottle (optional).",
    )
    row = forms.IntegerField(
        required=False,
        min_value=1,
        label="Row",
        help_text="Select the row in the storage.",
        widget=native_select_widget(),
    )
    column = forms.IntegerField(
        required=False,
        min_value=1,
        label="Column",
        help_text="Select the column in the storage.",
        widget=native_select_widget(),
    )
    bottle_price = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        label="Bottle Price",
        help_text="Price paid for this specific bottle "
        "(if different from whisky price).",
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
    )
    is_gift = forms.BooleanField(
        required=False,
        label="Is Gift",
        help_text="Check if this bottle was received as a gift.",
    )
    gift_from = forms.CharField(
        max_length=100,
        required=False,
        label="Gift From",
        help_text="Enter who gave you this bottle.",
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        label="Occasion",
        help_text="Enter a special occasion this bottle is reserved for.",
    )
    fill_level = forms.ChoiceField(
        choices=FillLevel.choices,
        initial=FillLevel.UNOPENED,
        required=False,
        label="Fill Level",
        help_text="Current fill level of the bottle.",
    )

    def clean_cask_type(self):
        """Accept user-created cask types from TomSelect (supports multiple)."""
        values = self.data.getlist("cask_type", [])
        if not values:
            value = self.data.get("cask_type", "")
            values = [value] if value else []
        cleaned = []
        for v in values:
            v = v.strip()
            if not v:
                continue
            if v.startswith("tom_new_opt"):
                v = v.removeprefix("tom_new_opt").strip()
            if v:
                cleaned.append(v)
        return ", ".join(cleaned)

    def clean_region(self):
        """Allow creating new regions on the fly via TomSelect."""
        value = self.data.get("region", "")
        if not value:
            return None
        # TomSelect sends new items with "tom_new_opt" prefix
        if isinstance(value, str) and value.startswith("tom_new_opt"):
            name = value.removeprefix("tom_new_opt").strip()
            if not name:
                return None
            slug = slugify(name)
            country = self.data.get("country", "GB") or "GB"
            region, _ = WhiskyRegion.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "country": country},
            )
            return region
        # Otherwise, standard ModelChoiceField validation
        return self.fields["region"].clean(value)

    def clean_distillery(self):
        """Allow creating new distilleries on the fly via TomSelect."""
        value = self.data.get("distillery", "")
        if not value:
            return None
        if isinstance(value, str) and value.startswith("tom_new_opt"):
            name = value.removeprefix("tom_new_opt").strip()
            if not name:
                return None
            country = self.data.get("country", "XS") or "XS"
            distillery, _ = Distillery.objects.get_or_create(
                name=name,
                country=country,
                defaults={"is_user_created": True},
            )
            return distillery
        return self.fields["distillery"].clean(value)

    def clean_bottler(self):
        """Allow creating new bottlers on the fly via TomSelect."""
        value = self.data.get("bottler", "")
        if not value:
            return None
        if isinstance(value, str) and value.startswith("tom_new_opt"):
            name = value.removeprefix("tom_new_opt").strip()
            if not name:
                return None
            bottler, _ = Bottler.objects.get_or_create(
                name=name,
                defaults={"is_user_created": True},
            )
            return bottler
        return self.fields["bottler"].clean(value)

    def clean_source(self):
        """Allow creating new sources on the fly via TomSelect."""
        value = self.data.get("source", "")
        if not value:
            return None
        if isinstance(value, str) and value.startswith("tom_new_opt"):
            name = value.removeprefix("tom_new_opt").strip()
            if not name:
                return None
            source, _ = WhiskySource.objects.get_or_create(
                name=name,
                user=self.user,
                defaults={"household": self.household},
            )
            return source
        return self.fields["source"].clean(value)

    def clean_owner(self):
        """Accept user-created owner values from TomSelect."""
        value = self.data.get("owner", "")
        if not value:
            return ""
        if isinstance(value, str) and value.startswith("tom_new_opt"):
            return value.removeprefix("tom_new_opt").strip()
        return value.strip()


class WhiskyForm(WhiskyBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial = self.initial

        # Configure TomSelect dropdowns, preserving initial values
        distillery = initial.get("distillery")
        distillery_items = [distillery] if distillery else []
        self.set_tom_config(
            name="distillery",
            items=distillery_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=not distillery,
            placeholder="Search or add distillery...",
        )
        region = initial.get("region")
        region_items = [region] if region else []
        self.set_tom_config(
            name="region",
            items=region_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=not region,
            placeholder="Search or add region...",
        )
        bottler = initial.get("bottler")
        bottler_items = [bottler] if bottler else []
        self.set_tom_config(
            name="bottler",
            items=bottler_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=not bottler,
            placeholder="Search or add bottler...",
        )
        country = initial.get("country")
        self.set_tom_config(
            name="country",
            items=[country] if country else [],
            max_items=1,
            max_options=-1,
            search=True,
            clear=not country,
        )
        self.set_tom_config(
            name="cask_type",
            max_options=-1,
            search=True,
            create=True,
            placeholder="Search or add cask type...",
        )
        source = initial.get("source")
        source_items = [source] if source else []
        self.set_tom_config(
            name="source",
            items=source_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=not source,
            placeholder="Search or add source...",
        )
        owner = initial.get("owner", "")
        owner_items = [owner] if owner else []
        self.set_tom_config(
            name="owner",
            items=owner_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=not owner,
            placeholder="Search or add owner...",
        )


class WhiskyEditForm(WhiskyBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial = self.initial

        # Configure TomSelect dropdowns with initial values
        distillery = initial.get("distillery")
        if distillery:
            pk = distillery.pk if hasattr(distillery, "pk") else distillery
            distillery_items = [pk]
        else:
            distillery_items = []

        region = initial.get("region")
        if region:
            region_items = [region.pk if hasattr(region, "pk") else region]
        else:
            region_items = []

        bottler = initial.get("bottler")
        if bottler:
            bottler_items = [bottler.pk if hasattr(bottler, "pk") else bottler]
        else:
            bottler_items = []

        source = initial.get("source")
        if source:
            source_items = [source.pk if hasattr(source, "pk") else source]
        else:
            source_items = []

        owner = initial.get("owner", "")
        owner_items = [owner] if owner else []

        country = initial.get("country", "GB")

        self.set_tom_config(
            name="distillery",
            items=distillery_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=False,
        )
        self.set_tom_config(
            name="region",
            items=region_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=False,
        )
        self.set_tom_config(
            name="bottler",
            items=bottler_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=False,
        )
        self.set_tom_config(
            name="country",
            items=[country],
            max_items=1,
            max_options=-1,
            search=True,
            clear=False,
        )

        cask_type = initial.get("cask_type", "")
        cask_type_items = (
            [c.strip() for c in cask_type.split(",") if c.strip()] if cask_type else []
        )
        self.initial["cask_type"] = cask_type_items
        # Add any custom cask types as valid choices
        existing_choices = {c[0] for c in self.fields["cask_type"].choices}
        for ct in cask_type_items:
            if ct not in existing_choices:
                self.fields["cask_type"].choices.append((ct, ct))
        self.set_tom_config(
            name="cask_type",
            items=cask_type_items,
            max_options=-1,
            search=True,
            create=True,
            clear=False,
            placeholder="Search or add cask type...",
        )
        self.set_tom_config(
            name="source",
            items=source_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=False,
            placeholder="Search or add source...",
        )
        self.set_tom_config(
            name="owner",
            items=owner_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=bool(not owner),
            placeholder="Search or add owner...",
        )


class WhiskyFilterForm(TomSelectMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in (
            "distillery",
            "region",
            "country",
            "collection",
            "owner",
            "rating",
        ):
            if field_name in self.fields:
                self.set_tom_config(
                    name=field_name,
                    create=False,
                    max_options=-1,
                    clear=False,
                    placeholder="",
                    search=True,
                )


class WhiskyStorageItemFilterForm(TomSelectMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("storage", "owner"):
            if field_name in self.fields:
                self.set_tom_config(
                    name=field_name,
                    create=False,
                    max_options=-1,
                    clear=False,
                    placeholder="",
                    search=True,
                )
        if "fill_level" in self.fields:
            self.set_tom_config(
                name="fill_level",
                create=False,
                max_options=-1,
                clear=False,
                placeholder="",
                closeAfterSelect=False,
            )


class WhiskyStockAddForm(TomSelectMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        whisky = kwargs.pop("whisky", None)
        super().__init__(*args, **kwargs)

        # Default bottle price from whisky price
        if whisky and not self.initial.get("price"):
            self.initial["price"] = whisky.price
        household = get_active_household(user)

        self.fields["storage"].queryset = Storage.objects.filter(
            household=household, app_type=get_app_type()
        ).order_by("order", "created")

        self.fields["owner"].widget.choices = get_whisky_owner_choices(household)

        owner_val = self.initial.get("owner", "")
        owner_items = [owner_val] if owner_val else []
        self.set_tom_config(
            name="owner",
            create=True,
            items=owner_items,
            clear=bool(not owner_val),
            placeholder="Search or add owner...",
        )

    storage = forms.ModelChoiceField(
        queryset=Storage.objects.none(),
        help_text="Select where to store this bottle.",
    )
    row = forms.IntegerField(
        required=False,
        min_value=1,
        label="Row",
        widget=native_select_widget(),
    )
    column = forms.IntegerField(
        required=False,
        min_value=1,
        label="Column",
        widget=native_select_widget(),
    )
    price = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        label="Price",
        help_text="Price paid for this bottle.",
        localize=True,
    )
    is_gift = forms.BooleanField(
        required=False,
        label="Is Gift",
    )
    gift_from = forms.CharField(
        max_length=100,
        required=False,
        label="Gift From",
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        label="Occasion",
    )
    rating = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        choices=[("", "-")] + [(i, f"{i} ★" if i else "0") for i in range(4)],
        label="Rating",
    )
    fill_level = forms.ChoiceField(
        choices=FillLevel.choices,
        initial=FillLevel.UNOPENED,
        label="Fill Level",
        help_text="Current fill level of the bottle.",
    )
    owner = forms.CharField(
        max_length=100,
        required=False,
        label="Owner",
        widget=forms.Select(),
    )

    def clean_owner(self):
        """Accept user-created owner values from TomSelect."""
        value = self.data.get("owner", "")
        if not value:
            return ""
        if isinstance(value, str) and value.startswith("tom_new_opt"):
            return value.removeprefix("tom_new_opt").strip()
        return value.strip()


POST_DRINK_STATUS_CONSUMED = "consumed"


class WhiskyStorageItemSelect(forms.Select):
    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )
        storage_item = getattr(value, "instance", None)
        if storage_item is not None:
            option.setdefault("attrs", {})["data-fill-level"] = storage_item.fill_level
        return option


class WhiskyDrinkRecordForm(BaseDrinkRecordForm):
    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    beverage_label = "whisky"
    storage_item = forms.ModelChoiceField(
        queryset=WhiskyStorageItem.objects.none(),
        required=False,
        label="Bottle",
        help_text="Select which bottle you consumed (optional).",
        widget=WhiskyStorageItemSelect,
    )

    post_drink_status = forms.ChoiceField(
        required=False,
        initial=FillLevel.OPENED,
        label="Bottle status after drink",
        choices=(
            (
                POST_DRINK_STATUS_CONSUMED,
                "Consumed (remove from stock)",
            ),
            (FillLevel.OPENED, "Opened (keep in stock)"),
            (FillLevel.DREG, "Dreg (keep in stock)"),
        ),
        help_text="If you select a bottle, choose how that bottle "
        "should be updated.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["post_drink_status"].initial = self.get_default_post_drink_status()
        self.fields["post_drink_status"].widget.attrs.update(
            {
                "data-default-status": FillLevel.OPENED,
                "data-dreg-status": FillLevel.DREG,
            }
        )

    def get_default_post_drink_status(self):
        bottle = self.get_initial_storage_item()
        if bottle and bottle.fill_level == FillLevel.DREG:
            return FillLevel.DREG
        return FillLevel.OPENED

    def get_initial_storage_item(self):
        initial_storage_item = self.initial.get("storage_item")
        if not initial_storage_item:
            return None
        if isinstance(initial_storage_item, WhiskyStorageItem):
            return initial_storage_item
        return (
            self.fields["storage_item"].queryset.filter(pk=initial_storage_item).first()
        )

    def clean(self):
        cleaned_data = super().clean()
        bottle = cleaned_data.get("storage_item")
        post_drink_status = cleaned_data.get("post_drink_status")

        if bottle and not post_drink_status:
            self.add_error(
                "post_drink_status",
                "Choose how to update the selected bottle.",
            )

        return cleaned_data


class WhiskyWishlistForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        help_text="Name of the whisky you want to buy.",
    )
    whisky_type = forms.ChoiceField(
        choices=[("", "---------")] + list(WhiskyType.choices),
        required=False,
        help_text="Type of whisky.",
    )
    distillery = forms.ModelChoiceField(
        queryset=Distillery.objects.all().order_by("name"),
        required=False,
        help_text="Distillery.",
    )
    region = forms.ModelChoiceField(
        queryset=WhiskyRegion.objects.all().order_by("order", "name"),
        required=False,
        help_text="Region.",
    )
    age_statement = forms.IntegerField(
        required=False,
        help_text="Desired age in years.",
    )
    price_limit = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        help_text="Maximum price you want to pay.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text="Any notes about why you want this whisky.",
    )
    priority = forms.IntegerField(
        initial=1,
        validators=[validators.MinValueValidator(1), validators.MaxValueValidator(5)],
        help_text="Priority from 1 (low) to 5 (high).",
    )


class WhiskyPriceHistoryForm(forms.Form):
    price = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0.01,
        localize=True,
        widget=forms.TextInput(
            attrs={"inputmode": "decimal", "placeholder": "e.g. 54.99"}
        ),
        help_text="Current market price.",
    )
    source = forms.ModelChoiceField(
        queryset=WhiskySource.objects.none(),
        required=False,
        empty_label="Manual / no source",
        help_text="Optional retailer or source for this price.",
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        household = get_active_household(user)
        self.fields["source"].queryset = WhiskySource.objects.filter(
            household=household
        ).order_by("name")

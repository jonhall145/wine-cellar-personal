import json
from datetime import datetime

import pycountry
from django import forms
from django.conf import settings
from django.core import validators
from django.forms import ImageField
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.storage.models import Storage, get_app_type
from wine_cellar.apps.user.views import get_active_household, get_user_settings
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


image_fields_map = {
    "image_front_label": WhiskyImage.ImageType.LABEL_FRONT,
    "image_back_label": WhiskyImage.ImageType.LABEL_BACK,
}


class TomSelectMixin:
    def set_tom_config(
        self,
        name,
        create=False,
        items=[],
        max_items=None,
        max_options=50,
        clear=True,
        placeholder=None,
        closeAfterSelect=True,
        search=False,
    ):
        tom_config = {
            "create": create,
            "maxItems": max_items,
            "closeAfterSelect": closeAfterSelect,
        }
        if items:
            tom_config["items"] = items
        if max_options:
            tom_config["maxOptions"] = None if max_options == -1 else max_options
        if placeholder is not None:
            tom_config["placeholder"] = placeholder

        self.fields[name].widget.attrs.update(
            {
                "data-tom_config": json.dumps(tom_config),
                "data-clear": "true" if clear else "false",
                "data-search": "true" if search else "false",
            }
        )


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


class WhiskyBaseForm(WhiskyFormPostCleanMixin, TomSelectMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        household = get_active_household(user)
        self.user = user
        self.household = household
        user_settings = get_user_settings(user)
        self.fields["price"].help_text = _(
            "Enter the price of the bottle in %(currency)s."
        ) % {"currency": settings.CURRENCY_SYMBOLS[user_settings.currency]}
        self.fields["rrp"].help_text = _("Enter the RRP in %(currency)s.") % {
            "currency": settings.CURRENCY_SYMBOLS[user_settings.currency]
        }

        # Configure source queryset for household
        self.fields["source"].queryset = WhiskySource.objects.filter(
            household=household
        ).order_by("name")

        # Populate owner choices from existing values
        existing_owners = (
            Whisky.objects.filter(household=household)
            .exclude(owner="")
            .values_list("owner", flat=True)
            .distinct()
            .order_by("owner")
        )
        owner_choices = [("", "---------")] + [(o, o) for o in existing_owners]
        self.fields["owner"].widget.choices = owner_choices

        # Configure storage field for household's storages
        if "storage" in self.fields:
            self.fields["storage"].queryset = Storage.objects.filter(
                household=household, app_type=get_app_type()
            ).order_by("order", "created")

        # Populate image fields with existing images for edit forms
        for field_name, image_type_code in image_fields_map.items():
            field = self.fields.get(field_name)
            if not field:
                continue
            if getattr(self, "initial", None):
                whisky_id = self.initial.get("id")
                if whisky_id:
                    image_obj = (
                        WhiskyImage.objects.filter(
                            whisky=whisky_id, image_type=image_type_code
                        )
                        .order_by("-id")
                        .first()
                    )
                    if image_obj:
                        self.initial[field_name] = image_obj.image
                        preview_url = (
                            image_obj.thumbnail.url
                            if image_obj.thumbnail
                            else image_obj.image.url
                        )
                        self.fields[field_name].widget.attrs[
                            "data-existing-url"
                        ] = preview_url

    name = forms.CharField(
        max_length=200,
        help_text=_("Enter the name of the whisky."),
    )
    whisky_type = forms.ChoiceField(
        choices=WhiskyType.choices,
        initial=WhiskyType.SINGLE_MALT,
        help_text=_("Select the type of whisky."),
    )
    distillery = CreatableModelChoiceField(
        queryset=Distillery.objects.all().order_by("name"),
        required=False,
        help_text=_("Select the distillery."),
    )
    region = CreatableModelChoiceField(
        queryset=WhiskyRegion.objects.all().order_by("order", "name"),
        required=False,
        help_text=_("Select the whisky region."),
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
        help_text=_("Select the country of origin."),
    )
    age_statement = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(100),
        ],
        help_text=_("Age in years (leave blank for NAS)."),
    )
    vintage_year = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(1800),
            validators.MaxValueValidator(datetime.now().year),
        ],
        help_text=_("Year the whisky was distilled."),
    )
    bottled_year = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(1800),
            validators.MaxValueValidator(datetime.now().year + 1),
        ],
        help_text=_("Year the whisky was bottled."),
    )
    abv = forms.FloatField(
        required=False,
        validators=[
            validators.MinValueValidator(0.0),
            validators.MaxValueValidator(100.0),
        ],
        help_text=_("Alcohol by volume percentage."),
        localize=True,
    )
    size = forms.ChoiceField(
        choices=BottleSize.choices,
        initial=BottleSize.STANDARD,
        help_text=_("Select the bottle size."),
    )
    peated_level = forms.ChoiceField(
        choices=[("", "---------")] + list(PeatedLevel.choices),
        required=False,
        label=_("Peated"),
        help_text=_("Is this whisky peated?"),
    )
    cask_type = forms.MultipleChoiceField(
        choices=[(c, c) for c in COMMON_CASK_TYPES],
        required=False,
        widget=forms.SelectMultiple(),
        help_text=_("e.g. Bourbon, Sherry (Oloroso). Type to add custom."),
    )
    color = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Color description."),
    )
    bottler = CreatableModelChoiceField(
        queryset=Bottler.objects.all().order_by("name"),
        required=False,
        help_text=_("Leave blank for Official Bottling (OB)."),
    )
    source = CreatableModelChoiceField(
        queryset=WhiskySource.objects.none(),
        required=False,
        label=_("Source"),
        help_text=_("Where was this whisky purchased?"),
    )
    owner = forms.CharField(
        max_length=100,
        required=False,
        label=_("Owner"),
        help_text=_("Who owns this bottle?"),
        widget=forms.Select(),
    )
    bottler_series = forms.CharField(
        max_length=200,
        required=False,
        help_text=_("Bottler series or range name."),
    )
    cask_number = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Cask number if single cask."),
    )
    batch_number = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Batch or edition number."),
    )
    bottle_number = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Bottle number (e.g. 123/500)."),
    )
    limited_edition = forms.BooleanField(
        required=False,
        help_text=_("Check if this is a limited edition."),
    )
    release_year = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(1800),
            validators.MaxValueValidator(datetime.now().year + 1),
        ],
        help_text=_("Year of release."),
    )
    rating = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        choices=[("", "-")] + [(i, f"{i} ★" if i else "0") for i in range(4)],
        help_text=_("Rate this whisky from 0 to 3 stars."),
    )
    price = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        localize=True,
    )
    rrp = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        localize=True,
    )
    barcode = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Enter the barcode number."),
    )
    comment = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea,
        help_text=_("Your thoughts and tasting notes."),
    )
    image_front_label = ImageField(
        widget=NoFilenameClearableFileInput,
        required=False,
        help_text=_("Upload a photo of the front label."),
    )
    image_back_label = ImageField(
        widget=NoFilenameClearableFileInput,
        required=False,
        help_text=_("Upload a photo of the back label."),
    )
    # Storage fields
    storage = forms.ModelChoiceField(
        queryset=Storage.objects.none(),
        required=False,
        help_text=_("Select where to store this bottle (optional)."),
    )
    row = forms.IntegerField(
        required=False,
        min_value=1,
        label=_("Row"),
        help_text=_("Select the row in the storage."),
        widget=forms.Select(),
    )
    column = forms.IntegerField(
        required=False,
        min_value=1,
        label=_("Column"),
        help_text=_("Select the column in the storage."),
        widget=forms.Select(),
    )
    bottle_price = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        label=_("Bottle Price"),
        help_text=_(
            "Price paid for this specific bottle (if different from whisky price)."
        ),
        localize=True,
    )
    is_gift = forms.BooleanField(
        required=False,
        label=_("Is Gift"),
        help_text=_("Check if this bottle was received as a gift."),
    )
    gift_from = forms.CharField(
        max_length=100,
        required=False,
        label=_("Gift From"),
        help_text=_("Enter who gave you this bottle."),
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        label=_("Occasion"),
        help_text=_("Enter a special occasion this bottle is reserved for."),
    )
    fill_level = forms.ChoiceField(
        choices=FillLevel.choices,
        initial=FillLevel.UNOPENED,
        required=False,
        label=_("Fill Level"),
        help_text=_("Current fill level of the bottle."),
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
            placeholder=str(_("Search or add distillery...")),
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
            placeholder=str(_("Search or add region...")),
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
            placeholder=str(_("Search or add bottler...")),
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
            placeholder=str(_("Search or add cask type...")),
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
            placeholder=str(_("Search or add source...")),
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
            placeholder=str(_("Search or add owner...")),
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
        )
        self.set_tom_config(
            name="region",
            items=region_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
        )
        self.set_tom_config(
            name="bottler",
            items=bottler_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
        )
        self.set_tom_config(
            name="country",
            items=[country],
            max_items=1,
            max_options=-1,
            search=True,
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
            placeholder=str(_("Search or add cask type...")),
        )
        self.set_tom_config(
            name="source",
            items=source_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            placeholder=str(_("Search or add source...")),
        )
        self.set_tom_config(
            name="owner",
            items=owner_items,
            max_items=1,
            max_options=-1,
            search=True,
            create=True,
            clear=bool(not owner),
            placeholder=str(_("Search or add owner...")),
        )


class WhiskyStockAddForm(TomSelectMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        whisky = kwargs.pop("whisky", None)
        super().__init__(*args, **kwargs)

        # Default bottle price from whisky RRP or price
        if whisky and not self.initial.get("price"):
            self.initial["price"] = whisky.rrp or whisky.price
        household = get_active_household(user)

        self.fields["storage"].queryset = Storage.objects.filter(
            household=household, app_type=get_app_type()
        ).order_by("order", "created")

        # Populate owner choices from existing values
        existing_owners = (
            WhiskyStorageItem.objects.filter(household=household)
            .exclude(owner="")
            .values_list("owner", flat=True)
            .distinct()
            .order_by("owner")
        )
        owner_choices = [("", "---------")] + [(o, o) for o in existing_owners]
        self.fields["owner"].widget.choices = owner_choices

        # Also include owners from Whisky model
        whisky_owners = (
            Whisky.objects.filter(household=household)
            .exclude(owner="")
            .values_list("owner", flat=True)
            .distinct()
        )
        all_owners = sorted(set(existing_owners) | set(whisky_owners))
        owner_choices = [("", "---------")] + [(o, o) for o in all_owners]
        self.fields["owner"].widget.choices = owner_choices

        owner_val = self.initial.get("owner", "")
        owner_items = [owner_val] if owner_val else []
        self.set_tom_config(
            name="owner",
            create=True,
            items=owner_items,
            clear=bool(not owner_val),
            placeholder=str(_("Search or add owner...")),
        )

    storage = forms.ModelChoiceField(
        queryset=Storage.objects.none(),
        help_text=_("Select where to store this bottle."),
    )
    row = forms.IntegerField(
        required=False,
        min_value=1,
        label=_("Row"),
        widget=forms.Select(),
    )
    column = forms.IntegerField(
        required=False,
        min_value=1,
        label=_("Column"),
        widget=forms.Select(),
    )
    price = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        label=_("Price"),
        help_text=_("Price paid for this bottle."),
        localize=True,
    )
    is_gift = forms.BooleanField(
        required=False,
        label=_("Is Gift"),
    )
    gift_from = forms.CharField(
        max_length=100,
        required=False,
        label=_("Gift From"),
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        label=_("Occasion"),
    )
    rating = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        choices=[("", "-")] + [(i, f"{i} ★" if i else "0") for i in range(4)],
        label=_("Rating"),
    )
    fill_level = forms.ChoiceField(
        choices=FillLevel.choices,
        initial=FillLevel.UNOPENED,
        label=_("Fill Level"),
        help_text=_("Current fill level of the bottle."),
    )
    owner = forms.CharField(
        max_length=100,
        required=False,
        label=_("Owner"),
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


class WhiskyDrinkRecordForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.whisky = kwargs.pop("whisky", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Set up bottle selection queryset
        if self.whisky and self.user:
            available_bottles = (
                WhiskyStorageItem.objects.filter(
                    whisky=self.whisky, user=self.user, deleted=False
                )
                .select_related("storage")
                .order_by("storage__name", "row", "column")
            )

            self.fields["storage_item"].queryset = available_bottles

            # Update help text with count
            count = available_bottles.count()
            if count == 0:
                self.fields["storage_item"].help_text = _(
                    "No bottles available in storage for this whisky."
                )
            else:
                self.fields["storage_item"].help_text = _(
                    "Select which bottle you consumed (%(count)d available)."
                ) % {"count": count}

    storage_item = forms.ModelChoiceField(
        queryset=WhiskyStorageItem.objects.none(),
        required=False,
        label=_("Bottle"),
        help_text=_("Select which bottle you consumed (optional)."),
    )
    date_consumed = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        help_text=_("When did you drink this whisky?"),
    )
    tasting_notes = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text=_("Your tasting notes for this whisky."),
    )
    rating = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        choices=[("", "-")] + [(i, f"{i} ★" if i else "0") for i in range(4)],
        help_text=_("Rate this whisky from 0 to 3 stars."),
    )
    shared_with = forms.CharField(
        max_length=250,
        required=False,
        help_text=_("Who did you share this whisky with?"),
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("What was the occasion?"),
    )

    def clean_storage_item(self):
        """Validate bottle selection."""
        bottle = self.cleaned_data.get("storage_item")

        # Check bottle not already deleted
        if bottle and bottle.deleted:
            raise forms.ValidationError(_("This bottle has already been consumed."))

        # Check bottle belongs to the correct whisky
        if bottle and self.whisky and bottle.whisky != self.whisky:
            raise forms.ValidationError(_("Invalid bottle selection."))

        return bottle


class WhiskyWishlistForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        help_text=_("Name of the whisky you want to buy."),
    )
    whisky_type = forms.ChoiceField(
        choices=[("", "---------")] + list(WhiskyType.choices),
        required=False,
        help_text=_("Type of whisky."),
    )
    distillery = forms.ModelChoiceField(
        queryset=Distillery.objects.all().order_by("name"),
        required=False,
        help_text=_("Distillery."),
    )
    region = forms.ModelChoiceField(
        queryset=WhiskyRegion.objects.all().order_by("order", "name"),
        required=False,
        help_text=_("Region."),
    )
    age_statement = forms.IntegerField(
        required=False,
        help_text=_("Desired age in years."),
    )
    price_limit = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        help_text=_("Maximum price you want to pay."),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text=_("Any notes about why you want this whisky."),
    )
    priority = forms.IntegerField(
        initial=1,
        validators=[validators.MinValueValidator(1), validators.MaxValueValidator(5)],
        help_text=_("Priority from 1 (low) to 5 (high)."),
    )


class WhiskySaleAlertForm(forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        household = get_active_household(user)

        self.fields["source"].queryset = WhiskySource.objects.filter(
            household=household
        ).order_by("name")

    source = forms.ModelChoiceField(
        queryset=WhiskySource.objects.none(),
        required=False,
        label=_("Source"),
        help_text=_("Leave blank to monitor all sources"),
    )
    threshold_percent = forms.IntegerField(
        initial=10,
        validators=[validators.MinValueValidator(1), validators.MaxValueValidator(100)],
        label=_("Price Drop Threshold (%)"),
        help_text=_("Alert when price drops by this percentage"),
    )
    threshold_price = forms.DecimalField(
        required=False,
        max_digits=8,
        decimal_places=2,
        label=_("Target Price"),
        help_text=_("Alert when price drops to or below this amount"),
    )


class BottleNoteForm(forms.Form):
    note_date = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        help_text=_("Date of this note."),
    )
    note = forms.CharField(
        widget=forms.Textarea,
        help_text=_("Your note about this bottle."),
    )


class ReorderReminderForm(forms.Form):
    min_stock = forms.IntegerField(
        min_value=1,
        initial=1,
        help_text=_("Alert when stock drops to or below this number."),
    )

import json
from datetime import datetime

import pycountry
from django import forms
from django.core import validators
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q
from django.forms import ImageField

from wine_cellar.apps.core.forms import (
    BaseDrinkRecordForm,
    BeverageBaseFormMixin,
    TomSelectMixin,
    native_select_widget,
)
from wine_cellar.apps.storage.models import Storage, StorageItem
from wine_cellar.apps.wine.fields import OpenMultipleChoiceField
from wine_cellar.apps.wine.models import (
    Appellation,
    Attribute,
    Category,
    FoodPairing,
    Grape,
    ImageType,
    SizeChoices,
    Source,
    Vineyard,
    WineImage,
    WineType,
)
from wine_cellar.apps.wine.widgets import NoFilenameClearableFileInput


class WineFormPostCleanMixin:
    def _post_clean(self):
        """Update tom-select config to prevent data loss in the form"""
        if hasattr(self, "cleaned_data"):
            wine_type = self.cleaned_data.get("wine_type")
            if wine_type and "wine_type" in self.fields:
                if isinstance(wine_type, list):
                    # Filter form: MultipleChoiceField returns a list
                    self.set_tom_config(
                        name="wine_type",
                        items=wine_type,
                        create=False,
                        clear=False,
                    )
                else:
                    # Edit form: CharField returns a single string
                    self.set_tom_config(
                        name="wine_type",
                        items=[wine_type],
                        max_items=1,
                        create=False,
                        clear=False,
                    )
            grapes = self.cleaned_data.get("grapes", [])
            if grapes:
                self.set_tom_config(
                    name="grapes",
                    create=True,
                    items=[g.pk for g in grapes],
                    clear=False,
                )
            attributes = self.cleaned_data.get("attributes", [])
            if attributes:
                self.set_tom_config(
                    name="attributes",
                    create=True,
                    items=[a.pk for a in attributes],
                    clear=False,
                )
            food_pairings = self.cleaned_data.get("food_pairings", [])
            if food_pairings:
                self.set_tom_config(
                    name="food_pairings",
                    create=True,
                    items=[f.pk for f in food_pairings],
                    clear=False,
                )
            source = self.cleaned_data.get("source", [])
            if source:
                self.set_tom_config(
                    name="source",
                    create=True,
                    items=[s.pk for s in source],
                    clear=False,
                )
            vineyard = self.cleaned_data.get("vineyard", [])
            if vineyard:
                self.set_tom_config(
                    name="vineyard",
                    items=[v.pk for v in vineyard],
                    create=True,
                    clear=False,
                )
            country = self.cleaned_data.get("country")
            if country:
                self.set_tom_config(
                    name="country",
                    items=[country],
                    max_items=1,
                    max_options=-1,
                    clear=False,
                )
            appellation = self.cleaned_data.get("appellation")
            if appellation and "appellation" in self.fields:
                # Handle both Appellation object and string/int (from filters)
                app_pk = appellation.pk if hasattr(appellation, "pk") else appellation
                self.set_tom_config(
                    name="appellation",
                    items=[app_pk],
                    max_items=1,
                    max_options=-1,
                    clear=False,
                )


class WineBaseForm(
    BeverageBaseFormMixin, TomSelectMixin, WineFormPostCleanMixin, forms.Form
):
    image_fields_map = {
        "image_front_label": ImageType.LABEL_FRONT,
        "image_back_label": ImageType.LABEL_BACK,
    }
    image_model = WineImage
    beverage_fk_name = "wine"

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self._init_beverage_form(user)

        # Wine-specific: M2M user fields
        household = self.household
        user_fields = [
            "vineyard",
            "attributes",
            "grapes",
            "food_pairings",
            "source",
        ]
        for user_field in user_fields:
            model = self.fields[user_field].queryset.model
            self.fields[user_field].queryset = model.objects.filter(
                Q(household__isnull=True) | Q(household=household)
            )
            self.fields[user_field].user = user

        # Wine-specific: drink window year choices
        current_year = datetime.now().year
        year_choices = [("", "---------"), (0, "Now")]
        year_choices += [
            (y, str(y)) for y in range(current_year - 5, current_year + 51)
        ]
        self.fields["drink_from"].choices = year_choices
        self.fields["drink_to"].choices = year_choices

        # Wine-specific: appellation->country mapping for JS
        if "appellation" in self.fields:
            country_map = {
                str(pk): country
                for pk, country in Appellation.objects.values_list("pk", "country")
            }
            self.fields["appellation"].widget.attrs["data-appellation-countries"] = (
                json.dumps(country_map)
            )

    class Meta:
        abstract = True

    name = forms.CharField(
        max_length=100,
        help_text="Enter the name of the wine as indicated on the label.",
    )
    wine_type = forms.CharField(
        max_length=2,
        widget=forms.Select(choices=WineType),
        help_text="Select the type of wine from the dropdown.",
    )
    category = forms.CharField(
        label="Sweetness",
        required=False,
        max_length=2,
        widget=forms.Select(choices=[("", "---------")] + list(Category.choices)),
        help_text="Select the sweetness level of the wine.",
    )
    country = forms.CharField(
        max_length=250,
        widget=forms.Select(
            choices={country.alpha_2: country.name for country in pycountry.countries},
        ),
        help_text="Select the country the wine was produced in "
        "as indicated on the label.",
    )
    subregion = forms.CharField(
        max_length=100,
        required=False,
        help_text="Enter the subregion or appellation of the wine, "
        "e.g. Douro Valley, Dao.",
    )
    appellation = forms.ModelChoiceField(
        queryset=Appellation.objects.all().order_by("country", "name"),
        required=False,
        help_text="Select a known wine region for map display. "
        "If your region is not listed, use subregion field above.",
    )
    size = forms.CharField(
        max_length=2,
        required=False,
        initial=SizeChoices.STANDARD,
        widget=forms.Select(choices=SizeChoices.choices),
        label="Size",
        help_text="Select the bottle size.",
    )
    abv = forms.FloatField(
        required=False,
        validators=[
            validators.MinValueValidator(0.0),
            validators.MaxValueValidator(100.0),
        ],
        help_text="Please enter the percentage of alcohol in the"
        " wine. This information is typically found on the label and indicates the"
        " strength of the wine.",
        localize=True,
    )
    vintage = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(1900),
            validators.MaxValueValidator(datetime.now().year),
        ],
        help_text="Enter the year the grapes were harvested to produce "
        "the wine. Typically, vintage years are prominently "
        "displayed on wine labels.",
    )
    grapes = OpenMultipleChoiceField(
        required=False,
        queryset=Grape.objects.none(),
        field_name="name",
        help_text="Select or add the grape varieties used to produce the wine. You can "
        "select multiple options if applicable.",
    )
    attributes = OpenMultipleChoiceField(
        required=False,
        queryset=Attribute.objects.none(),
        field_name="name",
        help_text="Add any attributes that apply to this wine, such as"
        " natural, retsina or organic.",
    )
    drink_from = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        label="Drink From",
        help_text="When this wine is ready to drink.",
    )
    drink_to = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        label="Drink Until",
        help_text="When this wine should be drunk by.",
    )
    food_pairings = OpenMultipleChoiceField(
        required=False,
        queryset=FoodPairing.objects.none(),
        field_name="name",
        help_text="Enter dishes, cuisines, or ingredients that complement the "
        "flavors of this wine.",
    )
    vineyard = OpenMultipleChoiceField(
        label="Vineyard",
        required=False,
        queryset=Vineyard.objects.none(),
        field_name="name",
        help_text="Enter the names of the vineyards which produced the wine.",
    )
    source = OpenMultipleChoiceField(
        required=False,
        queryset=Source.objects.none(),
        field_name="name",
        help_text="Where did you get the wine from?",
    )
    price = forms.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal"}),
    )
    price_url = forms.URLField(
        required=False,
        max_length=500,
        assume_scheme="https",
        help_text="Product page URL for automatic price tracking.",
    )
    barcode = forms.CharField(
        max_length=100,
        required=False,
        help_text="Enter the barcode number of the wine as indicated on the label.",
    )
    barcode_2 = forms.CharField(
        max_length=100,
        required=False,
        label="Additional Barcode",
        help_text="Enter an additional barcode (e.g. from a different region/format).",  # noqa: E501
    )
    comment = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.Textarea,
        help_text="Share your thoughts, tasting experiences, or any anecdotes"
        " related to this wine.",
    )
    rating = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        choices=[("", "-")] + [(i, f"{i} ★" if i else "0") for i in range(4)],
        help_text="Rate this wine from 0 to 3 stars.",
    )
    image_front_label = ImageField(
        widget=NoFilenameClearableFileInput,
        required=False,
        help_text="Upload a photo of the front of the bottle label.",
    )
    image_back_label = ImageField(
        widget=NoFilenameClearableFileInput,
        required=False,
        help_text="Upload a photo of the back of the bottle label.",
    )
    # Storage fields for adding bottle to cellar
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
        max_digits=6,
        decimal_places=2,
        label="Bottle Price",
        help_text="Price paid for this specific bottle (if different from wine price).",
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
    form_step = forms.IntegerField(
        widget=forms.HiddenInput(),
        label="",
        required=False,
        validators=[
            validators.MinValueValidator(0),
            validators.MaxValueValidator(4),
        ],
    )


class WineForm(WineBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["form_step"] = 0
        self.set_tom_config(name="grapes", create=True)
        self.set_tom_config(name="attributes", create=True)
        self.set_tom_config(name="food_pairings", create=True)
        self.set_tom_config(name="source", create=True)
        self.set_tom_config(name="vineyard", create=True)
        self.set_tom_config(
            name="appellation",
            max_items=1,
            max_options=-1,
            search=True,
            placeholder="Search appellations...",
        )

        # Include initial country value in TomSelect config to preserve it
        # (TomSelect's clear() would otherwise wipe pre-filled values from label scan)
        initial_country = self.initial.get("country")
        country_items = [initial_country] if initial_country else []
        self.set_tom_config(
            name="country",
            items=country_items,
            max_items=1,
            max_options=-1,
            search=True,
            clear=False,  # Don't clear - preserves initial value from label scan
        )


class WineEditForm(WineBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial = self.initial

        category = [initial["category"]]
        grapes = [grape.pk for grape in initial["grapes"]]
        attributes = [a.pk for a in initial["attributes"]]
        food_pairing = [f.pk for f in initial["food_pairings"]]
        source = [s.pk for s in initial["source"]]
        vineyard = [v.pk for v in initial["vineyard"]]
        country = initial["country"]
        # Size is a FK to Size model - model_to_dict returns the PK
        size_pk = initial.get("size")
        if size_pk:
            from wine_cellar.apps.wine.models import Size

            try:
                size_instance = Size.objects.get(pk=size_pk)
                self.initial["size"] = size_instance.name
            except (Size.DoesNotExist, TypeError):
                # TypeError handles case where size_pk is already a Size object
                if hasattr(size_pk, "name"):
                    self.initial["size"] = size_pk.name

        self.fields["category"].widget.attrs.update(
            {
                "data-tom_config": json.dumps(
                    {"create": "false", "items": category, "maxItems": 1}
                ),
            }
        )
        self.fields["grapes"].widget.attrs.update(
            {
                "data-tom_config": json.dumps(
                    {"create": True, "items": grapes, "maxItems": None}
                ),
            }
        )
        self.fields["attributes"].widget.attrs.update(
            {
                "data-tom_config": json.dumps(
                    {"create": True, "items": attributes, "maxItems": None}
                ),
            }
        )
        self.fields["food_pairings"].widget.attrs.update(
            {
                "data-tom_config": json.dumps(
                    {"create": True, "items": food_pairing, "maxItems": None}
                ),
            }
        )
        self.fields["source"].widget.attrs.update(
            {
                "data-tom_config": json.dumps(
                    {"create": True, "items": source, "maxItems": None}
                ),
            }
        )
        self.fields["vineyard"].widget.attrs.update(
            {
                "data-tom_config": json.dumps(
                    {
                        "create": True,
                        "items": vineyard,
                        "maxItems": None,
                        "maxOptions": None,
                    }
                ),
            }
        )
        self.fields["country"].widget.attrs.update(
            {
                "data-tom_config": json.dumps(
                    {
                        "create": False,
                        "items": country,
                        "maxItems": 1,
                        "maxOptions": None,
                    }
                ),
            }
        )
        # Configure appellation TomSelect
        appellation = initial.get("appellation")
        # Handle both int (from model_to_dict) and Appellation object
        if appellation:
            appellation_items = [
                appellation.pk if hasattr(appellation, "pk") else appellation
            ]
        else:
            appellation_items = []
        self.fields["appellation"].widget.attrs.update(
            {
                "data-tom_config": json.dumps(
                    {
                        "create": False,
                        "items": appellation_items,
                        "maxItems": 1,
                        "maxOptions": None,
                    }
                ),
                "data-search": "true",
            }
        )


class WineFilterForm(TomSelectMixin, WineFormPostCleanMixin, forms.Form):
    template_name = "wine_filter_field.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["form_step"] = 0
        self.set_tom_config(name="wine_type", create=False)
        self.set_tom_config(name="grapes", create=False)
        self.set_tom_config(name="food_pairings", create=False)
        self.set_tom_config(name="source", create=False)
        self.set_tom_config(name="vineyard", create=False)
        self.set_tom_config(name="attributes", create=False)
        self.set_tom_config(
            name="country", create=False, max_options=-1, placeholder="", search=True
        )


class DrinkRecordForm(BaseDrinkRecordForm):
    storage_item_model = StorageItem
    beverage_fk_name = "wine"
    beverage_label = "wine"


class WishlistForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        help_text="Name of the wine you want to buy.",
    )
    wine_type = forms.CharField(
        max_length=2,
        required=False,
        widget=forms.Select(choices=[("", "---------")] + list(WineType.choices)),
        help_text="Type of wine.",
    )
    country = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.Select(
            choices=[("", "---------")]
            + [(c.alpha_2, c.name) for c in pycountry.countries],
        ),
        help_text="Country of origin.",
    )
    subregion = forms.CharField(
        max_length=100,
        required=False,
        help_text="Subregion or appellation.",
    )
    vintage = forms.IntegerField(
        required=False,
        help_text="Desired vintage year.",
    )
    price_limit = forms.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        help_text="Maximum price you want to pay.",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text="Any notes about why you want this wine.",
    )
    priority = forms.IntegerField(
        initial=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Priority from 1 (low) to 5 (high).",
    )


class LabelScanForm(forms.Form):
    """Form for uploading wine label images for scanning."""

    barcode_image = forms.ImageField(
        required=False,
        label="Barcode Image",
        help_text="Optional: Upload barcode image",
    )
    front_image = forms.ImageField(
        required=True,
        label="Front Label Image",
        help_text="Required: Upload front label image",
    )
    back_image = forms.ImageField(
        required=False,
        label="Back Label Image",
        help_text="Optional: Upload back label image",
    )

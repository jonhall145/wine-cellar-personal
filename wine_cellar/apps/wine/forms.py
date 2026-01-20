import json
from datetime import datetime

import pycountry
from django import forms
from django.conf import settings
from django.core import validators
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q
from django.forms import ImageField
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.storage.models import Storage
from wine_cellar.apps.user.views import get_user_settings
from wine_cellar.apps.wine.fields import OpenMultipleChoiceField
from wine_cellar.apps.wine.models import (
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

image_fields_map = {
    "image_front_label": ImageType.LABEL_FRONT,
    "image_back_label": ImageType.LABEL_BACK,
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


class WineFormPostCleanMixin:
    def _post_clean(self):
        """Update tom-select config to prevent data loss in the form"""
        if hasattr(self, "cleaned_data"):
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


class WineBaseForm(TomSelectMixin, WineFormPostCleanMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        user_fields = [
            "vineyard",
            "attributes",
            "grapes",
            "food_pairings",
            "source",
        ]
        for user_field in user_fields:
            self.fields[user_field].queryset = self.fields[
                user_field
            ].queryset.model.objects.filter(Q(user=None) | Q(user=user))
            self.fields[user_field].user = user
        self.user = user
        user_settings = get_user_settings(user)
        self.fields["price"].help_text = _(
            "Enter the price of the bottle in %(currency)s."
        ) % {"currency": settings.CURRENCY_SYMBOLS[user_settings.currency]}

        # Set up drinking window year choices
        current_year = datetime.now().year
        year_choices = [("", "---------"), (0, _("Now"))]
        year_choices += [
            (y, str(y)) for y in range(current_year - 5, current_year + 51)
        ]
        self.fields["drink_from"].choices = year_choices
        self.fields["drink_to"].choices = year_choices

        # Configure storage field for user's storages
        if "storage" in self.fields:
            self.fields["storage"].queryset = Storage.objects.filter(user=user)

        for field_name, image_type_code in image_fields_map.items():
            field = self.fields.get(field_name)
            if not field:
                continue
            if getattr(self, "initial", None):
                wine_id = self.initial.get("id")
                if wine_id:
                    image_obj = (
                        WineImage.objects.filter(
                            wine=wine_id, image_type=image_type_code
                        )
                        .order_by("-id")
                        .first()
                    )
                    if image_obj:
                        self.initial[field_name] = image_obj.image
                        # Use thumbnail for preview if available, else full image
                        preview_url = (
                            image_obj.thumbnail.url
                            if image_obj.thumbnail
                            else image_obj.image.url
                        )
                        self.fields[field_name].widget.attrs[
                            "data-existing-url"
                        ] = preview_url

    class Meta:
        abstract = True

    name = forms.CharField(
        max_length=100,
        help_text=_("Enter the name of the wine as indicated on the label."),
    )
    wine_type = forms.CharField(
        max_length=2,
        widget=forms.Select(choices=WineType),
        help_text=_("Select the type of wine from the dropdown."),
    )
    category = forms.CharField(
        label="Sweetness",
        required=False,
        max_length=2,
        widget=forms.Select(choices=[("", "---------")] + list(Category.choices)),
        help_text=_("Select the sweetness level of the wine."),
    )
    country = forms.CharField(
        max_length=250,
        widget=forms.Select(
            choices={country.alpha_2: country.name for country in pycountry.countries},
        ),
        help_text=_(
            "Select the country the wine was produced in as indicated on the label."
        ),
    )
    subregion = forms.CharField(
        max_length=100,
        required=False,
        help_text=_(
            "Enter the subregion or appellation of the wine, e.g. Douro Valley, Dao."
        ),
    )
    size = forms.CharField(
        max_length=2,
        required=False,
        initial=SizeChoices.STANDARD,
        widget=forms.Select(choices=SizeChoices.choices),
        label="Size",
        help_text=_("Select the bottle size."),
    )
    abv = forms.FloatField(
        required=False,
        validators=[
            validators.MinValueValidator(0.0),
            validators.MaxValueValidator(100.0),
        ],
        help_text=_(
            "Please enter the percentage of alcohol in the"
            " wine. This information is typically found on the label and indicates the"
            " strength of the wine."
        ),
        localize=True,
    )
    vintage = forms.IntegerField(
        required=False,
        validators=[
            validators.MinValueValidator(1900),
            validators.MaxValueValidator(datetime.now().year),
        ],
        help_text=_(
            "Enter the year the grapes were harvested to produce the wine. Typically,"
            " vintage years are prominently displayed on wine labels."
        ),
    )
    grapes = OpenMultipleChoiceField(
        required=False,
        queryset=Grape.objects.none(),
        field_name="name",
        help_text=_(
            "Select or add the grape varieties used to produce the wine. You can "
            "select multiple options if applicable."
        ),
    )
    attributes = OpenMultipleChoiceField(
        required=False,
        queryset=Attribute.objects.none(),
        field_name="name",
        help_text=_(
            "Add any attributes that apply to this wine, such as"
            " natural, retsina or organic."
        ),
    )
    drink_from = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        label=_("Drink From"),
        help_text=_("When this wine is ready to drink."),
    )
    drink_to = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        label=_("Drink Until"),
        help_text=_("When this wine should be drunk by."),
    )
    food_pairings = OpenMultipleChoiceField(
        required=False,
        queryset=FoodPairing.objects.none(),
        field_name="name",
        help_text=_(
            "Enter dishes, cuisines, or ingredients that complement the "
            "flavors of this wine."
        ),
    )
    vineyard = OpenMultipleChoiceField(
        label="Vineyard",
        required=False,
        queryset=Vineyard.objects.none(),
        field_name="name",
        help_text=_("Enter the names of the vineyards which produced the wine."),
    )
    source = OpenMultipleChoiceField(
        required=False,
        queryset=Source.objects.none(),
        field_name="name",
        help_text=_("Where did you get the wine from?"),
    )
    price = forms.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        localize=True,
    )
    rrp = forms.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        localize=True,
        help_text=_(
            "Enter the recommended retail price if different from purchase price."
        ),
    )
    barcode = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Enter the barcode number of the wine as indicated on the label."),
    )
    comment = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.Textarea,
        help_text=_(
            "Share your thoughts, tasting experiences, or any anecdotes"
            " related to this wine."
        ),
    )
    rating = forms.IntegerField(
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        help_text=_("Rate this wine from 0 to 3 stars."),
    )
    image_front_label = ImageField(
        widget=NoFilenameClearableFileInput,
        required=False,
        help_text=_("Upload a photo of the front of the bottle label."),
    )
    image_back_label = ImageField(
        widget=NoFilenameClearableFileInput,
        required=False,
        help_text=_("Upload a photo of the back of the bottle label."),
    )
    # Storage fields for adding bottle to cellar
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
        max_digits=6,
        decimal_places=2,
        label=_("Bottle Price"),
        help_text=_(
            "Price paid for this specific bottle (if different from wine price)."
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
        self.set_tom_config(name="country", max_items=1, max_options=-1)


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


class WineFilterForm(TomSelectMixin, WineFormPostCleanMixin, forms.Form):
    template_name = "wine_filter_field.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["form_step"] = 0
        self.set_tom_config(name="grapes", create=False)
        self.set_tom_config(name="food_pairings", create=False)
        self.set_tom_config(name="source", create=False)
        self.set_tom_config(name="vineyard", create=False)
        self.set_tom_config(name="attributes", create=False)
        self.set_tom_config(
            name="country", create=False, max_options=-1, placeholder="", search=True
        )


class DrinkRecordForm(forms.Form):
    date_consumed = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        help_text=_("When did you drink this wine?"),
    )
    tasting_notes = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text=_("Your tasting notes for this wine."),
    )
    rating = forms.IntegerField(
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        help_text=_("Rate this wine from 0 to 3 stars."),
    )
    shared_with = forms.CharField(
        max_length=250,
        required=False,
        help_text=_("Who did you share this wine with?"),
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("What was the occasion?"),
    )


class WishlistForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        help_text=_("Name of the wine you want to buy."),
    )
    wine_type = forms.CharField(
        max_length=2,
        required=False,
        widget=forms.Select(choices=[("", "---------")] + list(WineType.choices)),
        help_text=_("Type of wine."),
    )
    country = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.Select(
            choices=[("", "---------")]
            + [(c.alpha_2, c.name) for c in pycountry.countries],
        ),
        help_text=_("Country of origin."),
    )
    subregion = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Subregion or appellation."),
    )
    vintage = forms.IntegerField(
        required=False,
        help_text=_("Desired vintage year."),
    )
    price_limit = forms.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        help_text=_("Maximum price you want to pay."),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text=_("Any notes about why you want this wine."),
    )
    priority = forms.IntegerField(
        initial=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_("Priority from 1 (low) to 5 (high)."),
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


class LabelScanForm(forms.Form):
    """Form for uploading wine label images for scanning."""

    barcode_image = forms.ImageField(
        required=False,
        label=_("Barcode Image"),
        help_text=_("Optional: Upload barcode image"),
    )
    front_image = forms.ImageField(
        required=True,
        label=_("Front Label Image"),
        help_text=_("Required: Upload front label image"),
    )
    back_image = forms.ImageField(
        required=False,
        label=_("Back Label Image"),
        help_text=_("Optional: Upload back label image"),
    )

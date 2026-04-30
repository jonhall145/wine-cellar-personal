import json

from django import forms
from django.conf import settings
from django.utils import timezone

from wine_cellar.apps.storage.models import Storage, StorageItem, get_app_type
from wine_cellar.apps.user.views import get_active_household, get_user_settings


class TomSelectMixin:
    def set_tom_config(
        self,
        name,
        create=False,
        items=None,
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


def native_select_widget(**attrs):
    select_attrs = {**attrs}
    select_attrs["data-native-select"] = "true"
    return forms.Select(attrs=select_attrs)


class BeverageBaseFormMixin:
    """Shared __init__ logic for WineBaseForm and WhiskyBaseForm.

    Subclasses must set:
        image_fields_map: dict  — {field_name: image_type_code}
        image_model: model class  — WineImage or WhiskyImage
        beverage_fk_name: str  — "wine" or "whisky"
    """

    image_fields_map = {}
    image_model = None
    beverage_fk_name = None

    def _init_beverage_form(self, user):
        """Call from subclass __init__ after super().__init__."""
        household = get_active_household(user)
        self.user = user
        self.household = household

        # Currency-specific price help text
        user_settings = get_user_settings(user)
        self.fields["price"].help_text = (
            "Enter the price of the bottle in %(currency)s."
            % {"currency": settings.CURRENCY_SYMBOLS[user_settings.currency]}
        )

        # Storage field queryset
        if "storage" in self.fields:
            self.fields["storage"].queryset = Storage.objects.filter(
                household=household, app_type=get_app_type()
            ).order_by("order", "created")

        # Image field initialization
        self._init_image_fields()

    def _init_image_fields(self):
        """Populate image fields with existing images for edit forms."""
        for field_name, image_type_code in self.image_fields_map.items():
            field = self.fields.get(field_name)
            if not field:
                continue
            if getattr(self, "initial", None):
                bev_id = self.initial.get("id")
                if bev_id:
                    image_obj = (
                        self.image_model.objects.filter(
                            **{
                                self.beverage_fk_name: bev_id,
                                "image_type": image_type_code,
                            }
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


class BaseDrinkRecordForm(forms.Form):
    """Shared drink record form for wine and whisky.

    Subclasses must set:
        storage_item_model: model class
        beverage_fk_name: str  — "wine" or "whisky"
        beverage_label: str  — "wine" or "whisky" (for messages)
    """

    storage_item_model = None
    beverage_fk_name = None
    beverage_label = "beverage"

    storage_item = forms.ModelChoiceField(
        queryset=StorageItem.objects.none(),
        required=False,
        label="Bottle",
        help_text="Select which bottle you consumed (optional).",
    )
    date_consumed = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        help_text="When did you drink this?",
    )
    tasting_notes = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text="Your tasting notes.",
    )
    rating = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        choices=[("", "-")] + [(i, f"{i} ★" if i else "0") for i in range(4)],
        help_text="Rate from 0 to 3 stars.",
    )
    shared_with = forms.CharField(
        max_length=250,
        required=False,
        help_text="Who did you share this with?",
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        help_text="What was the occasion?",
    )
    photo = forms.ImageField(
        required=False,
        help_text="Attach a photo of the bottle, meal, or setting (optional).",
    )
    taste_descriptors = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="Selected flavor descriptors from the tasting wheel.",
    )

    def __init__(self, *args, **kwargs):
        beverage = kwargs.pop(self.beverage_fk_name, None)
        self._beverage = beverage
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["storage_item"].queryset = self.storage_item_model.objects.none()

        if beverage and self.user:
            available_bottles = (
                self.storage_item_model.objects.filter(
                    **{self.beverage_fk_name: beverage},
                    user=self.user,
                    deleted=False,
                )
                .select_related("storage")
                .order_by("storage__name", "row", "column")
            )
            self.fields["storage_item"].queryset = available_bottles

            count = available_bottles.count()
            if count == 0:
                self.fields["storage_item"].help_text = (
                    "No bottles available in storage for this "
                    "%(label)s." % {"label": self.beverage_label}
                )
            else:
                self.fields["storage_item"].help_text = (
                    "Select which bottle you consumed "
                    "(%(count)d available)." % {"count": count}
                )

    def clean_storage_item(self):
        bottle = self.cleaned_data.get("storage_item")
        if bottle and bottle.deleted:
            raise forms.ValidationError("This bottle has already been consumed.")
        if (
            bottle
            and self._beverage
            and getattr(bottle, self.beverage_fk_name) != self._beverage
        ):
            raise forms.ValidationError("Invalid bottle selection.")
        return bottle


class MarkBottleGivenForm(forms.Form):
    recipient = forms.CharField(
        max_length=100,
        help_text="Who did you give this bottle to?",
    )
    given_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        help_text="When did you give this bottle away?",
    )
    given_occasion = forms.CharField(
        max_length=100,
        required=False,
        label="Occasion",
        help_text="Optional occasion for giving this bottle.",
    )


class BottleNoteForm(forms.Form):
    note_date = forms.DateField(
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        help_text="Date of this note.",
    )
    note = forms.CharField(
        widget=forms.Textarea,
        help_text="Your note about this bottle.",
    )


class ReorderReminderForm(forms.Form):
    min_stock = forms.IntegerField(
        min_value=1,
        initial=1,
        help_text="Alert when stock drops to or below this number.",
    )

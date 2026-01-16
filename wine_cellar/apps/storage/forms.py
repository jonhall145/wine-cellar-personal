from django import forms
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _

from wine_cellar.apps.storage.models import Storage
from wine_cellar.apps.user.views import get_user_settings


class StarRatingWidget(forms.RadioSelect):
    """A widget that renders star icons for rating selection (0-3 stars)."""

    template_name = "widgets/star_rating.html"

    def __init__(self, attrs=None, max_rating=3):
        self.max_rating = max_rating
        choices = [(i, str(i)) for i in range(max_rating + 1)]
        super().__init__(attrs=attrs, choices=choices)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["max_rating"] = self.max_rating
        return context


class StorageForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        help_text=_("Enter the name of the storage."),
    )
    description = forms.CharField(
        required=False,
        help_text=_("Enter a description of the storage."),
    )
    location = forms.CharField(
        max_length=100,
        help_text=_("Enter the location of the storage."),
    )
    rows = forms.IntegerField(
        min_value=0,
        required=False,
        help_text=_("Enter the number of rows in the storage."),
    )
    columns = forms.IntegerField(
        min_value=0,
        required=False,
        help_text=_("Enter the number of columns in the storage."),
    )


class StockAddForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        user_fields = ["storage"]
        for user_field in user_fields:
            self.fields[user_field].queryset = self.fields[
                user_field
            ].queryset.model.objects.filter(user=self.user)
            self.fields[user_field].user = self.user
        user_settings = get_user_settings(self.user)
        self.fields["price"].help_text = _(
            "Enter the price of the bottle in %(currency)s."
        ) % {"currency": settings.CURRENCY_SYMBOLS[user_settings.currency]}

    storage = forms.ModelChoiceField(
        queryset=Storage.objects.none(),
        help_text=_("Enter the name of the storage."),
    )
    row = forms.IntegerField(
        required=False,
        min_value=0,
        help_text=_("Enter the number of rows in the storage."),
        widget=forms.Select(),
    )
    column = forms.IntegerField(
        required=False,
        min_value=0,
        help_text=_("Enter the number of columns in the storage."),
        widget=forms.Select(),
    )
    price = forms.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        localize=True,
    )
    is_gift = forms.BooleanField(
        required=False,
        help_text=_("Check if this bottle was received as a gift."),
    )
    gift_from = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Enter who gave you this bottle."),
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Enter a special occasion this bottle is reserved for."),
    )
    rating = forms.IntegerField(
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(3)],
        help_text=_("Rate this bottle from 0 to 3 stars."),
    )

    def clean_row(self):
        row = self.cleaned_data.get("row")
        storage = self.cleaned_data.get("storage")
        if storage and row:
            if storage.rows == 0:
                raise forms.ValidationError(
                    _("The selected storage has no rows."), code="redundant_row"
                )
            if row > storage.rows:
                raise forms.ValidationError(
                    _("The selected row exceeds the number of rows in the storage."),
                    code="row_exceeds",
                )
        return row

    def clean_column(self):
        column = self.cleaned_data.get("column")
        storage = self.cleaned_data.get("storage")
        if storage and column:
            if storage.columns == 0:
                raise forms.ValidationError(
                    _("The selected storage has no columns."), code="redundant_column"
                )
            if column > storage.columns:
                raise forms.ValidationError(
                    _(
                        "The selected column exceeds the number of columns in the"
                        " storage."
                    ),
                    code="column_exceeds",
                )
        return column

    def clean(self):
        cleaned_data = super().clean()
        row = cleaned_data.get("row")
        column = cleaned_data.get("column")
        storage = cleaned_data.get("storage")
        if storage:
            if storage.rows > 0 and storage.columns > 0:
                if not row or not column:
                    raise forms.ValidationError(
                        _(
                            "Both row and column must be specified for the selected"
                            " storage."
                        ),
                        code="row_column_required",
                    )
                if storage.is_slot_occupied(row, column):
                    raise forms.ValidationError(
                        _(
                            "The selected slot (row: %(row)s, column: %(column)s)"
                            " is already occupied in the storage."
                        ),
                        code="slot_occupied",
                        params={"row": row, "column": column},
                    )
        return cleaned_data


class StorageItemEditForm(forms.Form):
    """Form for editing an existing StorageItem (bottle)."""

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)
        self.fields["storage"].queryset = Storage.objects.filter(user=self.user)
        user_settings = get_user_settings(self.user)
        self.fields["price"].help_text = _(
            "Enter the price of the bottle in %(currency)s."
        ) % {"currency": settings.CURRENCY_SYMBOLS[user_settings.currency]}

    storage = forms.ModelChoiceField(
        queryset=Storage.objects.none(),
        help_text=_("Select the storage location."),
    )
    row = forms.IntegerField(
        required=False,
        min_value=0,
        help_text=_("Enter the row number."),
        widget=forms.Select(),
    )
    column = forms.IntegerField(
        required=False,
        min_value=0,
        help_text=_("Enter the column number."),
        widget=forms.Select(),
    )
    price = forms.DecimalField(
        required=False,
        max_digits=6,
        decimal_places=2,
        localize=True,
    )
    is_gift = forms.BooleanField(
        required=False,
        help_text=_("Check if this bottle was received as a gift."),
    )
    gift_from = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Enter who gave you this bottle."),
    )
    occasion = forms.CharField(
        max_length=100,
        required=False,
        help_text=_("Enter a special occasion this bottle is reserved for."),
    )
    rating = forms.TypedChoiceField(
        required=False,
        coerce=lambda x: int(x) if x else None,
        empty_value=None,
        choices=[(None, "-")] + [(i, str(i)) for i in range(4)],
        widget=StarRatingWidget(max_rating=3),
        help_text=_("Rate this bottle from 0 to 3 stars."),
    )

    def clean_row(self):
        row = self.cleaned_data.get("row")
        storage = self.cleaned_data.get("storage")
        if storage and row:
            if storage.rows == 0:
                raise forms.ValidationError(
                    _("The selected storage has no rows."), code="redundant_row"
                )
            if row > storage.rows:
                raise forms.ValidationError(
                    _("The selected row exceeds the number of rows in the storage."),
                    code="row_exceeds",
                )
        return row

    def clean_column(self):
        column = self.cleaned_data.get("column")
        storage = self.cleaned_data.get("storage")
        if storage and column:
            if storage.columns == 0:
                raise forms.ValidationError(
                    _("The selected storage has no columns."), code="redundant_column"
                )
            if column > storage.columns:
                raise forms.ValidationError(
                    _(
                        "The selected column exceeds the number of columns in the"
                        " storage."
                    ),
                    code="column_exceeds",
                )
        return column

    def clean(self):
        cleaned_data = super().clean()
        row = cleaned_data.get("row")
        column = cleaned_data.get("column")
        storage = cleaned_data.get("storage")
        if storage:
            if storage.rows > 0 and storage.columns > 0:
                if not row or not column:
                    raise forms.ValidationError(
                        _(
                            "Both row and column must be specified for the selected"
                            " storage."
                        ),
                        code="row_column_required",
                    )
                # Check slot occupation, excluding current item
                occupied_query = storage.items.filter(
                    row=row, column=column, deleted=False
                )
                if self.instance:
                    occupied_query = occupied_query.exclude(pk=self.instance.pk)
                if occupied_query.exists():
                    raise forms.ValidationError(
                        _(
                            "The selected slot (row: %(row)s, column: %(column)s)"
                            " is already occupied in the storage."
                        ),
                        code="slot_occupied",
                        params={"row": row, "column": column},
                    )
        return cleaned_data

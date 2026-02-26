import json

from django import forms
from django.utils.translation import gettext_lazy as _


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

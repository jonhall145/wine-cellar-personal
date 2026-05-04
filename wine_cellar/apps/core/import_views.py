from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from wine_cellar.apps.core.forms import CsvImportMappingForm, CsvImportUploadForm
from wine_cellar.apps.core.importing import (
    CsvImportValidationError,
    parse_import_csv,
    parse_import_excel,
)
from wine_cellar.apps.household.mixins import RequireMemberMixin
from wine_cellar.apps.user.views import get_active_household


class BaseCsvImportView(RequireMemberMixin, TemplateView):
    template_name = "core/beverage_import.html"
    importer_class = None
    list_url_name = None
    session_key = None

    def get_importer(self):
        return self.importer_class()

    def get_session_key(self):
        return self.session_key

    def get_preview_data(self):
        return self.request.session.get(self.get_session_key())

    def clear_preview_data(self):
        self.request.session.pop(self.get_session_key(), None)

    def store_preview_data(self, *, headers, rows, filename):
        self.request.session[self.get_session_key()] = {
            "headers": headers,
            "rows": rows,
            "filename": filename,
        }

    def get_upload_form(self):
        return CsvImportUploadForm()

    def get_mapping_form(self, data=None):
        preview = self.get_preview_data()
        if not preview:
            return None

        importer = self.get_importer()
        initial = {
            f"map_{field_name}": header
            for field_name, header in importer.suggest_mapping(
                preview["headers"]
            ).items()
        }
        return CsvImportMappingForm(
            data=data,
            headers=preview["headers"],
            field_specs=importer.field_specs,
            user=self.request.user,
            initial=initial,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preview = self.get_preview_data()
        context.setdefault("upload_form", self.get_upload_form())
        context.setdefault("mapping_form", self.get_mapping_form())
        context["preview"] = preview
        context["sample_rows"] = (
            [
                [sample_row.get(header, "") for header in preview["headers"]]
                for sample_row in preview["rows"][:5]
            ]
            if preview
            else []
        )
        mapping_form = context.get("mapping_form")
        context["mapping_rows"] = (
            [
                {
                    "label": field.label,
                    "required": field.required,
                    "help_text": field.help_text,
                    "bound_field": mapping_form[f"map_{field.name}"],
                }
                for field in self.get_importer().field_specs
            ]
            if mapping_form
            else []
        )
        context["list_url"] = reverse(self.list_url_name)
        return context

    def post(self, request, *args, **kwargs):
        if not self.can_edit():
            raise PermissionDenied(
                "You need Member role or higher to perform this action."
            )
        action = request.POST.get("action", "upload")
        if action == "clear":
            self.clear_preview_data()
            return self._safe_redirect(request, request.path)
        if action == "import":
            return self.handle_import()
        return self.handle_upload()

    def _safe_redirect(self, request, fallback_url):
        """Redirect to the fallback URL (never user-supplied input)."""
        return redirect(fallback_url)

    def handle_upload(self):
        upload_form = CsvImportUploadForm(self.request.POST, self.request.FILES)
        if not upload_form.is_valid():
            return self.render_to_response(
                self.get_context_data(upload_form=upload_form)
            )

        uploaded_file = upload_form.cleaned_data["file"]
        filename_lower = uploaded_file.name.lower()

        try:
            if filename_lower.endswith(".xlsx"):
                headers, rows = parse_import_excel(uploaded_file)
            else:
                headers, rows = parse_import_csv(uploaded_file)
        except ValidationError as exc:
            upload_form.add_error("file", exc)
            return self.render_to_response(
                self.get_context_data(upload_form=upload_form)
            )

        self.store_preview_data(
            headers=headers,
            rows=rows,
            filename=upload_form.cleaned_data["file"].name,
        )
        return self.render_to_response(
            self.get_context_data(mapping_form=self.get_mapping_form())
        )

    def handle_import(self):
        preview = self.get_preview_data()
        if not preview:
            messages.error(self.request, "Upload a CSV or Excel file before importing.")
            return self._safe_redirect(self.request, self.request.path)

        mapping_form = self.get_mapping_form(data=self.request.POST)
        if mapping_form is None or not mapping_form.is_valid():
            return self.render_to_response(
                self.get_context_data(mapping_form=mapping_form)
            )

        importer = self.get_importer()
        household = get_active_household(self.request.user)

        try:
            summary = importer.import_rows(
                user=self.request.user,
                household=household,
                rows=preview["rows"],
                mapping=mapping_form.get_mapping(),
                default_storage=mapping_form.cleaned_data.get("default_storage"),
            )
        except CsvImportValidationError as exc:
            return self.render_to_response(
                self.get_context_data(
                    mapping_form=mapping_form,
                    row_errors=exc.row_errors,
                )
            )

        self.clear_preview_data()
        messages.success(
            self.request,
            "%(created)d created, %(matched)d matched existing, "
            "%(stock)d bottles added."
            % {
                "created": summary.created_beverages,
                "matched": summary.matched_beverages,
                "stock": summary.created_stock_items,
            },
        )
        return redirect(self.list_url_name)

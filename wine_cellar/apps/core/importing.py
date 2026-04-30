import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pycountry
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import QueryDict

from wine_cellar.apps.storage.models import Storage, get_app_type

MAX_IMPORT_FILE_SIZE = 512 * 1024
MAX_IMPORT_ROWS = 250

TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def normalize_import_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().casefold())


def split_import_values(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[,;\n]+", value) if part.strip()]


def parse_import_csv(uploaded_file):
    if uploaded_file.size > MAX_IMPORT_FILE_SIZE:
        raise ValidationError(
            f"CSV files must be {MAX_IMPORT_FILE_SIZE // 1024}KB or smaller."
        )

    if not uploaded_file.name.lower().endswith(".csv"):
        raise ValidationError("Only CSV files are supported right now.")

    raw_bytes = uploaded_file.read()
    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV files must be UTF-8 encoded.") from exc

    if not content.strip():
        raise ValidationError("The uploaded CSV file is empty.")

    sample = content[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    headers = list(reader.fieldnames or [])
    if not headers:
        raise ValidationError("The CSV file must include a header row.")

    cleaned_headers = [header.strip() for header in headers]
    if any(not header for header in cleaned_headers):
        raise ValidationError("CSV column headers cannot be blank.")

    normalized_headers = [normalize_import_key(header) for header in cleaned_headers]
    if len(normalized_headers) != len(set(normalized_headers)):
        raise ValidationError("CSV column headers must be unique.")

    rows = []
    for index, row in enumerate(reader, start=1):
        if index > MAX_IMPORT_ROWS:
            raise ValidationError(f"CSV imports are limited to {MAX_IMPORT_ROWS} rows.")
        cleaned_row = {
            header: (row.get(header) or "").strip() for header in cleaned_headers
        }
        rows.append(cleaned_row)

    if not rows:
        raise ValidationError("The CSV file does not contain any data rows.")

    return cleaned_headers, rows


@dataclass(frozen=True)
class ImportFieldSpec:
    name: str
    label: str
    aliases: tuple[str, ...] = ()
    required: bool = False
    help_text: str = ""


@dataclass
class PreparedImportRow:
    form_data: QueryDict
    stock_count: int
    extra_positions: list[tuple[int | None, int | None]]


@dataclass
class ImportSummary:
    created_beverages: int = 0
    matched_beverages: int = 0
    created_stock_items: int = 0
    skipped_rows: int = 0


class CsvImportValidationError(Exception):
    def __init__(self, row_errors: list[dict]):
        super().__init__("CSV import validation failed.")
        self.row_errors = row_errors


class BaseCsvBeverageImporter:
    form_class = None
    storage_item_model = None
    beverage_fk_name = None
    field_specs: tuple[ImportFieldSpec, ...] = ()
    multiple_fields: frozenset[str] = frozenset()
    boolean_fields: frozenset[str] = frozenset()
    stock_mapping_fields: frozenset[str] = frozenset(
        {"stock_count", "storage_name", "row", "column", "bottle_price"}
    )

    @property
    def field_spec_map(self):
        return {field.name: field for field in self.field_specs}

    def suggest_mapping(self, headers: list[str]) -> dict[str, str]:
        normalized_headers = {
            normalize_import_key(header): header for header in headers if header
        }
        suggestions = {}
        for field in self.field_specs:
            candidates = (field.name, *field.aliases)
            for candidate in candidates:
                match = normalized_headers.get(normalize_import_key(candidate))
                if match:
                    suggestions[field.name] = match
                    break
        return suggestions

    def import_rows(
        self,
        *,
        user,
        household,
        rows: list[dict[str, str]],
        mapping: dict[str, str],
        default_storage,
    ) -> ImportSummary:
        errors = []
        summary = ImportSummary()

        with transaction.atomic():
            for row_number, row in enumerate(rows, start=2):
                if self.row_is_blank(row, mapping):
                    summary.skipped_rows += 1
                    continue

                try:
                    prepared = self.prepare_row(
                        row=row,
                        mapping=mapping,
                        user=user,
                        household=household,
                        default_storage=default_storage,
                    )
                    form = self.form_class(prepared.form_data, user=user)
                    if not form.is_valid():
                        errors.append(
                            {
                                "row_number": row_number,
                                "messages": self.format_form_errors(form),
                            }
                        )
                        continue

                    beverage, created = self.create_beverage(
                        user=user,
                        household=household,
                        cleaned_data=form.cleaned_data,
                    )
                    if created:
                        summary.created_beverages += 1
                    else:
                        summary.matched_beverages += 1

                    summary.created_stock_items += prepared.stock_count
                    for extra_row, extra_column in prepared.extra_positions:
                        self.create_storage_item(
                            beverage=beverage,
                            user=user,
                            household=household,
                            cleaned_data=form.cleaned_data,
                            row=extra_row,
                            column=extra_column,
                        )
                except ValidationError as exc:
                    errors.append(
                        {
                            "row_number": row_number,
                            "messages": self.format_validation_error(exc),
                        }
                    )

            if errors:
                raise CsvImportValidationError(errors)

        return summary

    def row_is_blank(self, row: dict[str, str], mapping: dict[str, str]) -> bool:
        for header in mapping.values():
            if header and row.get(header, "").strip():
                return False
        return True

    def prepare_row(self, *, row, mapping, user, household, default_storage):
        form_data = QueryDict("", mutable=True)
        resolved_stock_data = {
            "stock_count": 0,
            "storage": None,
            "row": None,
            "column": None,
            "bottle_price": None,
        }

        for field in self.field_specs:
            header = mapping.get(field.name, "")
            raw_value = row.get(header, "").strip() if header else ""
            converted = self.convert_field_value(
                field_name=field.name,
                raw_value=raw_value,
                row=row,
                user=user,
                household=household,
            )
            if field.name in self.stock_mapping_fields:
                resolved_stock_data[field.name] = converted
                continue

            if field.name in self.multiple_fields:
                form_data.setlist(field.name, converted)
            elif field.name in self.boolean_fields:
                if converted:
                    form_data[field.name] = "on"
            elif converted not in (None, ""):
                form_data[field.name] = str(converted)

        stock_count = resolved_stock_data["stock_count"] or 0
        stock_requested = stock_count > 0 or any(
            resolved_stock_data.get(key)
            for key in ("storage", "row", "column", "bottle_price")
        )
        storage = resolved_stock_data["storage"] or default_storage

        if stock_requested and storage is None:
            raise ValidationError(
                "Select a default storage or map a storage column before "
                "importing stock."
            )

        if stock_requested and stock_count <= 0:
            stock_count = 1

        positions = self.resolve_stock_positions(
            storage=storage,
            count=stock_count,
            explicit_row=resolved_stock_data["row"],
            explicit_column=resolved_stock_data["column"],
        )

        if stock_requested:
            form_data["storage"] = str(storage.pk)
            if positions:
                first_row, first_column = positions[0]
                if first_row is not None:
                    form_data["row"] = str(first_row)
                if first_column is not None:
                    form_data["column"] = str(first_column)
            bottle_price = self.convert_decimal(
                resolved_stock_data["bottle_price"], "Bottle price"
            )
            if bottle_price is not None:
                form_data["bottle_price"] = str(bottle_price)

        return PreparedImportRow(
            form_data=form_data,
            stock_count=stock_count,
            extra_positions=(
                positions[1:] if positions else [(None, None)] * max(stock_count - 1, 0)
            ),
        )

    def resolve_stock_positions(self, *, storage, count, explicit_row, explicit_column):
        if count <= 0:
            return []

        if storage.rows <= 0 or storage.columns <= 0:
            if explicit_row or explicit_column:
                raise ValidationError(
                    f"Storage “{storage.name}” does not use row/column positions."
                )
            return [(None, None)] * count

        if explicit_row or explicit_column:
            if explicit_row is None or explicit_column is None:
                raise ValidationError("Both row and column are required together.")
            if count != 1:
                raise ValidationError(
                    "Rows with explicit storage positions can only import one bottle."
                )
            if not storage.is_cell_active(explicit_row, explicit_column):
                raise ValidationError(
                    f"Storage slot {explicit_row}/{explicit_column} is not active."
                )
            if storage.is_slot_occupied(explicit_row, explicit_column):
                raise ValidationError(
                    f"Storage slot {explicit_row}/{explicit_column} is already "
                    "occupied."
                )
            return [(explicit_row, explicit_column)]

        free_cells = storage.get_free_cells_by_row()
        available = [
            (row, column) for row in sorted(free_cells) for column in free_cells[row]
        ]
        if len(available) < count:
            raise ValidationError(
                f"Storage “{storage.name}” only has {len(available)} free slots."
            )
        return available[:count]

    def create_beverage(self, *, user, household, cleaned_data):
        raise NotImplementedError

    def create_storage_item(
        self, *, beverage, user, household, cleaned_data, row, column
    ):
        raise NotImplementedError

    def convert_field_value(self, *, field_name, raw_value, row, user, household):
        raise NotImplementedError

    def format_validation_error(self, exc: ValidationError) -> list[str]:
        if hasattr(exc, "error_dict"):
            messages = []
            for field, errors in exc.message_dict.items():
                prefix = self.field_spec_map.get(field)
                field_label = (
                    prefix.label if prefix else field.replace("_", " ").title()
                )
                for error in errors:
                    messages.append(f"{field_label}: {error}")
            return messages
        if hasattr(exc, "messages") and exc.messages:
            return list(exc.messages)
        return [str(exc)]

    def format_form_errors(self, form) -> list[str]:
        messages = []
        for field, errors in form.errors.items():
            spec = self.field_spec_map.get(field)
            field_label = spec.label if spec else field.replace("_", " ").title()
            for error in errors:
                messages.append(f"{field_label}: {error}")
        return messages

    def convert_int(self, value, label):
        value = (value or "").strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ValidationError(f"{label} must be a whole number.") from exc

    def convert_decimal(self, value, label):
        value = (value or "").strip()
        if not value:
            return None
        normalized = value.replace("£", "").replace("$", "").replace("€", "").strip()
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValidationError(f"{label} must be a valid decimal number.") from exc

    def convert_boolean(self, value):
        return normalize_import_key(value) in TRUE_VALUES

    def resolve_choice(self, value, choices, label):
        raw = (value or "").strip()
        if not raw:
            return ""
        normalized = normalize_import_key(raw)
        choice_map = {}
        for option in choices:
            option_value = str(option[0])
            option_label = str(option[1])
            choice_map[normalize_import_key(option_value)] = option_value
            choice_map[normalize_import_key(option_label)] = option_value
        resolved = choice_map.get(normalized)
        if resolved is None:
            raise ValidationError(f"{label} has an unsupported value: {raw}.")
        return resolved

    def resolve_country_code(self, value, *, allow_whisky_private=False):
        raw = (value or "").strip()
        if not raw:
            return ""

        custom_countries = {}
        if allow_whisky_private:
            custom_countries = {
                "xs": "XS",
                "scotland": "XS",
                "xe": "XE",
                "england": "XE",
                "xw": "XW",
                "wales": "XW",
            }

        if normalize_import_key(raw) in custom_countries:
            return custom_countries[normalize_import_key(raw)]

        if len(raw) == 2 and raw.upper() not in custom_countries.values():
            country = pycountry.countries.get(alpha_2=raw.upper())
            if country:
                return country.alpha_2

        country = pycountry.countries.get(name=raw)
        if country is None:
            country = pycountry.countries.get(common_name=raw)
        if country is None:
            try:
                country = pycountry.countries.search_fuzzy(raw)[0]
            except LookupError as exc:
                raise ValidationError(f"Unknown country: {raw}.") from exc
        return country.alpha_2

    def resolve_storage(self, value, *, household):
        raw = (value or "").strip()
        if not raw:
            return None
        storage_qs = Storage.objects.filter(
            household=household, app_type=get_app_type(), name__iexact=raw
        ).order_by("order", "created")
        count = storage_qs.count()
        if count == 0:
            raise ValidationError(f"Storage “{raw}” does not exist.")
        if count > 1:
            raise ValidationError(f"Storage “{raw}” is ambiguous.")
        return storage_qs.first()

    def resolve_name_values(
        self,
        model,
        value,
        *,
        household=None,
        include_global=False,
        allow_create=True,
    ):
        resolved = []
        for part in split_import_values(value):
            queryset = model.objects.all()
            if household is not None and hasattr(model, "household"):
                if include_global:
                    queryset = queryset.filter(
                        Q(household=household) | Q(household__isnull=True)
                    )
                else:
                    queryset = queryset.filter(household=household)
            match = queryset.filter(name__iexact=part).first()
            if match:
                resolved.append(str(match.pk))
                continue
            if not allow_create:
                raise ValidationError(f"Unknown value: {part}.")
            resolved.append(f"tom_new_opt{part}")
        return resolved

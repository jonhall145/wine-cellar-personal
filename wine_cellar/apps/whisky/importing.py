from django.core.exceptions import ValidationError
from django.utils import timezone

from wine_cellar.apps.core.importing import (
    BaseCsvBeverageImporter,
    ImportFieldSpec,
    split_import_values,
)
from wine_cellar.apps.whisky.forms import WhiskyForm
from wine_cellar.apps.whisky.models import (
    COMMON_CASK_TYPES,
    Bottler,
    BottleSize,
    Distillery,
    FillLevel,
    PeatedLevel,
    WhiskyRegion,
    WhiskySource,
    WhiskyStorageItem,
    WhiskyType,
)


class WhiskyCsvImporter(BaseCsvBeverageImporter):
    form_class = WhiskyForm
    storage_item_model = WhiskyStorageItem
    beverage_fk_name = "whisky"
    multiple_fields = frozenset({"cask_type"})
    boolean_fields = frozenset({"is_gift", "cask_strength"})
    field_specs = (
        ImportFieldSpec("name", "Name", required=True),
        ImportFieldSpec("whisky_type", "Whisky type", aliases=("type",), required=True),
        ImportFieldSpec("distillery", "Distillery"),
        ImportFieldSpec("region", "Region"),
        ImportFieldSpec("country", "Country", required=True),
        ImportFieldSpec("age_statement", "Age statement"),
        ImportFieldSpec("vintage_year", "Vintage year"),
        ImportFieldSpec("bottled_year", "Bottled year"),
        ImportFieldSpec("abv", "ABV"),
        ImportFieldSpec("price", "Price"),
        ImportFieldSpec("size", "Bottle size"),
        ImportFieldSpec("peated_level", "Peated"),
        ImportFieldSpec("cask_type", "Cask type"),
        ImportFieldSpec("cask_strength", "Cask strength"),
        ImportFieldSpec("bottler", "Bottler"),
        ImportFieldSpec("source", "Source"),
        ImportFieldSpec("owner", "Owner"),
        ImportFieldSpec("rating", "Rating"),
        ImportFieldSpec("comment", "Comment"),
        ImportFieldSpec("barcode", "Barcode"),
        ImportFieldSpec("fill_level", "Fill level"),
        ImportFieldSpec("stock_count", "Stock count", aliases=("stock", "quantity")),
        ImportFieldSpec("storage_name", "Storage", aliases=("storage",)),
        ImportFieldSpec("row", "Storage row"),
        ImportFieldSpec("column", "Storage column"),
        ImportFieldSpec("bottle_price", "Bottle price"),
        ImportFieldSpec("is_gift", "Gift"),
        ImportFieldSpec("gift_from", "Gift from"),
        ImportFieldSpec("occasion", "Occasion"),
    )

    def __init__(self, create_beverage_callback):
        self._create_beverage_callback = create_beverage_callback

    def create_beverage(self, *, user, household, cleaned_data):
        return self._create_beverage_callback(user, household, cleaned_data)

    def create_storage_item(
        self, *, beverage, user, household, cleaned_data, row, column
    ):
        fill_level = cleaned_data.get("fill_level") or FillLevel.UNOPENED
        dreg_date = timezone.localdate() if fill_level == FillLevel.DREG else None
        bottle_price = cleaned_data.get("bottle_price") or cleaned_data.get("price")
        WhiskyStorageItem.objects.create(
            storage=cleaned_data["storage"],
            whisky=beverage,
            row=row,
            column=column,
            user=user,
            household=household,
            price=bottle_price,
            is_gift=cleaned_data.get("is_gift", False),
            gift_from=cleaned_data.get("gift_from"),
            occasion=cleaned_data.get("occasion"),
            fill_level=fill_level,
            dreg_date=dreg_date,
        )

    def convert_field_value(
        self, *, field_name, raw_value, row, mapping, user, household
    ):
        if field_name in {
            "name",
            "owner",
            "comment",
            "barcode",
            "gift_from",
            "occasion",
        }:
            return raw_value
        if field_name == "whisky_type":
            return self.resolve_choice(raw_value, WhiskyType.choices, "Whisky type")
        if field_name == "country":
            return self.resolve_country_code(raw_value, allow_whisky_private=True)
        if field_name == "size":
            if not raw_value.strip():
                return BottleSize.STANDARD
            return self.resolve_choice(raw_value, BottleSize.choices, "Bottle size")
        if field_name == "peated_level":
            return self.resolve_choice(raw_value, PeatedLevel.choices, "Peated")
        if field_name == "fill_level":
            return self.resolve_choice(raw_value, FillLevel.choices, "Fill level")
        if field_name in {
            "age_statement",
            "vintage_year",
            "bottled_year",
            "rating",
            "stock_count",
            "row",
            "column",
        }:
            return self.convert_int(raw_value, self.field_spec_map[field_name].label)
        if field_name in {"abv", "price", "bottle_price"}:
            return self.convert_decimal(
                raw_value, self.field_spec_map[field_name].label
            )
        if field_name in {"is_gift", "cask_strength"}:
            return self.convert_boolean(raw_value)
        if field_name == "cask_type":
            values = split_import_values(raw_value)
            if not values:
                return []
            resolved = []
            common_types = {value.casefold(): value for value in COMMON_CASK_TYPES}
            for value in values:
                resolved.append(common_types.get(value.casefold(), value))
            return resolved
        if field_name in {"distillery", "region", "bottler", "source"}:
            model_map = {
                "distillery": Distillery,
                "region": WhiskyRegion,
                "bottler": Bottler,
                "source": WhiskySource,
            }
            model = model_map[field_name]
            raw_value = raw_value.strip()
            if not raw_value:
                return ""
            match = model.objects.filter(name__iexact=raw_value).first()
            if match:
                return str(match.pk)
            return f"tom_new_opt{raw_value}"
        if field_name == "storage_name":
            return self.resolve_storage(raw_value, household=household)
        raise ValidationError(f"Unsupported field mapping: {field_name}.")

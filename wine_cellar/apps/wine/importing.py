from django.core.exceptions import ValidationError

from wine_cellar.apps.core.importing import BaseCsvBeverageImporter, ImportFieldSpec
from wine_cellar.apps.storage.models import StorageItem
from wine_cellar.apps.wine.forms import WineForm
from wine_cellar.apps.wine.models import (
    SIZE_LITERS_TO_CODE,
    Appellation,
    Attribute,
    Category,
    FoodPairing,
    Grape,
    SizeChoices,
    Source,
    Vineyard,
    WineType,
)
from wine_cellar.apps.wine.views.wine_crud import WineCreateView


class WineCsvImporter(BaseCsvBeverageImporter):
    form_class = WineForm
    storage_item_model = StorageItem
    beverage_fk_name = "wine"
    multiple_fields = frozenset(
        {"grapes", "vineyard", "food_pairings", "attributes", "source"}
    )
    field_specs = (
        ImportFieldSpec("name", "Name", required=True),
        ImportFieldSpec("wine_type", "Wine type", aliases=("type",), required=True),
        ImportFieldSpec("category", "Sweetness", aliases=("sweetness",)),
        ImportFieldSpec("country", "Country", required=True),
        ImportFieldSpec("subregion", "Subregion"),
        ImportFieldSpec("appellation", "Appellation"),
        ImportFieldSpec("vintage", "Vintage"),
        ImportFieldSpec("grapes", "Grapes"),
        ImportFieldSpec("abv", "ABV"),
        ImportFieldSpec("rating", "Rating"),
        ImportFieldSpec("price", "Price"),
        ImportFieldSpec("size", "Bottle size"),
        ImportFieldSpec("drink_from", "Drink from"),
        ImportFieldSpec("drink_to", "Drink to"),
        ImportFieldSpec("comment", "Comment"),
        ImportFieldSpec("vineyard", "Vineyard"),
        ImportFieldSpec("food_pairings", "Food pairings"),
        ImportFieldSpec("attributes", "Attributes"),
        ImportFieldSpec("source", "Source"),
        ImportFieldSpec("barcode", "Barcode"),
        ImportFieldSpec("stock_count", "Stock count", aliases=("stock", "quantity")),
        ImportFieldSpec("storage_name", "Storage", aliases=("storage",)),
        ImportFieldSpec("row", "Storage row"),
        ImportFieldSpec("column", "Storage column"),
        ImportFieldSpec("bottle_price", "Bottle price"),
        ImportFieldSpec("is_gift", "Gift"),
        ImportFieldSpec("gift_from", "Gift from"),
        ImportFieldSpec("occasion", "Occasion"),
    )
    boolean_fields = frozenset({"is_gift"})

    def create_beverage(self, *, user, household, cleaned_data):
        return WineCreateView.process_form_data(user, household, cleaned_data)

    def create_storage_item(
        self, *, beverage, user, household, cleaned_data, row, column
    ):
        bottle_price = cleaned_data.get("bottle_price") or cleaned_data.get("price")
        StorageItem.objects.create(
            storage=cleaned_data["storage"],
            wine=beverage,
            row=row,
            column=column,
            user=user,
            household=household,
            price=bottle_price,
            is_gift=cleaned_data.get("is_gift", False),
            gift_from=cleaned_data.get("gift_from"),
            occasion=cleaned_data.get("occasion"),
        )

    def convert_field_value(self, *, field_name, raw_value, row, mapping, user, household):
        if field_name in {
            "name",
            "subregion",
            "comment",
            "barcode",
            "gift_from",
            "occasion",
        }:
            return raw_value
        if field_name == "wine_type":
            return self.resolve_choice(raw_value, WineType.choices, "Wine type")
        if field_name == "category":
            return self.resolve_choice(raw_value, Category.choices, "Sweetness")
        if field_name == "country":
            return self.resolve_country_code(raw_value)
        if field_name == "appellation":
            raw_value = raw_value.strip()
            if not raw_value:
                return ""
            country_code = None
            country_header = mapping.get("country", "")
            if country_header:
                country_raw = row.get(country_header, "").strip()
                if country_raw:
                    country_code = self.resolve_country_code(country_raw)
            qs = Appellation.objects.filter(name__iexact=raw_value)
            if country_code:
                qs = qs.filter(country=country_code)
            appellation = qs.first()
            if appellation is None:
                raise ValidationError(f"Unknown appellation: {raw_value}.")
            return str(appellation.pk)
        if field_name in {"vintage", "rating", "stock_count", "row", "column"}:
            return self.convert_int(raw_value, self.field_spec_map[field_name].label)
        if field_name in {"abv", "price", "bottle_price"}:
            return self.convert_decimal(
                raw_value, self.field_spec_map[field_name].label
            )
        if field_name == "size":
            raw_value = raw_value.strip()
            if not raw_value:
                return ""
            if raw_value in SIZE_LITERS_TO_CODE:
                return SIZE_LITERS_TO_CODE[raw_value]
            try:
                liters = float(raw_value)
            except ValueError:
                liters = None
            if liters in SIZE_LITERS_TO_CODE:
                return SIZE_LITERS_TO_CODE[liters]
            return self.resolve_choice(raw_value, SizeChoices.choices, "Bottle size")
        if field_name in {"drink_from", "drink_to"}:
            raw_value = raw_value.strip()
            if not raw_value:
                return ""
            if raw_value.casefold() == "now":
                return 0
            return self.convert_int(raw_value, self.field_spec_map[field_name].label)
        if field_name in {
            "grapes",
            "vineyard",
            "food_pairings",
            "attributes",
            "source",
        }:
            model_map = {
                "grapes": Grape,
                "vineyard": Vineyard,
                "food_pairings": FoodPairing,
                "attributes": Attribute,
                "source": Source,
            }
            return self.resolve_name_values(
                model_map[field_name],
                raw_value,
                household=household,
                include_global=True,
            )
        if field_name == "storage_name":
            return self.resolve_storage(raw_value, household=household)
        if field_name == "is_gift":
            return self.convert_boolean(raw_value)
        raise ValidationError(f"Unsupported field mapping: {field_name}.")

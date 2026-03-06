"""Wine data export to CSV and JSON formats."""

import csv
import io
import json
from datetime import date

from django.http import HttpResponse

from wine_cellar.apps.wine.models import Wine


def _get_wine_queryset(household):
    """Get wines with all related data prefetched."""
    return (
        Wine.objects.filter(household=household)
        .with_related()
        .with_stock_count()
        .order_by("name")
    )


def _wine_to_dict(wine) -> dict:
    """Convert a wine instance to a flat export dictionary."""
    return {
        "name": wine.name,
        "type": wine.get_type if wine.wine_type else "",
        "category": wine.get_category or "",
        "country": wine.country,
        "subregion": wine.subregion or "",
        "appellation": str(wine.appellation) if wine.appellation else "",
        "vintage": wine.vintage or "",
        "grapes": ", ".join(str(g) for g in wine.grapes.all()),
        "abv": wine.abv or "",
        "rating": wine.rating if wine.rating is not None else "",
        "price": str(wine.price) if wine.price else "",
        "size": str(wine.size) if wine.size else "",
        "drink_from": wine.drink_from or "",
        "drink_to": wine.drink_to or "",
        "comment": wine.comment,
        "vineyard": ", ".join(str(v) for v in wine.vineyard.all()),
        "food_pairings": ", ".join(str(f) for f in wine.food_pairings.all()),
        "attributes": ", ".join(str(a) for a in wine.attributes.all()),
        "stock": wine.stock_count,
        "created": wine.created.isoformat() if wine.created else "",
    }


EXPORT_FIELDS = [
    "name",
    "type",
    "category",
    "country",
    "subregion",
    "appellation",
    "vintage",
    "grapes",
    "abv",
    "rating",
    "price",
    "size",
    "drink_from",
    "drink_to",
    "comment",
    "vineyard",
    "food_pairings",
    "attributes",
    "stock",
    "created",
]


def export_wines_csv(household) -> HttpResponse:
    """Export all wines for a household as CSV."""
    wines = _get_wine_queryset(household)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    for wine in wines:
        writer.writerow(_wine_to_dict(wine))

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="wines_export_{date.today().isoformat()}.csv"'
    )
    return response


def export_wines_json(household) -> HttpResponse:
    """Export all wines for a household as JSON."""
    wines = _get_wine_queryset(household)
    data = [_wine_to_dict(wine) for wine in wines]

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type="application/json",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="wines_export_{date.today().isoformat()}.json"'
    )
    return response

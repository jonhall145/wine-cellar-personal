import json

from django import template
from django.conf import settings
from django.utils.html import format_html

from wine_cellar.apps.wine.models import Wine

register = template.Library()


def wine_to_json(wine: Wine):
    feature = {
        "name": wine.name,
        "country": wine.country,
        "country_name": wine.country_name,
        "country_icon": wine.country_icon,
        "image": wine.image_thumbnail,
        "vintage": wine.vintage,
        "url": wine.get_absolute_url(),
        "subregion": wine.subregion,
    }
    # Add appellation coordinates if available
    if wine.appellation:
        feature["appellation"] = {
            "name": wine.appellation.name,
            "lat": wine.appellation.latitude,
            "lng": wine.appellation.longitude,
        }
    return feature


@register.simple_tag()
def react_map(wines):
    map_settings = {
        "attribution": '<a href="https://openfreemap.org" target="_blank" rel="noopener noreferrer">'
        + 'OpenFreeMap</a> <a href="https://www.openmaptiles.org/" '
        + 'target="_blank" rel="noopener noreferrer">© OpenMapTiles</a> Data from '
        + '<a href="https://www.openstreetmap.org/copyright" '
        + 'target="_blank" rel="noopener noreferrer">OpenStreetMap</a>',
        "baseUrl": settings.MAP_BASEURL,
    }
    # Get unique country codes from wines currently in stock
    countries_with_wines = list(set(w.country for w in wines if w.country))
    wines_json = [wine_to_json(w) for w in wines]
    attributes = {
        "map": map_settings,
        "wines": wines_json,
        "countriesWithWines": countries_with_wines,
    }

    return format_html(
        '<div id="wine_map" ' 'data-attributes="{attributes}"></div>',
        attributes=json.dumps(attributes),
    )

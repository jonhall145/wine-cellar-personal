"""Grape name normalization: aliases, deduplication, and cleanup."""

import re

# Map alternative/regional grape names to canonical names
GRAPE_ALIASES = {
    "cab sav": "Cabernet Sauvignon",
    "cab": "Cabernet Sauvignon",
    "sav blanc": "Sauvignon Blanc",
    "shiraz": "Syrah",
    "garnacha": "Grenache",
    "primitivo": "Zinfandel",
    "pinot grigio": "Pinot Gris",
    "monastrell": "Mourvèdre",
    "spätburgunder": "Pinot Noir",
    "weissburgunder": "Pinot Blanc",
    "grauburgunder": "Pinot Gris",
    "cinsaut": "Cinsault",
    "tinta roriz": "Tempranillo",
    "aragonez": "Tempranillo",
    "muskat": "Muskateller",
    "brunello": "Sangiovese",
    "morellino": "Sangiovese",
    "nielluccio": "Sangiovese",
    "pinot bianco": "Pinot Blanc",
    "pinot nero": "Pinot Noir",
}

# Values that should be skipped entirely
SKIP_VALUES = {
    "not found",
    "unknown",
    "blend",
    "n/a",
    "none",
    "",
    "pinot",  # Ambiguous without qualifier (Noir/Blanc/Gris)
}


def normalize_grape_name(name):
    """Normalize a grape name: strip parentheticals, apply aliases, title case.

    Returns None if the name should be skipped.
    """
    name = name.strip()
    # Remove parenthetical notes like "(specific variety not specified)"
    name = re.sub(r"\s*\(.*?\)\s*", "", name).strip()
    if not name or name.lower() in SKIP_VALUES:
        return None
    # Check aliases (case-insensitive)
    alias = GRAPE_ALIASES.get(name.lower())
    if alias:
        return alias
    # Preserve existing casing if mixed, otherwise title case
    if name == name.lower() or name == name.upper():
        return name.title()
    return name


def normalize_grape_list(names):
    """Normalize a list of grape names, removing duplicates.

    Returns deduplicated list preserving order.
    """
    seen = set()
    result = []
    for name in names:
        normalized = normalize_grape_name(name)
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            result.append(normalized)
    return result

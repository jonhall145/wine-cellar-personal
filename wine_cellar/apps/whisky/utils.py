SHERRY_PORT_KEYWORDS = [
    "sherry",
    "oloroso",
    "pedro ximénez",
    "px",
    "fino",
    "port",
]

BOURBON_WOOD_KEYWORDS = [
    "bourbon",
    "virgin oak",
    "french oak",
    "american oak",
]


def classify_cask_type(cask_type_str):
    """Classify a cask_type string into a category.

    Priority: sherry/port > bourbon/wood > other.
    Returns: "sherry", "bourbon", or "other".
    """
    if not cask_type_str:
        return "other"

    lower = cask_type_str.lower()

    for keyword in SHERRY_PORT_KEYWORDS:
        if keyword in lower:
            return "sherry"

    for keyword in BOURBON_WOOD_KEYWORDS:
        if keyword in lower:
            return "bourbon"

    return "other"

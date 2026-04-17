from django.db.models.functions import Coalesce, TruncDate


def format_bottle_location(storage, row, column):
    parts = []
    if storage:
        parts.append(storage.name)

    position_parts = []
    if row is not None:
        position_parts.append(f"Row {row}")
    if column is not None:
        position_parts.append(f"Cell {column}")

    if position_parts:
        parts.append(", ".join(position_parts))

    return " - ".join(parts) if parts else "Unassigned"


def format_move_detail(
    from_storage,
    from_row,
    from_column,
    to_storage,
    to_row,
    to_column,
):
    return (
        f"{format_bottle_location(from_storage, from_row, from_column)}"
        f" -> {format_bottle_location(to_storage, to_row, to_column)}"
    )


def format_given_detail(recipient, occasion=""):
    parts = []
    if recipient:
        parts.append(f"Recipient: {recipient}")
    if occasion:
        parts.append(f"Occasion: {occasion}")
    return "\n".join(parts)


def with_removal_sort_date(queryset):
    return queryset.annotate(
        removal_sort_date=Coalesce(
            "given_date",
            "finished_date",
            TruncDate("created"),
        )
    )

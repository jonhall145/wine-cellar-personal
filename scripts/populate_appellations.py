#!/usr/bin/env python3
"""
Populate appellation field on existing wines that don't have one set.

Matches wines to appellations using:
1. Exact match on subregion text -> appellation name
2. Partial match (subregion contains appellation name or vice versa)
3. Country-aware matching (only matches appellations from same country)

Usage:
    # Dry run (show what would be updated):
    python manage.py shell < scripts/populate_appellations.py

    # Or via: python manage.py runscript populate_appellations
"""

import os
import sys

import django

# Setup Django if running standalone
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wine_cellar.conf.settings")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    django.setup()

from wine_cellar.apps.wine.models import Appellation, Wine


def populate_appellations(dry_run=False):
    """Match wines without appellations to the best matching appellation."""

    # Build lookup structures
    appellations = list(Appellation.objects.all())

    # name (lowercase) -> appellation
    exact_lookup = {}
    for a in appellations:
        exact_lookup[a.name.lower()] = a

    # country -> [appellations]
    country_lookup = {}
    for a in appellations:
        country_lookup.setdefault(a.country, []).append(a)

    # Find wines missing appellation
    wines = Wine.objects.filter(appellation__isnull=True)
    total = wines.count()

    if total == 0:
        print("All wines already have appellations set. Nothing to do.")
        return

    print(f"Found {total} wines without appellation.\n")

    updated = 0
    matched_by_subregion = 0
    matched_by_country = 0
    unmatched = []

    for wine in wines:
        match = None
        match_type = None

        subregion = (wine.subregion or "").strip()
        country = wine.country

        # Strategy 1: Exact match on subregion
        if subregion:
            sub_lower = subregion.lower()
            if sub_lower in exact_lookup:
                match = exact_lookup[sub_lower]
                match_type = "exact subregion"

            # Strategy 2: Partial match - subregion contains appellation name
            if not match:
                candidates = country_lookup.get(country, [])
                for a in candidates:
                    if a.name.lower() in sub_lower or sub_lower in a.name.lower():
                        match = a
                        match_type = "partial subregion"
                        break

        # Strategy 3: Country-only match - skipped (too ambiguous)

        if match:
            if match_type == "exact subregion":
                matched_by_subregion += 1
            else:
                matched_by_country += 1

            action = "WOULD SET" if dry_run else "SET"
            print(
                f"  {action}: {wine.name} ({wine.country}, "
                f'subregion="{subregion}") -> {match.name} [{match_type}]'
            )

            if not dry_run:
                wine.appellation = match
                wine.save(update_fields=["appellation"])
            updated += 1
        else:
            if subregion:
                unmatched.append(
                    f"  SKIP: {wine.name} ({wine.country}, "
                    f'subregion="{subregion}") - no match found'
                )

    print(f"\n{'DRY RUN ' if dry_run else ''}Summary:")
    print(f"  Total wines without appellation: {total}")
    print(f"  Matched by exact subregion: {matched_by_subregion}")
    print(f"  Matched by partial subregion: {matched_by_country}")
    print(f"  Total updated: {updated}")
    print(f"  Unmatched with subregion: {len(unmatched)}")

    if unmatched:
        print("\nUnmatched wines with subregion text:")
        for line in unmatched:
            print(line)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    populate_appellations(dry_run=dry_run)
else:
    # Running via manage.py shell
    print("=== Dry Run ===")
    populate_appellations(dry_run=True)
    print("\n=== To apply, run: ===")
    print(
        "source venv/bin/activate && "
        "DJANGO_SETTINGS_MODULE=wine_cellar.conf.settings "
        "python -c \"exec(open('scripts/populate_appellations.py').read()); "
        'populate_appellations(dry_run=False)"'
    )

"""Load all appellations from expanded fixture data."""

from django.db import migrations


def load_appellations(apps, schema_editor):
    """Load all appellations (pk 1-145), creating base ones if missing."""
    Appellation = apps.get_model("wine", "Appellation")

    # All appellations - parent_region set in second pass to avoid FK issues
    appellations = [
        # France
        (1, "Bordeaux", "FR", 44.8378, -0.5792),
        (2, "Burgundy", "FR", 47.0520, 4.3833),
        (3, "Champagne", "FR", 49.0500, 4.0500),
        (4, "Rhone Valley", "FR", 44.9333, 4.8833),
        (5, "Loire Valley", "FR", 47.3833, 0.6833),
        (6, "Alsace", "FR", 48.0833, 7.3500),
        (7, "Provence", "FR", 43.5333, 6.0500),
        (8, "Languedoc", "FR", 43.6167, 3.8833),
        (9, "Beaujolais", "FR", 46.1500, 4.6667),
        (10, "Chablis", "FR", 47.8167, 3.8000),
        # Italy
        (11, "Tuscany", "IT", 43.7711, 11.2486),
        (12, "Piedmont", "IT", 44.6939, 7.6708),
        (13, "Veneto", "IT", 45.4408, 12.3155),
        (14, "Sicily", "IT", 37.5000, 14.0000),
        (15, "Chianti", "IT", 43.4600, 11.2533),
        (16, "Barolo", "IT", 44.6094, 7.9394),
        (17, "Prosecco", "IT", 45.8833, 12.0667),
        # Spain
        (18, "Rioja", "ES", 42.4500, -2.4500),
        (19, "Ribera del Duero", "ES", 41.6500, -3.7000),
        (20, "Priorat", "ES", 41.2000, 0.7500),
        (21, "Rias Baixas", "ES", 42.3333, -8.6667),
        (22, "Cava", "ES", 41.4500, 1.7500),
        # Portugal
        (23, "Douro Valley", "PT", 41.1564, -7.8528),
        (24, "Vinho Verde", "PT", 41.8000, -8.4000),
        (25, "Dao", "PT", 40.5167, -7.9000),
        (26, "Alentejo", "PT", 38.5667, -7.9000),
        # Germany
        (27, "Mosel", "DE", 49.9667, 6.7500),
        (28, "Rheingau", "DE", 50.0167, 8.0500),
        (29, "Pfalz", "DE", 49.2333, 8.0833),
        # USA
        (30, "Napa Valley", "US", 38.4596, -122.4286),
        (31, "Sonoma", "US", 38.5110, -122.8453),
        (32, "Willamette Valley", "US", 45.0522, -123.0855),
        (33, "Paso Robles", "US", 35.6264, -120.6910),
        # Australia
        (34, "Barossa Valley", "AU", -34.5333, 138.9500),
        (35, "Margaret River", "AU", -33.9500, 115.0667),
        (36, "Hunter Valley", "AU", -32.8167, 151.1500),
        (37, "McLaren Vale", "AU", -35.2167, 138.5500),
        # New Zealand
        (38, "Marlborough", "NZ", -41.5167, 173.9500),
        (39, "Central Otago", "NZ", -45.0333, 169.1500),
        (40, "Hawke's Bay", "NZ", -39.6500, 176.8500),
        # Argentina
        (41, "Mendoza", "AR", -32.8833, -68.8167),
        (42, "Salta", "AR", -24.7833, -65.4167),
        # Chile
        (43, "Maipo Valley", "CL", -33.6833, -70.6500),
        (44, "Casablanca Valley", "CL", -33.3167, -71.4000),
        (45, "Colchagua Valley", "CL", -34.5833, -71.2167),
        # South Africa
        (46, "Stellenbosch", "ZA", -33.9333, 18.8500),
        (47, "Constantia", "ZA", -34.0333, 18.4167),
        # Austria / Greece / Hungary
        (48, "Wachau", "AT", 48.3667, 15.5167),
        (49, "Santorini", "GR", 36.4167, 25.4333),
        (50, "Tokaj", "HU", 48.1167, 21.4000),
        # New France sub-regions
        (51, "Saint-\u00c9milion", "FR", 44.8944, -0.1547),
        (52, "Pauillac", "FR", 45.1972, -0.7478),
        (53, "Margaux", "FR", 45.0422, -0.6681),
        (54, "Sauternes", "FR", 44.5333, -0.3167),
        (55, "Ch\u00e2teauneuf-du-Pape", "FR", 44.0564, 4.8331),
        (56, "C\u00f4tes du Rh\u00f4ne", "FR", 44.2500, 4.7500),
        (57, "Vouvray", "FR", 47.4133, 0.7919),
        (58, "Muscadet", "FR", 47.0833, -1.6667),
        (59, "Sancerre", "FR", 47.3306, 2.8389),
        (60, "Cahors", "FR", 44.4500, 1.4333),
        (61, "Jura", "FR", 46.7333, 5.9167),
        (62, "C\u00f4tes de Provence", "FR", 43.4667, 6.2333),
        (63, "M\u00e9doc", "FR", 45.1500, -0.8833),
        (64, "Pomerol", "FR", 44.9306, -0.1917),
        (65, "Roussillon", "FR", 42.6833, 2.8833),
        (66, "Bandol", "FR", 43.1500, 5.7500),
        # New Italy
        (67, "Abruzzo", "IT", 42.3500, 13.4000),
        (68, "Puglia", "IT", 41.1253, 16.8667),
        (69, "Campania", "IT", 40.8333, 14.2500),
        (70, "Sardinia", "IT", 39.2167, 9.1167),
        (71, "Friuli-Venezia Giulia", "IT", 45.6333, 13.8000),
        (72, "Trentino-Alto Adige", "IT", 46.0667, 11.1167),
        (73, "Lombardy", "IT", 45.4642, 9.1900),
        (74, "Umbria", "IT", 42.7167, 12.3833),
        (75, "Emilia-Romagna", "IT", 44.4939, 11.3428),
        (76, "Brunello di Montalcino", "IT", 43.0583, 11.4917),
        (77, "Valpolicella", "IT", 45.5167, 10.8833),
        (78, "Barbaresco", "IT", 44.7239, 8.0833),
        (79, "Soave", "IT", 45.4167, 11.2500),
        (80, "Amarone", "IT", 45.5000, 10.9000),
        (81, "Asti", "IT", 44.9000, 8.2069),
        (82, "Marche", "IT", 43.6167, 13.5167),
        # New Spain
        (83, "Navarra", "ES", 42.6667, -1.6667),
        (84, "Pened\u00e8s", "ES", 41.3500, 1.7000),
        (85, "Rueda", "ES", 41.4167, -4.9500),
        (86, "Toro", "ES", 41.5167, -5.3833),
        (87, "Jerez", "ES", 36.6833, -6.1333),
        (88, "Jumilla", "ES", 38.4833, -1.3167),
        (89, "Vald\u00e9penas", "ES", 38.7622, -3.3836),
        (90, "Galicia", "ES", 42.5750, -8.1339),
        # New Germany
        (91, "Nahe", "DE", 49.8333, 7.6000),
        (92, "Rheinhessen", "DE", 49.8333, 8.1500),
        (93, "Baden", "DE", 48.0000, 7.8500),
        (94, "Franken", "DE", 49.8000, 10.0000),
        (95, "W\u00fcrttemberg", "DE", 48.8833, 9.2000),
        (96, "Ahr", "DE", 50.5333, 7.0333),
        # New Portugal
        (97, "Madeira", "PT", 32.6500, -16.9083),
        (98, "Bairrada", "PT", 40.3833, -8.5000),
        (99, "Lisboa", "PT", 39.0000, -9.1667),
        (100, "Set\u00fabal", "PT", 38.5333, -8.9000),
        (101, "Beira Interior", "PT", 40.3500, -7.3500),
        (102, "Tr\u00e1s-os-Montes", "PT", 41.5000, -7.2500),
        (103, "Tejo", "PT", 39.4000, -8.4000),
        # New USA
        (104, "Finger Lakes", "US", 42.6833, -76.9333),
        (105, "Walla Walla Valley", "US", 46.0667, -118.3333),
        (106, "Columbia Valley", "US", 46.7333, -119.7833),
        (107, "Santa Barbara", "US", 34.7200, -119.7014),
        (108, "Russian River Valley", "US", 38.5200, -122.9100),
        (109, "Central Coast", "US", 35.5000, -120.7000),
        (110, "Lodi", "US", 38.1302, -121.2724),
        (111, "Alexander Valley", "US", 38.6500, -122.8500),
        # New South Africa
        (112, "Swartland", "ZA", -33.4500, 18.7333),
        (113, "Franschhoek", "ZA", -33.9000, 19.1167),
        (114, "Paarl", "ZA", -33.7333, 18.9667),
        (115, "Walker Bay", "ZA", -34.3667, 19.3333),
        (116, "Elgin", "ZA", -34.1500, 19.0500),
        # New Australia
        (117, "Coonawarra", "AU", -37.2833, 140.8333),
        (118, "Yarra Valley", "AU", -37.7500, 145.4667),
        (119, "Eden Valley", "AU", -34.6333, 139.0667),
        (120, "Clare Valley", "AU", -33.8333, 138.6000),
        (121, "Tasmania", "AU", -42.0000, 146.5000),
        (122, "Adelaide Hills", "AU", -35.0167, 138.7167),
        (123, "Rutherglen", "AU", -36.0500, 146.4667),
        # New New Zealand
        (124, "Waipara", "NZ", -43.0667, 172.7500),
        (125, "Gisborne", "NZ", -38.6667, 178.0167),
        (126, "Wairarapa", "NZ", -41.2333, 175.3833),
        # New Argentina
        (127, "Uco Valley", "AR", -33.6833, -69.2500),
        (128, "Patagonia", "AR", -39.0000, -67.5000),
        (129, "San Juan", "AR", -31.5375, -68.5364),
        # New Chile
        (130, "Rapel Valley", "CL", -34.2000, -71.2000),
        (131, "Aconcagua Valley", "CL", -32.8333, -70.7167),
        (132, "Leyda Valley", "CL", -33.6167, -71.5000),
        # New Austria
        (133, "Kremstal", "AT", 48.4167, 15.6000),
        (134, "Kamptal", "AT", 48.4000, 15.6667),
        (135, "Burgenland", "AT", 47.8500, 16.5333),
        # Other countries
        (136, "Bekaa Valley", "LB", 33.8500, 35.9000),
        (137, "Kakheti", "GE", 41.9500, 45.4000),
        (138, "Niagara Peninsula", "CA", 43.0833, -79.1500),
        (139, "Okanagan Valley", "CA", 49.5000, -119.5667),
        (140, "Nemea", "GR", 37.8167, 22.6667),
        (141, "Naoussa", "GR", 40.6333, 22.0667),
        (142, "Dalmatia", "HR", 43.5167, 16.4500),
        (143, "Sussex", "GB", 50.8270, -0.1530),
        (144, "Etna", "IT", 37.7510, 14.9934),
        (145, "Ribera del Guadiana", "ES", 38.9000, -6.3500),
    ]

    # Parent region mappings (child_pk -> parent_pk)
    parent_map = {
        10: 2,  # Chablis -> Burgundy
        15: 11,  # Chianti -> Tuscany
        16: 12,  # Barolo -> Piedmont
        17: 13,  # Prosecco -> Veneto
        51: 1,  # Saint-Emilion -> Bordeaux
        52: 1,  # Pauillac -> Bordeaux
        53: 1,  # Margaux -> Bordeaux
        54: 1,  # Sauternes -> Bordeaux
        55: 4,  # Chateauneuf-du-Pape -> Rhone
        56: 4,  # Cotes du Rhone -> Rhone
        57: 5,  # Vouvray -> Loire
        58: 5,  # Muscadet -> Loire
        59: 5,  # Sancerre -> Loire
        62: 7,  # Cotes de Provence -> Provence
        63: 1,  # Medoc -> Bordeaux
        64: 1,  # Pomerol -> Bordeaux
        66: 7,  # Bandol -> Provence
        76: 11,  # Brunello di Montalcino -> Tuscany
        77: 13,  # Valpolicella -> Veneto
        78: 12,  # Barbaresco -> Piedmont
        79: 13,  # Soave -> Veneto
        80: 13,  # Amarone -> Veneto
        81: 12,  # Asti -> Piedmont
        108: 31,  # Russian River Valley -> Sonoma
        111: 31,  # Alexander Valley -> Sonoma
        127: 41,  # Uco Valley -> Mendoza
        144: 14,  # Etna -> Sicily
    }

    # First pass: create all without parent_region
    for pk, name, country, lat, lng in appellations:
        Appellation.objects.update_or_create(
            pk=pk,
            defaults={
                "name": name,
                "country": country,
                "latitude": lat,
                "longitude": lng,
                "parent_region_id": None,
            },
        )

    # Second pass: set parent regions
    for child_pk, parent_pk in parent_map.items():
        Appellation.objects.filter(pk=child_pk).update(parent_region_id=parent_pk)


def reverse_migration(apps, schema_editor):
    Appellation = apps.get_model("wine", "Appellation")
    # Only delete the new ones (51+), keep originals
    Appellation.objects.filter(pk__gte=51, pk__lte=145).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("wine", "0038_remove_wine_barcode_field"),
    ]

    operations = [
        migrations.RunPython(load_appellations, reverse_migration),
    ]

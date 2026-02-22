"""Load expanded appellations fixture (pk 146-334)."""

from django.db import migrations


def load_appellations(apps, schema_editor):
    """Add new appellations (pk 146-334) without touching existing ones."""
    Appellation = apps.get_model("wine", "Appellation")

    new_appellations = [
        # France – Bordeaux sub-regions
        (146, "Saint-Julien", "FR", 45.1794, -0.7217),
        (147, "Saint-Est\u00e8phe", "FR", 45.2500, -0.7667),
        (148, "Moulis", "FR", 45.0833, -0.8333),
        (149, "Listrac", "FR", 45.0833, -0.8667),
        (150, "Haut-M\u00e9doc", "FR", 45.1333, -0.8167),
        (151, "Pessac-L\u00e9ognan", "FR", 44.7167, -0.5833),
        (152, "Graves", "FR", 44.5833, -0.5667),
        (153, "Fronsac", "FR", 44.9667, -0.2667),
        (154, "Lalande-de-Pomerol", "FR", 44.9583, -0.1917),
        (155, "Barsac", "FR", 44.5667, -0.3333),
        (156, "Blaye", "FR", 45.1286, -0.6669),
        (157, "Bourg", "FR", 45.0500, -0.5667),
        # France – Burgundy villages
        (158, "Gevrey-Chambertin", "FR", 47.2333, 4.9667),
        (159, "Chambolle-Musigny", "FR", 47.1944, 4.9583),
        (160, "Vosne-Roman\u00e9e", "FR", 47.1667, 4.9667),
        (161, "Nuits-Saint-Georges", "FR", 47.1167, 4.9500),
        (162, "Pommard", "FR", 47.0333, 4.7833),
        (163, "Volnay", "FR", 47.0167, 4.7667),
        (164, "Meursault", "FR", 46.9833, 4.7667),
        (165, "Puligny-Montrachet", "FR", 46.9500, 4.7500),
        (166, "Chassagne-Montrachet", "FR", 46.9333, 4.7500),
        (167, "Aloxe-Corton", "FR", 47.0667, 4.8333),
        (168, "Pouilly-Fuiss\u00e9", "FR", 46.2833, 4.7500),
        (169, "C\u00f4te de Nuits", "FR", 47.1500, 4.9500),
        (170, "C\u00f4te de Beaune", "FR", 47.0000, 4.8000),
        (171, "C\u00f4te Chalonnaise", "FR", 46.7000, 4.7833),
        (172, "M\u00e2connais", "FR", 46.3000, 4.8333),
        # France – Rhône sub-zones
        (173, "Hermitage", "FR", 45.0861, 4.8333),
        (174, "Crozes-Hermitage", "FR", 45.0667, 4.8500),
        (175, "Condrieu", "FR", 45.4667, 4.7667),
        (176, "C\u00f4te-R\u00f4tie", "FR", 45.5333, 4.7667),
        (177, "Saint-Joseph", "FR", 45.2000, 4.7667),
        (178, "Cornas", "FR", 44.9333, 4.8333),
        (179, "Gigondas", "FR", 44.1667, 5.0000),
        (180, "Vacqueyras", "FR", 44.1500, 4.9833),
        (181, "Lirac", "FR", 44.0167, 4.7333),
        (182, "Tavel", "FR", 44.0167, 4.7000),
        (183, "Rasteau", "FR", 44.2167, 5.0000),
        (184, "Ventoux", "FR", 44.1583, 5.2789),
        # France – Loire sub-zones
        (185, "Chinon", "FR", 47.1667, 0.2500),
        (186, "Bourgueil", "FR", 47.2833, 0.1667),
        (187, "Anjou", "FR", 47.4667, -0.5500),
        (188, "Touraine", "FR", 47.4000, 0.8833),
        (189, "Pouilly-Fum\u00e9", "FR", 47.3167, 2.9500),
        (190, "Menetou-Salon", "FR", 47.2167, 2.5167),
        # France – Languedoc sub-zones
        (191, "Corbi\u00e8res", "FR", 43.0833, 2.5333),
        (192, "Minervois", "FR", 43.3667, 2.6167),
        (193, "Fitou", "FR", 42.9667, 2.9333),
        (194, "Picpoul de Pinet", "FR", 43.4167, 3.5000),
        (195, "Costi\u00e8res de N\u00eemes", "FR", 43.7000, 4.4167),
        # France – SW / other
        (196, "Bergerac", "FR", 44.8500, 0.4833),
        (197, "Madiran", "FR", 43.5833, -0.2833),
        (198, "Gaillac", "FR", 43.9000, 1.9000),
        (199, "Luberon", "FR", 43.7833, 5.3500),
        # Italy – Piedmont
        (200, "Barbera d'Asti", "IT", 44.9000, 8.2069),
        (201, "Dolcetto d'Alba", "IT", 44.7000, 8.0167),
        (202, "Roero", "IT", 44.7833, 7.9667),
        (203, "Gavi", "IT", 44.6833, 8.8000),
        (204, "Moscato d'Asti", "IT", 44.8056, 8.1806),
        (205, "Langhe", "IT", 44.6333, 8.0000),
        (206, "Nizza", "IT", 44.7667, 8.3500),
        (207, "Barbera d'Alba", "IT", 44.7000, 8.0333),
        # Italy – Tuscany
        (208, "Bolgheri", "IT", 43.2167, 10.6000),
        (209, "Morellino di Scansano", "IT", 42.6833, 11.3333),
        (210, "Carmignano", "IT", 43.8000, 11.0167),
        (211, "Vino Nobile di Montepulciano", "IT", 43.1000, 11.7833),
        (212, "Vernaccia di San Gimignano", "IT", 43.4667, 11.0500),
        (213, "Maremma Toscana", "IT", 42.7667, 11.1667),
        # Italy – Veneto
        (214, "Bardolino", "IT", 45.5500, 10.7167),
        (215, "Lugana", "IT", 45.4833, 10.7167),
        # Italy – Central & South
        (216, "Montepulciano d'Abruzzo", "IT", 42.3500, 13.4000),
        (217, "Primitivo di Manduria", "IT", 40.3500, 17.6333),
        (218, "Salice Salentino", "IT", 40.2167, 17.8833),
        (219, "Taurasi", "IT", 40.9833, 14.9333),
        (220, "Greco di Tufo", "IT", 40.9667, 14.8333),
        (221, "Fiano di Avellino", "IT", 40.9167, 14.7833),
        (222, "Falanghina", "IT", 41.1667, 14.3500),
        (223, "Sagrantino di Montefalco", "IT", 42.9333, 12.6500),
        (224, "Verdicchio dei Castelli di Jesi", "IT", 43.5000, 13.2667),
        (225, "Vermentino di Sardegna", "IT", 40.5000, 9.0000),
        (226, "Nero d'Avola", "IT", 36.9000, 15.1000),
        (227, "Marsala", "IT", 37.8000, 12.4333),
        # Spain – Rioja sub-zones
        (228, "Rioja Alta", "ES", 42.5000, -2.8500),
        (229, "Rioja Alavesa", "ES", 42.6667, -2.6667),
        (230, "Rioja Oriental", "ES", 42.2500, -1.9000),
        # Spain – other
        (231, "Bierzo", "ES", 42.6000, -6.7000),
        (232, "Txakoli", "ES", 43.2667, -2.5333),
        (233, "Calatayud", "ES", 41.3500, -1.6500),
        (234, "Campo de Borja", "ES", 41.8500, -1.6833),
        (235, "Cari\u00f1ena", "ES", 41.3333, -1.2167),
        (236, "Somontano", "ES", 42.1000, -0.1000),
        (237, "Yecla", "ES", 38.6167, -1.1167),
        (238, "Alicante", "ES", 38.3500, -0.4833),
        (239, "Utiel-Requena", "ES", 39.5667, -1.2333),
        (240, "Montsant", "ES", 41.2500, 0.8500),
        (241, "Terra Alta", "ES", 41.0500, 0.4167),
        (242, "Costers del Segre", "ES", 41.8667, 0.8833),
        # Portugal – Douro sub-zones
        (243, "Douro Superior", "PT", 41.2333, -7.0000),
        (244, "Cima Corgo", "PT", 41.1333, -7.5000),
        (245, "Baixo Corgo", "PT", 41.1667, -7.8500),
        # Portugal – other
        (246, "Bucelas", "PT", 38.9500, -9.1000),
        (247, "Alentejano", "PT", 38.5500, -7.9333),
        (248, "Palmela", "PT", 38.5667, -8.9000),
        (249, "Pico", "PT", 38.4667, -28.3333),
        # Germany – Mosel sub-zones
        (250, "Bernkastel", "DE", 49.9167, 7.0667),
        (251, "Piesport", "DE", 49.8833, 6.9167),
        (252, "Wehlen", "DE", 49.9333, 7.0500),
        (253, "Brauneberg", "DE", 49.9000, 6.9833),
        (254, "Erden", "DE", 49.9667, 7.0667),
        (255, "\u00dcrzig", "DE", 50.0000, 7.0833),
        # Germany – Rheingau sub-zones
        (256, "Johannisberg", "DE", 49.9833, 7.9833),
        (257, "R\u00fcdesheim", "DE", 49.9833, 7.9167),
        (258, "Hochheim", "DE", 50.0167, 8.3500),
        (259, "Hattenheim", "DE", 49.9833, 8.0833),
        (260, "Eltville", "DE", 50.0333, 8.1167),
        # USA – Napa sub-AVAs
        (261, "Oakville", "US", 38.4333, -122.4167),
        (262, "Rutherford", "US", 38.4667, -122.4333),
        (263, "Stags Leap District", "US", 38.3833, -122.3833),
        (264, "Howell Mountain", "US", 38.5833, -122.3500),
        (265, "Mount Veeder", "US", 38.3667, -122.3833),
        (266, "Spring Mountain", "US", 38.5000, -122.5333),
        (267, "Coombsville", "US", 38.2833, -122.2833),
        (268, "Atlas Peak", "US", 38.3833, -122.3333),
        (269, "Carneros", "US", 38.2167, -122.4667),
        (270, "Oak Knoll District", "US", 38.3500, -122.3500),
        # USA – Sonoma sub-AVAs
        (271, "Dry Creek Valley", "US", 38.7000, -122.9833),
        (272, "Knights Valley", "US", 38.7333, -122.6833),
        (273, "Chalk Hill", "US", 38.6000, -122.8333),
        (274, "Sonoma Valley", "US", 38.3167, -122.5833),
        (275, "Sonoma Coast", "US", 38.4667, -123.0167),
        (276, "Fort Ross-Seaview", "US", 38.5833, -123.2500),
        (277, "Petaluma Gap", "US", 38.2500, -122.7500),
        (278, "Los Carneros", "US", 38.2167, -122.4333),
        # USA – Oregon sub-AVAs
        (279, "Dundee Hills", "US", 45.2833, -123.0000),
        (280, "Chehalem Mountains", "US", 45.4167, -123.0833),
        (281, "Ribbon Ridge", "US", 45.4167, -123.1667),
        (282, "Yamhill-Carlton", "US", 45.3333, -123.2167),
        (283, "Eola-Amity Hills", "US", 45.1167, -123.1667),
        (284, "McMinnville", "US", 45.2167, -123.2333),
        # USA – Washington sub-AVAs
        (285, "Horse Heaven Hills", "US", 46.0000, -119.8333),
        (286, "Wahluke Slope", "US", 46.6000, -119.9167),
        (287, "Rattlesnake Hills", "US", 46.4500, -120.0667),
        # USA – California other
        (288, "Santa Cruz Mountains", "US", 37.1667, -122.0833),
        (289, "Monterey", "US", 36.2167, -121.3167),
        (290, "Santa Ynez Valley", "US", 34.5833, -120.0833),
        (291, "Santa Maria Valley", "US", 34.8333, -120.3333),
        (292, "Sta. Rita Hills", "US", 34.6167, -120.3500),
        (293, "Edna Valley", "US", 35.2333, -120.6167),
        (294, "Ballard Canyon", "US", 34.7167, -120.0500),
        # Australia – Victoria
        (295, "Heathcote", "AU", -36.9167, 144.7167),
        (296, "Mornington Peninsula", "AU", -38.3833, 145.0833),
        (297, "Grampians", "AU", -37.0000, 142.5000),
        (298, "Macedon Ranges", "AU", -37.1000, 144.5667),
        (299, "Geelong", "AU", -38.1500, 144.3667),
        (300, "Beechworth", "AU", -36.3600, 146.6800),
        (301, "King Valley", "AU", -36.5833, 146.4500),
        # Australia – NSW
        (302, "Mudgee", "AU", -32.5833, 149.5833),
        # Australia – SA
        (303, "Langhorne Creek", "AU", -35.2833, 139.0333),
        (304, "Padthaway", "AU", -36.6000, 140.5167),
        (305, "Wrattonbully", "AU", -36.9000, 140.5000),
        (306, "Robe", "AU", -37.1667, 139.7500),
        # New Zealand – Marlborough sub-zones
        (307, "Wairau Valley", "NZ", -41.4833, 173.9667),
        (308, "Awatere Valley", "NZ", -41.8500, 174.1500),
        (309, "Southern Valleys", "NZ", -41.5500, 173.8333),
        # South Africa
        (310, "Hemel-en-Aarde", "ZA", -34.3833, 19.2833),
        (311, "Robertson", "ZA", -33.8167, 19.8833),
        (312, "Elim", "ZA", -34.5833, 19.7500),
        # Austria
        (313, "Weinviertel", "AT", 48.5000, 16.0000),
        (314, "Vienna", "AT", 48.1683, 16.3800),
        (315, "Thermenregion", "AT", 47.9667, 16.2500),
        # Hungary
        (316, "Eger", "HU", 47.9025, 20.3772),
        (317, "Vill\u00e1ny", "HU", 45.8667, 18.4500),
        # Greece
        (318, "Crete", "GR", 35.2401, 24.8093),
        (319, "Patras", "GR", 38.2444, 21.7344),
        # Switzerland
        (320, "Valais", "CH", 46.2333, 7.3500),
        (321, "Vaud", "CH", 46.5833, 6.5167),
        (322, "Geneva", "CH", 46.2000, 6.1500),
        # Canada
        (323, "Niagara Escarpment", "CA", 43.1500, -79.3167),
        (324, "Prince Edward County", "CA", 44.0000, -77.1500),
        # England
        (325, "Kent", "GB", 51.1667, 0.8833),
        (326, "Hampshire", "GB", 51.0667, -1.3167),
        (327, "Essex", "GB", 51.8000, 0.6167),
        # Israel
        (328, "Galilee", "IL", 32.8333, 35.5000),
        (329, "Golan Heights", "IL", 33.0833, 35.7833),
        # Brazil
        (330, "Vale dos Vinhedos", "BR", -29.1667, -51.5667),
        (331, "Serra Ga\u00facha", "BR", -29.0000, -51.5000),
        # Mexico
        (332, "Valle de Guadalupe", "MX", 32.0000, -116.5833),
        # Japan
        (333, "Yamanashi", "JP", 35.6667, 138.5500),
        (334, "Nagano", "JP", 36.6500, 138.1000),
    ]

    # Parent region mappings for new entries (child_pk -> parent_pk)
    parent_map = {
        # Bordeaux sub-regions
        146: 63,  # Saint-Julien -> Médoc
        147: 63,  # Saint-Estèphe -> Médoc
        148: 63,  # Moulis -> Médoc
        149: 63,  # Listrac -> Médoc
        150: 1,  # Haut-Médoc -> Bordeaux
        151: 1,  # Pessac-Léognan -> Bordeaux
        152: 1,  # Graves -> Bordeaux
        153: 1,  # Fronsac -> Bordeaux
        154: 1,  # Lalande-de-Pomerol -> Bordeaux
        155: 1,  # Barsac -> Bordeaux
        156: 1,  # Blaye -> Bordeaux
        157: 1,  # Bourg -> Bordeaux
        # Burgundy villages -> Burgundy
        158: 2,
        159: 2,
        160: 2,
        161: 2,
        162: 2,
        163: 2,
        164: 2,
        165: 2,
        166: 2,
        167: 2,
        168: 2,
        169: 2,  # Côte de Nuits -> Burgundy
        170: 2,  # Côte de Beaune -> Burgundy
        171: 2,  # Côte Chalonnaise -> Burgundy
        172: 2,  # Mâconnais -> Burgundy
        # Rhône sub-zones -> Rhône Valley
        173: 4,
        174: 4,
        175: 4,
        176: 4,
        177: 4,
        178: 4,
        179: 4,
        180: 4,
        181: 4,
        182: 4,
        183: 4,
        184: 4,
        # Loire sub-zones -> Loire Valley
        185: 5,
        186: 5,
        187: 5,
        188: 5,
        189: 5,
        190: 5,
        # Languedoc sub-zones -> Languedoc
        191: 8,
        192: 8,
        193: 8,
        194: 8,
        195: 8,
        # Italy – Piedmont sub-zones
        200: 12,
        201: 12,
        202: 12,
        203: 12,
        204: 12,
        205: 12,
        206: 12,
        207: 12,
        # Italy – Tuscany sub-zones
        208: 11,
        209: 11,
        210: 11,
        211: 11,
        212: 11,
        213: 11,
        # Italy – Veneto sub-zones
        214: 13,
        215: 13,
        # Italy – other regional sub-zones
        216: 67,  # Montepulciano d'Abruzzo -> Abruzzo
        217: 68,  # Primitivo di Manduria -> Puglia
        218: 68,  # Salice Salentino -> Puglia
        219: 69,  # Taurasi -> Campania
        220: 69,  # Greco di Tufo -> Campania
        221: 69,  # Fiano di Avellino -> Campania
        222: 69,  # Falanghina -> Campania
        223: 74,  # Sagrantino di Montefalco -> Umbria
        224: 82,  # Verdicchio dei Castelli di Jesi -> Marche
        225: 70,  # Vermentino di Sardegna -> Sardinia
        226: 14,  # Nero d'Avola -> Sicily
        227: 14,  # Marsala -> Sicily
        # Spain – Rioja sub-zones
        228: 18,
        229: 18,
        230: 18,
        # Portugal – Douro sub-zones
        243: 23,
        244: 23,
        245: 23,
        # Germany – Mosel sub-zones
        250: 27,
        251: 27,
        252: 27,
        253: 27,
        254: 27,
        255: 27,
        # Germany – Rheingau sub-zones
        256: 28,
        257: 28,
        258: 28,
        259: 28,
        260: 28,
        # USA – Napa sub-AVAs
        261: 30,
        262: 30,
        263: 30,
        264: 30,
        265: 30,
        266: 30,
        267: 30,
        268: 30,
        269: 30,
        270: 30,
        # USA – Sonoma sub-AVAs
        271: 31,
        272: 31,
        273: 31,
        274: 31,
        275: 31,
        276: 31,
        277: 31,
        278: 31,
        # USA – Oregon sub-AVAs
        279: 32,
        280: 32,
        281: 32,
        282: 32,
        283: 32,
        284: 32,
        # USA – Washington sub-AVAs
        285: 106,
        286: 106,
        287: 106,
        # USA – Santa Barbara sub-AVAs
        290: 107,
        291: 107,
        292: 107,
        294: 107,
        # NZ – Marlborough sub-zones
        307: 38,
        308: 38,
        309: 38,
        # ZA – Walker Bay ward
        310: 115,
        # Canada – Niagara Peninsula sub-zone
        323: 138,
    }

    # First pass: create all without parent_region
    for pk, name, country, lat, lng in new_appellations:
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
    Appellation.objects.filter(pk__gte=146, pk__lte=334).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("wine", "0042_remove_rrp_preserve_price"),
    ]

    operations = [
        migrations.RunPython(load_appellations, reverse_migration),
    ]

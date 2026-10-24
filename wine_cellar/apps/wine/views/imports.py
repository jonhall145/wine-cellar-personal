from wine_cellar.apps.core.import_views import BaseCsvImportView
from wine_cellar.apps.wine.importing import WineCsvImporter


class WineImportView(BaseCsvImportView):
    importer_class = WineCsvImporter
    list_url_name = "wine-list"
    session_key = "wine_csv_import_preview"

from django.apps import AppConfig


class HardwareConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wine_cellar.apps.hardware'
    verbose_name = 'Hardware Integration'

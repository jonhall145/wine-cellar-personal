from django.apps import AppConfig


class WhiskyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "wine_cellar.apps.whisky"
    verbose_name = "Whisky"

    def ready(self):
        import wine_cellar.apps.whisky.signals  # noqa

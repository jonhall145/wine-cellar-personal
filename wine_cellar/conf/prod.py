# Import all settings from base settings module
# Using wildcard import here is acceptable as this is a settings override pattern
from wine_cellar.conf.settings import *  # noqa: F403

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

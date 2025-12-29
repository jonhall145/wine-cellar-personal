from wine_cellar.conf.settings import BASE_DIR

MEDIA_ROOT = BASE_DIR / "test_media/"

CELERY_TASK_ALWAYS_EAGER = True

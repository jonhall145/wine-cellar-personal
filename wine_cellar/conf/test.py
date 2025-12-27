from .settings import BASE_DIR  # noqa: F401

MEDIA_ROOT = BASE_DIR / "test_media/"

CELERY_TASK_ALWAYS_EAGER = True

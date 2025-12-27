# Import all settings from base settings module
# This is the standard Django pattern for test settings that override base settings
from .settings import *  # noqa: F403

MEDIA_ROOT = BASE_DIR / "test_media/"  # noqa: F405

CELERY_TASK_ALWAYS_EAGER = True

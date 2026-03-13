import logging

import pytest

from wine_cellar.apps.core.audit import log_create, log_delete, log_update


class _LogCapture(logging.Handler):
    """Simple handler that captures log records in a list."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))


@pytest.fixture
def audit_logs():
    """Capture audit logs regardless of propagate settings."""
    handler = _LogCapture()
    logger = logging.getLogger("wine_cellar.audit")
    logger.addHandler(handler)
    yield handler.records
    logger.removeHandler(handler)


@pytest.mark.django_db
class TestAuditLogging:
    def test_log_create(self, audit_logs, user, wine_factory):
        wine = wine_factory(user=user)
        log_create(user, wine)
        assert any(
            "created Wine" in msg and f"pk={wine.pk}" in msg for msg in audit_logs
        )

    def test_log_update(self, audit_logs, user, wine_factory):
        wine = wine_factory(user=user)
        log_update(user, wine, changed_fields=["name", "vintage"])
        text = "\n".join(audit_logs)
        assert "updated Wine" in text
        assert f"pk={wine.pk}" in text
        assert "name" in text
        assert "vintage" in text

    def test_log_update_no_fields(self, audit_logs, user, wine_factory):
        wine = wine_factory(user=user)
        log_update(user, wine)
        text = "\n".join(audit_logs)
        assert "updated Wine" in text
        assert "[]" in text

    def test_log_delete(self, audit_logs, user, wine_factory):
        wine = wine_factory(user=user)
        log_delete(user, wine)
        assert any(
            "deleted Wine" in msg and f"pk={wine.pk}" in msg for msg in audit_logs
        )

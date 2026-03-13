"""Tests for wine email sending functions."""

import pytest
from django.core import mail

from wine_cellar.apps.wine.emails import send_drink_by_reminder


@pytest.mark.django_db
class TestSendDrinkByReminder:
    def test_sends_email(self, user, wine_factory):
        wines = [wine_factory(user=user, name="Test Wine")]
        send_drink_by_reminder(user, wines)
        assert len(mail.outbox) == 1

    def test_email_recipient(self, user, wine_factory):
        wines = [wine_factory(user=user)]
        send_drink_by_reminder(user, wines)
        assert mail.outbox[0].to == [user.email]

    def test_email_subject_contains_reminder(self, user, wine_factory):
        wines = [wine_factory(user=user)]
        send_drink_by_reminder(user, wines)
        assert "reminder" in mail.outbox[0].subject.lower()

    def test_email_body_contains_wine_info(self, user, wine_factory):
        wines = [wine_factory(user=user, name="Château Lafite")]
        send_drink_by_reminder(user, wines)
        assert "Château Lafite" in mail.outbox[0].body

    def test_multiple_wines(self, user, wine_factory):
        wines = [
            wine_factory(user=user, name="Wine A"),
            wine_factory(user=user, name="Wine B"),
        ]
        send_drink_by_reminder(user, wines)
        assert len(mail.outbox) == 1
        body = mail.outbox[0].body
        assert "Wine A" in body
        assert "Wine B" in body

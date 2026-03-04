"""Audit logging helpers for CRUD operations."""

import logging

logger = logging.getLogger("wine_cellar.audit")


def log_create(user, instance) -> None:
    """Log creation of a model instance."""
    model = instance.__class__.__name__
    logger.info(
        "created %s pk=%s",
        model,
        instance.pk,
        extra={"user": user.pk, "action": "create", "model": model},
    )


def log_update(user, instance, changed_fields: list[str] | None = None) -> None:
    """Log update of a model instance."""
    model = instance.__class__.__name__
    logger.info(
        "updated %s pk=%s fields=%s",
        model,
        instance.pk,
        changed_fields or [],
        extra={"user": user.pk, "action": "update", "model": model},
    )


def log_delete(user, instance) -> None:
    """Log deletion of a model instance."""
    model = instance.__class__.__name__
    logger.info(
        "deleted %s pk=%s",
        model,
        instance.pk,
        extra={"user": user.pk, "action": "delete", "model": model},
    )
